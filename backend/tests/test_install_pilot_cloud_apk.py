"""Offline package preflight; no SDK or adb command is executed."""
import hashlib
import io
from pathlib import Path
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import install_pilot_cloud_apk as installer


class PilotApkPackageGuardTests(unittest.TestCase):
    AAPT = Path("C:/synthetic-sdk/build-tools/37.0.0/aapt.exe")
    APK = Path("synthetic-pilot.apk")
    VALID = b"package: name='com.meteofriul.app.localpilot' versionCode='300012' versionName='1.0.1-local-pilot'\napplication-debuggable\n"

    def test_exact_pilot_package_uses_bounded_fixed_sdk_tool(self):
        with patch.object(installer, "_resolve_aapt", return_value=self.AAPT), \
             patch.object(installer.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=self.VALID)) as run:
            installer.verify_apk_package(self.APK)
        self.assertEqual(run.call_args.args[0], [str(self.AAPT), "dump", "badging", str(self.APK.resolve())])
        self.assertEqual(run.call_args.kwargs["timeout"], 30)
        self.assertTrue(run.call_args.kwargs["capture_output"])

    def test_missing_malformed_duplicate_wrong_package_and_tool_failure_reject(self):
        bad_outputs = [
            b"", b"tool diagnostic with no metadata", b"package: malformed",
            b"package: name='com.meteofriul.app' versionCode='300012'",
            b"package: name='com.meteofriul.app.localpilot.evil'",
            b"package: name='com.meteofriul.app.localpilot'garbage",
            self.VALID + self.VALID, b"package: name='\xff'", b"x" * (2 * 1024 * 1024 + 1),
        ]
        for output in bad_outputs:
            with self.subTest(output_size=len(output)), \
                 patch.object(installer, "_resolve_aapt", return_value=self.AAPT), \
                 patch.object(installer.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=output)), \
                 self.assertRaisesRegex(RuntimeError, "^pilot_apk_package_identity_rejected$"):
                installer.verify_apk_package(self.APK)
        for failure in (subprocess.TimeoutExpired("private-output", 30), OSError("private-output")):
            with patch.object(installer, "_resolve_aapt", return_value=self.AAPT), \
                 patch.object(installer.subprocess, "run", side_effect=failure), \
                 self.assertRaisesRegex(RuntimeError, "^pilot_apk_package_identity_rejected$"):
                installer.verify_apk_package(self.APK)
        with patch.object(installer, "_resolve_aapt", return_value=self.AAPT), \
             patch.object(installer.subprocess, "run", return_value=SimpleNamespace(returncode=1, stdout=self.VALID)), \
             self.assertRaisesRegex(RuntimeError, "^pilot_apk_package_identity_rejected$"):
            installer.verify_apk_package(self.APK)

    def test_discovery_matches_guard_and_missing_tools_never_fall_back(self):
        root = Path("C:/synthetic-local/Android/Sdk/build-tools")
        with patch.dict("os.environ", {"LOCALAPPDATA": "C:/synthetic-local"}), \
             patch.object(Path, "iterdir", return_value=iter([root / "36.0.0", root / "37.0.0"])), \
             patch.object(Path, "is_dir", return_value=True), patch.object(Path, "is_file", return_value=True):
            self.assertEqual(installer._resolve_aapt(), root / "37.0.0/aapt.exe")
        for fault in ("directory-missing", "empty", "aapt-missing"):
            with self.subTest(fault=fault), patch.dict("os.environ", {"LOCALAPPDATA": "C:/synthetic-local"}), \
                 patch.object(Path, "iterdir", side_effect=FileNotFoundError() if fault == "directory-missing" else None,
                              return_value=iter([] if fault == "empty" else [root / "37.0.0"])), \
                 patch.object(Path, "is_dir", return_value=True), patch.object(Path, "is_file", return_value=False), \
                 patch.object(installer.subprocess, "run") as run, \
                 self.assertRaisesRegex(RuntimeError, "^pilot_apk_package_tool_unavailable$"):
                installer.verify_apk_package(self.APK)
            run.assert_not_called()

    def test_main_rejects_correctly_hashed_beta_apk_before_any_adb_command(self):
        content = b"synthetic-beta-apk"
        argv = ["install_pilot_cloud_apk", "--apk", str(self.APK), "--sha256", hashlib.sha256(content).hexdigest(), "--serial", "synthetic-device"]
        with patch("sys.argv", argv), patch.object(Path, "open", return_value=io.BytesIO(content)), \
             patch.object(installer, "_resolve_aapt", return_value=self.AAPT), \
             patch.object(installer.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=b"package: name='com.meteofriul.app'")) as run, \
             self.assertRaisesRegex(RuntimeError, "^pilot_apk_package_identity_rejected$"):
            installer.main()
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0][0], str(self.AAPT))
        self.assertNotIn("install", run.call_args.args[0])


if __name__ == "__main__":
    unittest.main()

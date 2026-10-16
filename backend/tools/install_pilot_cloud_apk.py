"""Owner pilot install-r with private-data hash and unchanged-beta checks."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

PACKAGE = "com.meteofriul.app.localpilot"
BETA = "com.meteofriul.app"


def _resolve_aapt():
    # Match the guarded pilot build: fixed local SDK, newest build-tools folder.
    # Do not fall back to an arbitrary executable from PATH or another SDK.
    try:
        root = Path(os.environ["LOCALAPPDATA"]) / "Android/Sdk/build-tools"
        versions = sorted((item for item in root.iterdir() if item.is_dir()),
                          key=lambda item: item.name, reverse=True)
        aapt = versions[0] / "aapt.exe"
        if not aapt.is_file():
            raise ValueError()
        return aapt
    except Exception:
        raise RuntimeError("pilot_apk_package_tool_unavailable") from None


def verify_apk_package(apk):
    aapt = _resolve_aapt()
    try:
        result = subprocess.run(
            [str(aapt), "dump", "badging", str(apk.resolve())],
            capture_output=True, timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0 or not isinstance(result.stdout, bytes) or len(result.stdout) > 2 * 1024 * 1024:
            raise ValueError()
        package_lines = [line for line in result.stdout.decode("utf-8").splitlines() if line.startswith("package:")]
        if len(package_lines) != 1:
            raise ValueError()
        match = re.match(r"^package: name='([^']+)'(?:\s|$)", package_lines[0])
        if match is None or match.group(1) != PACKAGE:
            raise ValueError()
    except Exception:
        # Never print subprocess output or continue to any adb command on error.
        raise RuntimeError("pilot_apk_package_identity_rejected") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--serial", required=True)
    args = parser.parse_args()
    if hashlib.file_digest(args.apk.open("rb"), "sha256").hexdigest() != args.sha256:
        raise RuntimeError("pilot_apk_checksum_mismatch")
    verify_apk_package(args.apk)
    adb = [str(Path(os.environ["LOCALAPPDATA"]) / "Android/Sdk/platform-tools/adb.exe"), "-s", args.serial]

    def run(*parts, timeout=60):
        result = subprocess.run(adb + list(parts), capture_output=True, timeout=timeout)
        if result.returncode:
            raise RuntimeError("pilot_adb_command_failed")
        return result.stdout

    def package_times(package):
        lines = run("shell", "dumpsys", "package", package).decode("utf-8", "replace").splitlines()
        return [line.strip() for line in lines if any(key in line for key in (
            "versionCode=", "versionName=", "firstInstallTime=", "lastUpdateTime="))]

    def private_hash():
        data = run("exec-out", "run-as", PACKAGE, "tar", "-cf", "-", "shared_prefs", "app_webview", "databases", "no_backup")
        if len(data) < 1024:
            raise RuntimeError("pilot_data_snapshot_empty")
        return hashlib.sha256(data).hexdigest()

    before_beta = package_times(BETA)
    before_pilot = package_times(PACKAGE)
    run("shell", "am", "force-stop", PACKAGE)
    before_data = private_hash()
    installed = run("install", "-r", str(args.apk.resolve()), timeout=180)
    if b"Success" not in installed:
        raise RuntimeError("pilot_install_not_confirmed")
    after_data = private_hash()
    after_beta = package_times(BETA)
    after_pilot = package_times(PACKAGE)
    beta_unchanged = before_beta == after_beta
    preserved = before_data == after_data
    first_install = [s for s in before_pilot if "firstInstallTime" in s] == [s for s in after_pilot if "firstInstallTime" in s]
    print(json.dumps({"package": PACKAGE, "installed": True, "data_hash_unchanged": preserved,
        "first_install_unchanged": first_install, "beta_unchanged": beta_unchanged,
        "pilot_version": after_pilot, "beta_version": after_beta}))
    if not (beta_unchanged and preserved and first_install):
        raise RuntimeError("pilot_install_preservation_needs_review")


if __name__ == "__main__":
    main()

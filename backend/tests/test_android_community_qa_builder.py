"""Reject public/tracked QA configuration and outputs before any build starts."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BUILDER = Path(__file__).resolve().parents[2] / "scripts/build-android-community-qa.py"


class CommunityQaBuilderPrivacyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="meteofriul-qa-config-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / "scripts").mkdir()
        (self.root / "frontend").mkdir()
        shutil.copy2(BUILDER, self.root / "scripts/build-android-community-qa.py")
        subprocess.run(["git", "init", "--quiet", str(self.root)], check=True, capture_output=True)
        (self.root / ".gitignore").write_text(".tmp/\nignored-config.json\n", encoding="utf-8")
        self.config = {
            "projectId": "meteofriul-comm-qa-261016",
            "projectNumber": "445478488139",
            "packageName": "com.meteofriul.app.communityqa",
            "appId": "1:445478488139:android:0000000000000000000000",
            "apiKey": "synthetic-not-a-key",
        }

    def config_file(self, name):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.config), encoding="utf-8")
        return path

    def assert_rejected(self, config, output=".tmp/output", expected="must be outside Git"):
        process = subprocess.run(
            [sys.executable, "-B", str(self.root / "scripts/build-android-community-qa.py"),
             "--config", str(config), "--output", str(self.root / output)],
            cwd=self.root, capture_output=True, text=True, timeout=15,
        )
        self.assertNotEqual(process.returncode, 0)
        self.assertIn(expected, process.stderr)
        self.assertFalse((self.root / output).exists())
        self.assertEqual(list((self.root / "frontend").iterdir()), [])

    def test_unignored_configuration_is_rejected_before_build(self):
        self.assert_rejected(self.config_file("public-config.json"))

    def test_tracked_configuration_is_rejected_even_if_ignored(self):
        path = self.config_file("ignored-config.json")
        subprocess.run(["git", "add", "-f", "ignored-config.json"], cwd=self.root, check=True, capture_output=True)
        self.assert_rejected(path)

    def test_unignored_artifact_destination_is_rejected(self):
        self.assert_rejected(self.config_file(".tmp/config.json"), output="public-output")

    def test_google_services_file_cannot_be_reused_as_qa_configuration(self):
        self.assert_rejected(self.config_file(".tmp/google-services.json"), expected="separate private configuration")


if __name__ == "__main__":
    unittest.main()

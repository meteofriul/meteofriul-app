import unittest
from pathlib import Path

from app.services.push_version_policy import (
    android_app_version_allowed,
    parse_min_play_version_code,
    parse_play_version_code,
)


class PushVersionPolicyTests(unittest.TestCase):
    def test_production_api_and_all_notification_writers_share_floor(self):
        backend_root = Path(__file__).resolve().parents[1]
        for name in (
            "api-production-runtime.env.yaml",
            "official-alert-production.env.yaml",
            "local-notice-production.env.yaml",
            "morning-forecast-production.env.yaml",
            "evening-forecast-production.env.yaml",
        ):
            with self.subTest(name=name):
                lines = (backend_root / name).read_text(
                    encoding="utf-8"
                ).splitlines()
                self.assertIn("PUSH_PLAY_BETA_MIN_VERSION_CODE: '300029'", lines)
                self.assertFalse(
                    any(
                        line.startswith("PUSH_PLAY_BETA_ALLOWED_APP_VERSIONS:")
                        for line in lines
                    )
                )

    def test_minimum_code_accepts_current_and_future_releases(self):
        for app_version, expected in (
            ("0.1.11+300028", False),
            ("0.1.12+300029", True),
            ("0.1.13+300030", True),
            ("1.0.0+400000", True),
            ("0.1.12", False),
            ("unknown", False),
            ("0.1.12+not-a-code", False),
            ("0.1.12+2147483648", False),
        ):
            with self.subTest(app_version=app_version):
                self.assertEqual(
                    android_app_version_allowed(
                        app_version,
                        allowed_app_versions=frozenset(),
                        min_app_version_code=300029,
                    ),
                    expected,
                )

    def test_exact_release_policy_remains_available_for_legacy_config(self):
        self.assertTrue(
            android_app_version_allowed(
                "0.1.9+300026",
                allowed_app_versions=frozenset({"0.1.9+300026"}),
                min_app_version_code=None,
            )
        )
        self.assertFalse(
            android_app_version_allowed(
                "0.1.12+300029",
                allowed_app_versions=frozenset({"0.1.9+300026"}),
                min_app_version_code=None,
            )
        )

    def test_invalid_minimum_and_client_versions_fail_closed(self):
        for value in ("0", "-1", "300029.0", "unknown", "2147483648"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_min_play_version_code(value)
        self.assertIsNone(parse_min_play_version_code(""))
        self.assertIsNone(parse_play_version_code("0.1.12+0"))
        self.assertEqual(parse_play_version_code("0.1.12+300029"), 300029)

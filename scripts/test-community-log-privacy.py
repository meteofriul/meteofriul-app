"""Boundary checks for the offline Cloud Logging policy generator."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("community_log_privacy", Path(__file__).with_name("prepare-community-log-privacy.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PrivacyPolicyBoundaryTests(unittest.TestCase):
    def test_scope_has_exact_project_service_and_request_log(self):
        value = module.exclusion("isolated-community-qa", "community-compat-qa")
        self.assertFalse(value["disabled"])
        self.assertEqual(value["filter"].splitlines(), [
            'resource.type="cloud_run_revision"',
            'resource.labels.project_id="isolated-community-qa"',
            'resource.labels.service_name="community-compat-qa"',
            'LOG_ID("run.googleapis.com/requests")',
        ])

    def test_rejects_filter_injection_and_wildcards(self):
        for project, service in [
            ('valid-project" OR true', "community"),
            ("valid-project", 'community" OR true'),
            ("*", "community"), ("valid-project", "*"),
            ("123456789", "community"), ("valid-project", ""),
            ("valid-project", "Community"), ("valid-project", "community/other"),
            ("valid-project", "x" * 64),
        ]:
            with self.subTest(project=project, service=service):
                with self.assertRaises(ValueError):
                    module.exclusion(project, service)

    def test_valid_boundary_names(self):
        for project, service in [("a12345", "a"), ("a" * 30, "a" * 63)]:
            self.assertTrue(module.exclusion(project, service)["filter"])


if __name__ == "__main__":
    unittest.main()

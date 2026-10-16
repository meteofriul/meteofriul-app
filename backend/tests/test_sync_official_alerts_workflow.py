import unittest
from pathlib import Path


WORKFLOW = (
    Path(__file__).resolve().parents[2]
    / ".github"
    / "workflows"
    / "sync-official-alerts.yml"
)


class SyncOfficialAlertsWorkflowContractTests(unittest.TestCase):
    def test_alternative_workflow_is_disabled_by_an_explicit_repository_variable(self):
        content = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn(
            "vars.OFFICIAL_ALERT_SYNC_WORKFLOW_ENABLED == 'true'",
            content,
        )

    def test_play_beta_security_scope_is_exported_without_permissive_defaults(self):
        content = WORKFLOW.read_text(encoding="utf-8")

        required_empty_vars = (
            "PUSH_APP_CHECK_ANDROID_APP_IDS",
            "PUSH_ENROLLMENT_GENERATION",
            "PUSH_PLAY_BETA_ALLOWED_APP_VERSIONS",
        )
        for variable in required_empty_vars:
            with self.subTest(variable=variable):
                self.assertIn(
                    f"{variable}: ${{{{ vars.{variable} || '' }}}}",
                    content,
                )


if __name__ == "__main__":
    unittest.main()

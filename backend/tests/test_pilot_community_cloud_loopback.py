"""No-network owner preview and credential refresh boundaries."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.pilot_community_cloud_loopback import LOOPBACK_CLOUD_KIND, create_loopback_cloud_app
from app.pilot_owner_credentials import PILOT_OWNER, PilotOwnerCredentialUnavailable, PilotOwnerTokenRefresher, create_owner_credentials
from app.repositories.community import CommunityRepositoryUnavailable
from app.repositories.pilot_community import PilotMemoryCommunityRepository
from app.repositories.pilot_community_cloud import PILOT_PROJECT, PilotCloudCommunityRepository
from tests.test_pilot_community import FixtureGeography
from tests.test_pilot_community_cloud import FakeCloud


class LoopbackCloudTests(unittest.TestCase):
    def setUp(self):
        self.cloud = FakeCloud()
        PilotCloudCommunityRepository.seed(firestore_client=self.cloud, storage_client=self.cloud,
                                           state=PilotMemoryCommunityRepository()._snapshot_state())

    def application(self, **changes):
        return create_loopback_cloud_app(**{
            "project": PILOT_PROJECT, "geography": FixtureGeography(),
            "firestore_client": self.cloud, "storage_client": self.cloud, **changes,
        })

    def test_health_identifies_shared_cloud_and_reads_without_writes(self):
        app = self.application()
        self.addCleanup(app.state.community.repository.close)
        client = TestClient(app, base_url="http://127.0.0.1:8783")
        before = self.cloud.uploads, self.cloud.updates
        response = client.get("/api/community/health")
        self.assertEqual(response.json(), {"ok": True, "kind": LOOPBACK_CLOUD_KIND,
                         "storage": "pilot-cloud", "project_id": PILOT_PROJECT, "scope": "IT", "published": False})
        self.assertEqual((self.cloud.uploads, self.cloud.updates), before)
        self.cloud.fail_read = True
        self.assertEqual(client.get("/api/community/health").status_code, 503)
        self.assertEqual((self.cloud.uploads, self.cloud.updates), before)

    def test_local_host_origin_and_mutation_guards_are_preserved(self):
        app = self.application()
        self.addCleanup(app.state.community.repository.close)
        client = TestClient(app, base_url="http://127.0.0.1:8783")
        for headers in ({"host": "evil.example"}, {"origin": "https://evil.example"}):
            self.assertEqual(client.get("/api/community/health", headers=headers).status_code, 403)
        self.assertEqual(client.post("/api/community/reputation", json={}).status_code, 403)
        response = client.post("/api/community/reputation", json={}, headers={"x-meteo-pilot-community": "local-only", "origin": "http://127.0.0.1:5174"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.headers["access-control-allow-origin"], "http://127.0.0.1:5174")

    def test_wrong_project_port_cloud_runtime_and_missing_state_fail_closed(self):
        for change in ({"project": "meteo-friul"}, {"port": 8080}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.application(**change)
        with patch.dict("os.environ", {"K_SERVICE": "public-service"}), self.assertRaises(ValueError):
            self.application()
        self.cloud.pointer = None
        before = self.cloud.uploads, self.cloud.updates
        with self.assertRaises(CommunityRepositoryUnavailable):
            self.application()
        self.assertEqual((self.cloud.uploads, self.cloud.updates), before)


class OwnerCredentialTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.document = {"credential": {"access_token": "fake-secret-access-token", "token_expiry": (self.now + timedelta(minutes=45)).strftime("%Y-%m-%dT%H:%M:%SZ")},
                         "configuration": {"properties": {"core": {"account": PILOT_OWNER, "project": PILOT_PROJECT}}}}
        self.active = PILOT_OWNER
        self.calls = []

    def runner(self, command, **kwargs):
        self.calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout=self.active + "\n" if command[2:4] == ["auth", "list"] else json.dumps(self.document))

    def refresher(self, runner=None):
        return PilotOwnerTokenRefresher(runner=runner or self.runner, sdk_path=Path(__file__), now=lambda: self.now)

    def test_refresh_uses_explicit_owner_project_timeout_and_no_token_arguments(self):
        token, expiry = self.refresher()()
        self.assertEqual(token, "fake-secret-access-token")
        self.assertIsNone(expiry.tzinfo)
        for command, options in self.calls:
            self.assertNotIn(token, repr(command))
            self.assertTrue(options["capture_output"])
            self.assertEqual(options["timeout"], 25)
        self.assertIn(f"--project={PILOT_PROJECT}", self.calls[1][0])
        self.assertIn(f"--account={PILOT_OWNER}", self.calls[1][0])
        self.assertIn("--min-expiry=5m", self.calls[1][0])

    def test_google_auth_refreshes_without_adc_or_token_files(self):
        credentials = create_owner_credentials(refresher=self.refresher())
        self.assertEqual(credentials.token, "fake-secret-access-token")
        self.document["credential"]["access_token"] = "second-fake-token"
        credentials.refresh(None)
        self.assertEqual(credentials.token, "second-fake-token")
        self.assertEqual(len(self.calls), 4)

    def test_wrong_identity_project_impersonation_expiry_and_output_fail_closed(self):
        baseline = deepcopy(self.document)
        for fault in ("active", "account", "project", "impersonation", "expired", "near-expiry", "bad-token", "missing"):
            with self.subTest(fault=fault):
                self.document, self.active = deepcopy(baseline), PILOT_OWNER
                if fault == "active": self.active = "other@example.test"
                elif fault in ("account", "project"): self.document["configuration"]["properties"]["core"][fault] = "wrong"
                elif fault == "impersonation": self.document["configuration"]["properties"]["auth"] = {"impersonate_service_account": "other"}
                elif fault in ("expired", "near-expiry"): self.document["credential"]["token_expiry"] = (self.now + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
                elif fault == "bad-token": self.document["credential"]["access_token"] = "secret\nvalue"
                elif fault == "missing": self.document = {}
                with self.assertRaisesRegex(PilotOwnerCredentialUnavailable, "^pilot_owner_credential_unavailable$"):
                    self.refresher()()

    def test_timeout_failure_and_sdk_overrides_do_not_expose_outputs(self):
        for failure in (subprocess.TimeoutExpired("secret-command", 25, output="secret-token"), RuntimeError("secret-token")):
            def runner(*args, **kwargs): raise failure
            with self.assertRaises(PilotOwnerCredentialUnavailable) as error:
                self.refresher(runner)()
            self.assertNotIn("secret", str(error.exception))
            self.assertTrue(error.exception.__suppress_context__)
        with patch.dict("os.environ", {"CLOUDSDK_AUTH_ACCESS_TOKEN": "secret"}), self.assertRaises(PilotOwnerCredentialUnavailable):
            self.refresher()()


if __name__ == "__main__":
    unittest.main()

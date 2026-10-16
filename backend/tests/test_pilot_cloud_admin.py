from contextlib import redirect_stdout
import hashlib
import io
import json
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools import pilot_cloud_admin as admin


class PilotCloudAdminTests(unittest.TestCase):
    def setUp(self):
        self.digest = "a" * 64
        self.token = "T" * 43
        self.binding = {"version": 1, "client_id_sha256": self.digest, "api_base": admin.API_BASE}
        # Provisioning serializes these four keys in this exact order.
        self.payload = json.dumps({"version": 1, "client_id_sha256": self.digest,
                                   "token": self.token, "api_base": admin.API_BASE}).encode()
        self.firestore = Mock()
        self.registry = self.firestore.collection.return_value.document.return_value

    @staticmethod
    def result(code=0, data=b""):
        return SimpleNamespace(returncode=code, stdout=data, stderr=b"private-device-output")

    def call(self, results):
        with patch.dict("os.environ", {"LOCALAPPDATA": "C:/synthetic-fixture"}), \
             patch.object(admin, "clients", return_value=(self.firestore, Mock())) as clients, \
             patch.object(admin.secrets, "token_urlsafe", return_value=self.token), \
             patch.object(admin.subprocess, "run", side_effect=results) as run:
            output = io.StringIO()
            with redirect_stdout(output):
                admin.enroll("synthetic-serial")
            return output.getvalue(), run, clients

    def valid_results(self):
        return [self.result(data=json.dumps(self.binding).encode()), self.result(data=b"ABSENT"),
                self.result(), self.result(data=self.payload)]

    def test_exact_native_shape_exclusive_private_write_and_no_token_output(self):
        output, run, _ = self.call(self.valid_results())
        self.assertTrue(json.loads(output)["enrolled"])
        self.assertNotIn(self.token, output)
        self.firestore.collection.assert_called_once_with("pilot_community_installations")
        self.firestore.collection.return_value.document.assert_called_once_with(hashlib.sha256(self.token.encode()).hexdigest())
        created = self.registry.create.call_args.args[0]
        self.assertEqual(created["client_id_sha256"], self.digest)
        self.assertEqual(created["project"], admin.PROJECT)
        write = run.call_args_list[2]
        self.assertEqual(write.kwargs["input"], self.payload)
        self.assertIn("set -C", write.args[0][-1])
        self.assertIn("test ! -L", write.args[0][-1])
        self.assertNotIn(self.token, str(write.args[0]))
        self.assertIn("test -f", run.call_args_list[0].args[0][-1])
        self.assertIn("head -c 4097", run.call_args_list[0].args[0][-1])
        self.assertFalse(run.call_args_list[0].args[0][-1].startswith("'"))
        self.assertTrue(run.call_args_list[1].args[0][-1].startswith("'"))
        self.registry.update.assert_not_called()

    def test_invalid_binding_or_file_probe_never_creates_registry(self):
        invalid = [{**self.binding, "version": True}, {**self.binding, "version": 2},
                   {**self.binding, "api_base": "https://meteo-friul.invalid/api"},
                   {**self.binding, "client_id_sha256": None}]
        for binding in invalid:
            with self.subTest(binding=binding):
                with self.assertRaisesRegex(RuntimeError, "pilot_binding_missing_or_invalid"):
                    self.call([self.result(data=json.dumps(binding).encode())])
        for code in (0, 1, 2, 3, 255):
            with self.subTest(code=code):
                with self.assertRaises(RuntimeError):
                    self.call([self.result(data=json.dumps(self.binding).encode()), self.result(code)])
        with self.assertRaisesRegex(RuntimeError, "already_provisioned"):
            self.call([self.result(data=json.dumps(self.binding).encode()), self.result(data=b"PRESENT")])
        self.registry.create.assert_not_called()

    def test_zero_status_shell_error_or_non_object_never_becomes_private_file(self):
        for output in (b"sh: test -d no_backup: not found\n", b"run-as: Package unavailable", b"[]"):
            with self.subTest(output_kind=output[:6]):
                with self.assertRaisesRegex(RuntimeError, "pilot_private_device_file_unavailable"):
                    self.call([self.result(data=output)])
        self.registry.create.assert_not_called()

    def test_write_failure_readback_failure_and_transport_exception_all_revoke(self):
        failures = [
            [self.result(1)],
            [self.result(), self.result(1)],
            [self.result(), self.result(data=b"wrong-payload")],
            [subprocess.TimeoutExpired("synthetic", 30, output=self.token.encode())],
            [self.result(), subprocess.TimeoutExpired("synthetic", 30, output=self.token.encode())],
        ]
        for failure in failures:
            with self.subTest(failure=type(failure[-1]).__name__):
                self.registry.reset_mock()
                with self.assertRaisesRegex(RuntimeError, "pilot_provision_failed_enrollment_revoked") as rejected:
                    self.call([self.result(data=json.dumps(self.binding).encode()), self.result(data=b"ABSENT"), *failure])
                self.registry.update.assert_called_once_with({"active": False}, timeout=15, retry=None)
                self.assertNotIn(self.token, str(rejected.exception))

    def test_uncertain_registry_create_also_attempts_revocation(self):
        self.registry.create.side_effect = TimeoutError("private-cloud-diagnostic")
        with self.assertRaisesRegex(RuntimeError, "pilot_provision_failed_enrollment_revoked"):
            self.call(self.valid_results()[:2])
        self.registry.update.assert_called_once_with({"active": False}, timeout=15, retry=None)

    def test_failed_revocation_has_safe_actionable_error(self):
        self.registry.update.side_effect = OSError(self.token)
        with self.assertRaisesRegex(RuntimeError, "revocation_unconfirmed") as rejected:
            self.call(self.valid_results()[:2] + [self.result(1)])
        self.assertNotIn(self.token, str(rejected.exception))


if __name__ == "__main__":
    unittest.main()

"""Offline checks for bounded pilot logs; no cloud SDK or credentials required."""
from contextlib import redirect_stdout
import io
import json
import unittest
from unittest.mock import patch

from local_pipeline.operational_diagnostics import attach_error_fields, emit, error_fields, phase


class OperationalDiagnosticsTests(unittest.TestCase):
    def test_tolerance_denominators_and_guard_reasons_survive_safe_logging(self):
        fields = {f"quality_tolerance_{metric}_{field}": 15
                  for field in ("precipitation", "rain", "snow") for metric in ("expected", "verified")}
        fields.update({f"quality_guard_{field}_{reason}": 3
                       for field in ("precipitation", "rain", "snow")
                       for reason in ("resolution_metadata_missing", "resolution_budget_exceeded", "missing_or_invalid_accumulation")})
        output = io.StringIO()
        with redirect_stdout(output):
            emit("source_quality", source_run_id="20261019T000000Z", **fields, quality_private_token="secret")
        record = json.loads(output.getvalue())
        self.assertEqual({key: record.get(key) for key in fields}, fields)
        self.assertEqual(record['source_run_id'], '20261019T000000Z')
        self.assertNotIn('secret', output.getvalue())

    def test_phase_records_success_and_resets_context(self):
        output = io.StringIO()
        with redirect_stdout(output):
            with phase("icon_validation", provider="icon", source_run_id="20260908T000000Z"):
                emit("validation_result", validated_count=215, validation_status="passed")
            emit("outside")
        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual([row["event"] for row in rows],
                         ["phase_started", "validation_result", "phase_completed", "outside"])
        self.assertEqual(rows[1]["validated_count"], 215)
        self.assertEqual(rows[2]["stage"], "icon_validation")
        self.assertNotIn("stage", rows[-1])

    def test_innermost_failed_stage_survives_outer_context_and_system_exit(self):
        output = io.StringIO()
        error = SystemExit("Authorization Bearer secret https://host/file?token=secret")
        with redirect_stdout(output), self.assertRaises(SystemExit) as caught:
            with phase("cloud_job", provider="cams"):
                with phase("constraints_validation", run_date="2026-09-08"):
                    raise error
        self.assertIs(caught.exception, error)
        fields = error_fields(caught.exception)
        self.assertEqual(fields["stage"], "constraints_validation")
        self.assertEqual(fields["error_type"], "SystemExit")
        self.assertNotIn("secret", output.getvalue())
        self.assertNotIn("host", output.getvalue())

    def test_errors_never_call_untrusted_str_and_log_only_controlled_message(self):
        class UntrustedError(Exception):
            def __str__(self):
                raise AssertionError("must not serialize remote error")
        fields = error_fields(UntrustedError("secret"))
        self.assertEqual(fields["error_type"], "UntrustedError")
        self.assertNotIn("secret", json.dumps(fields))
        controlled = error_fields(RuntimeError("latest disappeared after CAS"))
        self.assertEqual(controlled["error_summary"], "latest disappeared after CAS")

    def test_sensitive_unknown_fields_urls_absolute_paths_and_nested_data_are_dropped(self):
        output = io.StringIO()
        with redirect_stdout(output):
            emit("safe", token="secret", authorization="Bearer secret", body={"secret": 1},
                 object_key="https://host/file?token=secret", provider="x\nsecret",
                 failure_file="C:/private/secret.txt", metadata_sha256="a" * 64,
                 expected_count=215, status={"secret": 1})
        record = json.loads(output.getvalue())
        self.assertNotIn("secret", output.getvalue())
        self.assertNotIn("object_key", record)
        self.assertEqual(record["expected_count"], 215)
        self.assertEqual(record["metadata_sha256"], "a" * 64)

    def test_icon_recovery_failures_keep_readable_controlled_reasons(self):
        for message in (
            "stored manifest differs from publication intent",
            "ICON checkpoint cannot be authenticated",
            "ICON checkpoint storage integrity failed",
            "invalid ICON acquisition claim",
            "remote publication identity conflict",
            "published_at cannot regress",
        ):
            with self.subTest(message=message):
                fields = error_fields(attach_error_fields(RuntimeError(message),
                    stage="publication_recovery_validation", municipality_code="093033",
                    object_key="weather/v1/icon2i/runs/20260908T000000Z/municipalities/093033.json"))
                self.assertEqual(fields["error_summary"], message)
                self.assertEqual(fields["municipality_code"], "093033")
                self.assertEqual(fields["stage"], "publication_recovery_validation")

    def test_icon_field_checkpoint_reports_safe_inner_location_and_reason(self):
        import run_pilot as pilot
        from test_run_pilot import snapshot_fixture

        field = "T_2M"
        for key, value, reason in (
            ("unexpected_diagnostic", 1, "Checkpoint metadata is invalid"),
            ("packingError", -0.001, "Checkpoint packing error is invalid"),
        ):
            with self.subTest(key=key):
                fixture = snapshot_fixture()
                data = fixture["raw"][field]
                data["metadata"][0][key] = value
                record = pilot._with_checkpoint_integrity(dict(
                    schema_version=pilot.CHECKPOINT_SCHEMA_VERSION,
                    kind="icon_extracted_field_checkpoint", intent_sha256="d" * 64,
                    run=fixture["run"], field=field, url=data["url"],
                    grid_hash=fixture["grid_hash"], grid_points=fixture["grid_points"], data=data))
                output = io.StringIO()
                with redirect_stdout(output), self.assertRaises(ValueError):
                    with phase("acquisition", provider="icon"):
                        pilot._validate_field_checkpoint(record, intent_sha="d" * 64,
                            field=field, run=fixture["run"], url=data["url"], points=fixture["points"])
                # assertRaises clears exception tracebacks; inspect the actual
                # emitted record, captured while the original trace is intact.
                fields = next(json.loads(line) for line in output.getvalue().splitlines()
                              if json.loads(line)["event"] == "phase_failed")
                self.assertEqual(fields["error_summary"], reason)
                self.assertEqual(fields["failure_file"], "run_pilot.py")
                self.assertEqual(fields["failure_function"], "_validate_field_checkpoint")
                self.assertGreater(fields["failure_line"], 0)
                self.assertEqual(fields["stage"], "acquisition")
                self.assertNotIn(data["url"], output.getvalue())

    def test_safe_inner_cause_is_not_lost_when_publication_wraps_it(self):
        try:
            try:
                raise attach_error_fields(RuntimeError("secret"), error_type="ServiceUnavailable",
                                          http_status=503, operation="upload", retryable=True,
                                          error_summary="storage service temporarily unavailable")
            except RuntimeError as inner:
                raise ValueError("secret outer") from inner
        except ValueError as outer:
            fields = error_fields(outer)
        self.assertEqual(fields["error_type"], "ValueError")
        self.assertEqual(fields["cause_type"], "ServiceUnavailable")
        self.assertEqual(fields["http_status"], 503)
        self.assertNotIn("secret", json.dumps(fields))

    def test_logging_failure_does_not_change_success_or_replace_original_error(self):
        original = RuntimeError("original")
        with patch("builtins.print", side_effect=BrokenPipeError("closed")):
            with phase("success"):
                pass
            with self.assertRaises(RuntimeError) as caught:
                with phase("failure"):
                    raise original
        self.assertIs(caught.exception, original)

    def test_unknown_inner_run_does_not_erase_verified_outer_run_context(self):
        with redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError) as caught:
            with phase("outer", source_run_id="20260908T000000Z"):
                with phase("inner", source_run_id=None):
                    raise RuntimeError("secret")
        self.assertEqual(error_fields(caught.exception)["source_run_id"], "20260908T000000Z")


if __name__ == "__main__":
    unittest.main()

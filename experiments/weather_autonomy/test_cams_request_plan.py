from copy import deepcopy
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cams_request_plan as cams
from local_pipeline.operational_diagnostics import error_fields
from cams_test_fixtures import (
    FakePublicSession,
    TEST_DATE,
    public_metadata_documents,
    valid_evidence,
    valid_plan,
    write_valid_plan,
)


def validate_documents(documents, *, run_date=TEST_DATE, area=cams.DEFAULT_AREA):
    return cams.validate_public_metadata(
        run_date,
        area=area,
        catalogue=documents["catalogue"],
        catalogue_url=cams.CATALOGUE_URL,
        catalogue_sha256=documents["catalogue_sha256"],
        form=documents["form"],
        form_url=documents["form_url"],
        form_sha256=documents["form_sha256"],
        constraints=documents["constraints"],
        constraints_url=documents["constraints_url"],
        constraints_sha256=documents["constraints_sha256"],
        checked_at_utc=f"{run_date}T08:00:00Z",
    )


class PublicMetadataTests(unittest.TestCase):
    def test_dynamic_discovery_uses_three_anonymous_direct_gets(self):
        session = FakePublicSession()
        evidence = cams.fetch_verified_metadata(TEST_DATE, session=session)
        self.assertFalse(session.trust_env)
        self.assertTrue(session.cookies.cleared)
        self.assertEqual(
            [call[0] for call in session.calls],
            [cams.CATALOGUE_URL, session.documents["form_url"], session.documents["constraints_url"]],
        )
        for _, kwargs in session.calls:
            self.assertFalse(kwargs["allow_redirects"])
            self.assertIsNone(kwargs["auth"])
            self.assertEqual(kwargs["headers"]["Accept"], "application/json")
            self.assertNotIn("Authorization", kwargs["headers"])
        self.assertEqual(evidence["catalogue_sanity"]["status"], "available")
        for name in ("catalogue", "form", "constraints"):
            self.assertRegex(evidence["documents"][name]["sha256"], r"^[0-9a-f]{64}$")

    def test_catalogue_with_only_zero_to_72_fails_closed(self):
        for status in ("available", "down"):
            with self.subTest(status=status):
                documents = public_metadata_documents(leads=range(73))
                documents["catalogue"]["cads:sanity_check"]["status"] = status
                with self.assertRaisesRegex(cams.PublicMetadataUnavailable, r"73/97.*maximum=72"):
                    validate_documents(documents)

    def test_catalogue_identity_sanity_and_licence_are_exact(self):
        mutations = (
            ("id", "other"),
            ("license", "other"),
            ("sci:doi", "other"),
        )
        for key, value in mutations:
            with self.subTest(key=key):
                documents = public_metadata_documents()
                documents["catalogue"][key] = value
                with self.assertRaises(cams.PublicMetadataError):
                    validate_documents(documents)
        documents = public_metadata_documents()
        documents["catalogue"]["cads:sanity_check"]["status"] = "unavailable"
        with self.assertRaises(cams.PublicMetadataUnavailable) as raised:
            validate_documents(documents)
        fields = error_fields(raised.exception)
        self.assertEqual(fields["reason_code"], "catalogue_sanity_unavailable")
        self.assertEqual(
            fields["error_summary"],
            "CAMS catalogue sanity status is not available",
        )

    def test_down_catalogue_can_build_plan_only_with_valid_form_and_constraints(self):
        documents = public_metadata_documents()
        documents["catalogue"]["cads:sanity_check"]["status"] = "down"
        documents["catalogue_raw"] = json.dumps(
            documents["catalogue"], ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        session = FakePublicSession(documents)
        output = io.StringIO()
        with redirect_stdout(output):
            evidence = cams.fetch_verified_metadata(TEST_DATE, session=session)
        plan = cams.build_request_plan(TEST_DATE, metadata_evidence=evidence)
        self.assertEqual(len(session.calls), 3)
        self.assertEqual(evidence["catalogue_sanity"]["status"], "down")
        self.assertEqual(plan["counts"]["requested_fields"], 2716)
        self.assertTrue(cams.encode_request_plan(plan))
        records = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(
            [record["reason_code"] for record in records],
            ["constraints_validated", "catalogue_sanity_down_constraints_validated"],
        )
        self.assertEqual(records[0]["validation_status"], "passed")
        self.assertEqual(records[1]["validation_status"], "passed")
        self.assertEqual(records[1]["severity"], "WARNING")

    def test_explicit_catalogue_disable_still_fails_closed(self):
        documents = public_metadata_documents()
        documents["catalogue"]["cads:sanity_check"]["status"] = "down"
        documents["catalogue"]["cads:disabled_reason"] = "maintenance"
        with self.assertRaises(cams.PublicMetadataUnavailable) as raised:
            validate_documents(documents)
        fields = error_fields(raised.exception)
        self.assertEqual(fields["reason_code"], "catalogue_disabled")
        self.assertEqual(fields["error_summary"], "CAMS catalogue is explicitly disabled")

    def test_links_must_be_unique_content_addressed_approved_https_urls(self):
        bad_urls = (
            "http://object-store.os-api.cci2.ecmwf.int/cci2-prod-catalogue/resources/"
            + cams.DATASET + "/form_" + "0" * 64 + ".json",
            "https://evil.example/cci2-prod-catalogue/resources/" + cams.DATASET
            + "/form_" + "0" * 64 + ".json",
            "https://user@object-store.os-api.cci2.ecmwf.int/cci2-prod-catalogue/resources/"
            + cams.DATASET + "/form_" + "0" * 64 + ".json",
            "https://object-store.os-api.cci2.ecmwf.int/other/form_" + "0" * 64 + ".json",
        )
        for url in bad_urls:
            with self.subTest(url=url):
                documents = public_metadata_documents()
                next(link for link in documents["catalogue"]["links"] if link["rel"] == "form")["href"] = url
                documents["form_url"] = url
                with self.assertRaises(cams.PublicMetadataError):
                    validate_documents(documents)
        documents = public_metadata_documents()
        form_link = next(link for link in documents["catalogue"]["links"] if link["rel"] == "form")
        documents["catalogue"]["links"].append(dict(form_link))
        with self.assertRaises(cams.PublicMetadataError):
            validate_documents(documents)

    def test_form_requires_exact_variables_leads_and_selection_options(self):
        for field, mutation in (
            ("variable", lambda values: values.pop()),
            ("variable", lambda values: values.append("extra")),
            ("leadtime_hour", lambda values: values.pop()),
            ("model", lambda values: values.remove("ensemble")),
            ("level", lambda values: values.remove("0")),
            ("type", lambda values: values.remove("forecast")),
            ("time", lambda values: values.remove("00:00")),
        ):
            with self.subTest(field=field):
                documents = public_metadata_documents()
                values = next(row for row in documents["form"] if row["name"] == field)["details"]["values"]
                mutation(values)
                with self.assertRaises(cams.PublicMetadataError):
                    validate_documents(documents)

    def test_constraints_require_one_compatible_28_by_97_surface_ensemble_row(self):
        for key, value in (
            ("model", ["chimere"]),
            ("level", ["50"]),
            ("type", ["analysis"]),
            ("time", ["01:00"]),
            ("variable", list(cams.EXPECTED_VARIABLE_IDS[:-1])),
        ):
            with self.subTest(key=key):
                documents = public_metadata_documents()
                documents["constraints"][0][key] = value
                with self.assertRaises(cams.PublicMetadataUnavailable):
                    validate_documents(documents)
        documents = public_metadata_documents()
        documents["constraints"].append(deepcopy(documents["constraints"][0]))
        with self.assertRaises(cams.PublicMetadataUnavailable):
            validate_documents(documents)

    def test_constraints_treat_row_values_as_selectable_options(self):
        documents = public_metadata_documents()
        row = documents["constraints"][0]
        row["model"] = [
            "ensemble",
            "chimere",
            "dehm",
            "emep",
            "euradim",
            "gemaq",
            "lotos",
            "match",
            "minni",
            "monarch",
            "mocage",
            "silam",
        ]
        row["level"] = ["0", "50"]
        row["type"] = ["analysis", "forecast"]
        row["time"] = ["00:00", "01:00"]
        evidence = validate_documents(documents)
        selection = evidence["validated_selection"]
        self.assertEqual(["ensemble"], selection["model"])
        self.assertEqual(["0"], selection["level"])
        self.assertEqual(["forecast"], selection["type"])
        self.assertEqual(["00:00"], selection["time"])
        self.assertEqual(list(cams.EXPECTED_VARIABLE_IDS), selection["variable"])

    def test_only_one_row_may_project_to_the_requested_selection(self):
        documents = public_metadata_documents()
        broader = deepcopy(documents["constraints"][0])
        broader["model"].append("chimere")
        documents["constraints"].append(broader)
        with self.assertRaises(cams.PublicMetadataUnavailable):
            validate_documents(documents)

    def test_date_must_be_covered_by_catalogue_form_and_constraints(self):
        documents = public_metadata_documents()
        documents["constraints"][0]["date"] = ["2026-09-03/2026-09-04"]
        evidence = validate_documents(documents)
        self.assertEqual(evidence["run_date"], TEST_DATE)
        documents["constraints"][0]["date"] = ["2026-09-03"]
        with self.assertRaises(cams.PublicMetadataUnavailable):
            validate_documents(documents)

    def test_response_byte_hash_must_match_content_addressed_filename(self):
        documents = public_metadata_documents()
        documents["form_sha256"] = "0" * 64
        with self.assertRaisesRegex(cams.PublicMetadataError, "URL hash"):
            validate_documents(documents)


class PartitionedConstraintsTests(unittest.TestCase):
    def documents(self):
        documents = public_metadata_documents()
        base = documents["constraints"][0]
        air, pollen = deepcopy(base), deepcopy(base)
        air["variable"] = [v for v in base["variable"] if not v.endswith("_pollen")]
        pollen["variable"] = [v for v in base["variable"] if v.endswith("_pollen")]
        pollen["date"] = ["2025-05-04/" + TEST_DATE]
        documents["constraints"] = [air, pollen]
        return documents

    def test_air_and_pollen_partitions_produce_exact_original_request(self):
        documents = self.documents()
        evidence = validate_documents(documents)
        plan = cams.build_request_plan(TEST_DATE, metadata_evidence=evidence)
        self.assertEqual(plan["request_groups"], valid_plan()["request_groups"])
        self.assertEqual(plan["counts"]["requested_fields"], 28 * 97)
        self.assertEqual(evidence["validated_selection"]["date"], [TEST_DATE])
        self.assertTrue(cams.encode_request_plan(plan))
        documents["constraints"].reverse()
        self.assertEqual(validate_documents(documents), evidence)

    def test_missing_air_or_pollen_variable_is_rejected(self):
        for index in (0, 1):
            with self.subTest(index=index):
                documents = self.documents()
                documents["constraints"][index]["variable"].pop()
                with self.assertRaises(cams.PublicMetadataUnavailable) as raised:
                    validate_documents(documents)
                self.assertEqual(error_fields(raised.exception)["error_summary"],
                                 "CAMS constraints do not contain unambiguous complete surface ensemble coverage")

    def test_partitions_cannot_borrow_different_model_date_or_level(self):
        for key, value in (("model", ["chimere"]), ("date", ["2026-09-03"]),
                           ("level", ["50"]), ("type", ["analysis"]), ("time", ["01:00"])):
            with self.subTest(key=key):
                documents = self.documents()
                documents["constraints"][1][key] = value
                with self.assertRaises(cams.PublicMetadataUnavailable):
                    validate_documents(documents)

    def test_every_partition_requires_all_97_leads(self):
        for index in (0, 1):
            with self.subTest(index=index):
                documents = self.documents()
                documents["constraints"][index]["leadtime_hour"].remove("48")
                with self.assertRaises(cams.PublicMetadataUnavailable) as raised:
                    validate_documents(documents)
                self.assertEqual(error_fields(raised.exception)["reason_code"], "constraints_incomplete_leads")

    def test_overlapping_variable_partitions_remain_ambiguous(self):
        documents = self.documents()
        documents["constraints"][0]["variable"].append(documents["constraints"][1]["variable"][0])
        with self.assertRaises(cams.PublicMetadataUnavailable) as raised:
            validate_documents(documents)
        self.assertEqual(error_fields(raised.exception)["reason_code"], "constraints_multiple_compatible_rows")

    def test_complete_row_plus_partial_duplicate_remains_ambiguous(self):
        documents = self.documents()
        documents["constraints"].append(public_metadata_documents()["constraints"][0])
        with self.assertRaises(cams.PublicMetadataUnavailable):
            validate_documents(documents)

    def test_malformed_partition_is_rejected(self):
        documents = self.documents()
        documents["constraints"][1]["variable"].append(documents["constraints"][1]["variable"][0])
        with self.assertRaises(cams.PublicMetadataError):
            validate_documents(documents)

    def test_unrelated_model_rows_do_not_create_false_overlap(self):
        documents = self.documents()
        other = deepcopy(documents["constraints"][0])
        other["model"] = ["chimere"]
        documents["constraints"].append(other)
        evidence = validate_documents(documents)
        self.assertEqual(len(evidence["validated_selection"]["variable"]), 28)


class PublicMetadataDiagnosticTests(unittest.TestCase):
    def rejected(self, documents, error_type=cams.PublicMetadataUnavailable):
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(error_type) as failed:
            validate_documents(documents)
        records = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["stage"], "constraints_validation")
        self.assertEqual(record["provider"], "cams")
        self.assertEqual(record["run_date"], TEST_DATE)
        self.assertEqual(record["validation_status"], "failed")
        self.assertEqual(record["metadata_sha256"], documents["constraints_sha256"])
        self.assertEqual(record["error_type"], error_type.__name__)
        self.assertEqual(failed.exception.weather_diagnostics["reason_code"], record["reason_code"])
        return record

    def test_no_date_and_multiple_candidates_have_distinct_diagnostics(self):
        documents = public_metadata_documents()
        documents["constraints"][0]["date"] = ["2026-09-03"]
        record = self.rejected(documents)
        self.assertEqual(record["reason_code"], "constraints_no_date_rows")
        self.assertEqual(record["constraints_rows"], 1)
        self.assertEqual(record["date_rows"], 0)
        self.assertEqual(record["compatible_rows"], 0)

        documents = public_metadata_documents()
        documents["constraints"].append(deepcopy(documents["constraints"][0]))
        record = self.rejected(documents)
        self.assertEqual(record["reason_code"], "constraints_multiple_compatible_rows")
        self.assertEqual(record["date_rows"], 2)
        self.assertEqual(record["compatible_rows"], 2)

    def test_each_missing_selection_is_counted_without_exposing_values(self):
        for key in ("model", "level", "type", "time", "variable"):
            with self.subTest(key=key):
                documents = public_metadata_documents()
                documents["constraints"][0][key] = ["https://provider.invalid/private?token=do-not-log"]
                record = self.rejected(documents)
                self.assertEqual(record["reason_code"], "constraints_no_compatible_rows")
                self.assertEqual(record["date_rows"], 1)
                self.assertEqual(record["compatible_rows"], 0)
                self.assertEqual(record[f"missing_{key}_rows"], 1)
                self.assertNotIn("provider.invalid", json.dumps(record))
                self.assertNotIn("do-not-log", json.dumps(record))
                if key == "variable":
                    self.assertEqual(record["missing_variable_count"], 28)

    def test_incomplete_horizon_reports_only_requested_lead_coverage(self):
        record = self.rejected(public_metadata_documents(leads=range(25)))
        self.assertEqual(record["reason_code"], "constraints_incomplete_leads")
        self.assertEqual(record["compatible_rows"], 1)
        self.assertEqual(record["leadcount"], 25)
        self.assertEqual(record["maxlead"], 24)
        self.assertEqual(record["missing_lead_count"], 72)
        record = self.rejected(public_metadata_documents(leads=[]))
        self.assertEqual(record["leadcount"], 0)
        self.assertEqual(record["missing_lead_count"], 97)
        self.assertNotIn("maxlead", record)

    def test_malformed_constraints_remain_errors_not_provider_pending(self):
        documents = public_metadata_documents()
        documents["constraints"][0]["model"] = "ensemble"
        record = self.rejected(documents, cams.PublicMetadataError)
        self.assertEqual(record["reason_code"], "constraints_malformed_selections")
        self.assertEqual(record["severity"], "ERROR")

    def test_success_emits_validation_summary_without_changing_evidence(self):
        documents = public_metadata_documents()
        output = io.StringIO()
        with redirect_stdout(output):
            evidence = validate_documents(documents)
        record = json.loads(output.getvalue())
        self.assertEqual(record["validation_status"], "passed")
        self.assertEqual(record["reason_code"], "constraints_validated")
        self.assertEqual(record["metadata_sha256"], documents["constraints_sha256"])
        self.assertEqual(record["compatible_rows"], 1)
        self.assertEqual(record["leadcount"], 97)
        self.assertEqual(record["maxlead"], 96)
        self.assertEqual(evidence["validated_selection"], documents["constraints"][0])

    def test_cli_preserves_typed_diagnostic_through_argparse_exit(self):
        documents = public_metadata_documents(leads=range(25))
        with tempfile.TemporaryDirectory() as temporary:
            output_path = Path(temporary) / "plan.json"
            output = io.StringIO()
            with patch.object(cams, "fetch_verified_metadata", side_effect=lambda *args, **kwargs: validate_documents(documents)), \
                    redirect_stdout(output), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stopped:
                cams.main(["--date", TEST_DATE, "--output", str(output_path)])
            self.assertEqual(stopped.exception.code, 2)
            self.assertFalse(output_path.exists())
            self.assertEqual(stopped.exception.weather_diagnostics["error_type"], "PublicMetadataUnavailable")
            self.assertEqual(stopped.exception.weather_diagnostics["reason_code"], "constraints_incomplete_leads")
            self.assertEqual(stopped.exception.weather_diagnostics["leadcount"], 25)
            self.assertEqual(len(output.getvalue().splitlines()), 1)


class RequestPlanTests(unittest.TestCase):
    def test_library_entry_point_builds_the_same_verified_plan_without_retrieval(self):
        with patch.object(cams, 'fetch_verified_metadata', return_value=valid_evidence()) as fetch:
            plan = cams.create_verified_request_plan(TEST_DATE)
        fetch.assert_called_once_with(TEST_DATE, area=cams.DEFAULT_AREA)
        self.assertEqual(plan, valid_plan())
        self.assertFalse(plan['retrieval_performed'])
        self.assertEqual(cams.encode_request_plan(plan), cams.encode_request_plan(valid_plan()))

    def test_library_entry_point_preserves_unavailable_and_invalid_exceptions(self):
        for error in (cams.PublicMetadataUnavailable('not ready'), cams.PublicMetadataError('invalid')):
            with self.subTest(error=type(error).__name__), \
                 patch.object(cams, 'fetch_verified_metadata', side_effect=error), \
                 self.assertRaises(type(error)) as raised:
                cams.create_verified_request_plan(TEST_DATE)
            self.assertIs(raised.exception, error)

    def test_plan_has_exact_request_and_provenance(self):
        plan = valid_plan()
        request = plan["request_groups"][0]["request"]
        self.assertEqual(plan["run_date"], TEST_DATE)
        self.assertEqual(set(request["variable"]), set(cams.EXPECTED_VARIABLE_IDS))
        self.assertEqual(request["leadtime_hour"], list(cams.EXPECTED_LEADS))
        self.assertEqual(request["model"], ["ensemble"])
        self.assertEqual(request["level"], ["0"])
        self.assertEqual(request["type"], ["forecast"])
        self.assertEqual(request["time"], ["00:00"])
        self.assertEqual(request["date"], [f"{TEST_DATE}/{TEST_DATE}"])
        self.assertEqual(plan["counts"]["requested_fields"], 2716)
        self.assertEqual(plan["counts"]["pollen"], 6)
        self.assertEqual(plan["licence"]["catalogue_identifier"], "CC-BY-4.0")
        cams.validate_request_plan(plan)

    def test_plan_requires_explicit_matching_evidence_and_bounded_area(self):
        with self.assertRaises(TypeError):
            cams.build_request_plan(TEST_DATE)
        for area in ((47.3, 12.2, 45.5, 14.0), (46.7, 11.7, 45.5, 14.0), (46.7, 12.2, 46.7, 14.0)):
            with self.subTest(area=area), self.assertRaises(cams.PublicMetadataError):
                cams.build_request_plan(TEST_DATE, metadata_evidence=valid_evidence(), area=area)

    def test_any_plan_mutation_is_rejected(self):
        mutations = []
        plan = valid_plan()
        bad = deepcopy(plan); bad["run_date"] = "2026-09-05"; mutations.append(bad)
        bad = deepcopy(plan); bad["request_groups"][0]["request"]["leadtime_hour"].pop(); mutations.append(bad)
        bad = deepcopy(plan); bad["metadata_evidence"]["documents"]["constraints"]["sha256"] = "0" * 64; mutations.append(bad)
        bad = deepcopy(plan); bad["licence"]["url"] = "https://example.invalid"; mutations.append(bad)
        bad = deepcopy(plan); bad["extra"] = True; mutations.append(bad)
        for bad in mutations:
            with self.subTest(), self.assertRaises(cams.PublicMetadataError):
                cams.validate_request_plan(bad)

    def test_loader_hashes_exact_bytes_and_rejects_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as temporary:
            path, plan, raw, digest = write_valid_plan(temporary)
            loaded, loaded_raw, loaded_digest = cams.load_verified_request_plan(path)
            self.assertEqual(loaded, plan)
            self.assertEqual(loaded_raw, raw)
            self.assertEqual(loaded_digest, digest)
            duplicate = Path(temporary) / "duplicate.json"
            duplicate.write_bytes(b'{"schema_version":2,"schema_version":2}')
            with self.assertRaises(cams.PublicMetadataError):
                cams.load_verified_request_plan(duplicate)

    def test_cli_requires_explicit_date_and_new_output_before_network(self):
        with patch.object(cams, "fetch_verified_metadata") as fetch:
            with self.assertRaises(SystemExit):
                cams.main([])
            fetch.assert_not_called()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "existing.json"
            output.write_text("existing", encoding="utf-8")
            with patch.object(cams, "fetch_verified_metadata") as fetch:
                with self.assertRaises(SystemExit):
                    cams.main(["--date", TEST_DATE, "--output", str(output)])
                fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()

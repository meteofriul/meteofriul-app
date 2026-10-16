from __future__ import annotations

import hashlib
import json
from pathlib import Path
import socket
import tempfile
import unittest

from local_pipeline.contract_publisher import ContractPublicationResult
from local_pipeline.contract_v1 import CAMS_POLLEN_PROVIDER, CAMS_PROVIDER, ICON_PROVIDER
from local_pipeline.sqlite_object_store import SQLiteObjectStore
from run_compressed_schedule import (
    CompressedScheduleError,
    ContinuityMonitor,
    EVIDENCE_FILES,
    FailBeforeLatestCasStore,
    InjectedIconCrash,
    LoopbackDataPlane,
    LoopbackOnlyNetworkGuard,
    RunJournal,
    SourceInputs,
    _manifest,
    _provider_bundle,
    run_sequence,
    stage_inputs,
    verify_sources_unchanged,
)


def _publication(
    provider: str,
    run_id: str,
    *,
    idempotent: bool = False,
    updated: bool = True,
    reused: int = 0,
    manifest_reused: bool = False,
) -> ContractPublicationResult:
    return ContractPublicationResult(
        provider=provider,
        source_run_id=run_id,
        payload_keys=tuple(f"key-{index}" for index in range(215)),
        manifest_key="manifest",
        latest_key="latest",
        latest_etag='"etag"',
        reused_payload_count=reused,
        manifest_reused=manifest_reused,
        idempotent=idempotent,
        latest_updated=updated,
    )


class StagingTests(unittest.TestCase):
    def test_staging_copies_only_allowlisted_evidence_and_never_overwrites(self):
        with tempfile.TemporaryDirectory(prefix="compressed-schedule-test-") as temporary:
            root = Path(temporary)
            sources = root / "sources"
            sources.mkdir()
            evidence = sources / "evidence"
            evidence.mkdir()

            artifact_paths = {}
            for name in (
                "icon-first-payload",
                "icon-first-report",
                "icon-second-payload",
                "icon-second-report",
                "cams-first-payload",
                "cams-first-report",
                "cams-second-payload",
                "cams-second-report",
            ):
                path = sources / f"{name}.json"
                path.write_bytes((name + "\n").encode("ascii"))
                artifact_paths[name] = path
            for name in EVIDENCE_FILES:
                (evidence / name).write_bytes((name + "\n").encode("ascii"))
            (evidence / ".cdsapirc").write_text("must-not-be-copied", encoding="utf-8")

            inputs = SourceInputs(
                icon_first_payload=artifact_paths["icon-first-payload"],
                icon_first_report=artifact_paths["icon-first-report"],
                icon_second_payload=artifact_paths["icon-second-payload"],
                icon_second_report=artifact_paths["icon-second-report"],
                cams_first_payload=artifact_paths["cams-first-payload"],
                cams_first_report=artifact_paths["cams-first-report"],
                cams_second_payload=artifact_paths["cams-second-payload"],
                cams_second_report=artifact_paths["cams-second-report"],
                cams_second_evidence_directory=evidence,
            )
            work = root / "run"
            staged, records = stage_inputs(inputs, work)

            self.assertEqual(14, len(records))
            self.assertFalse((staged.cams_second_evidence_directory / ".cdsapirc").exists())
            self.assertEqual(
                set(EVIDENCE_FILES) | {"decoded-payload.json", "decode-report.json"},
                {path.name for path in staged.cams_second_evidence_directory.iterdir()},
            )
            verify_sources_unchanged(records)
            staging = json.loads((work / "staging-manifest.json").read_text(encoding="utf-8"))
            self.assertFalse(staging["credential_files_copied"])
            self.assertFalse(staging["network_used"])
            with self.assertRaisesRegex(CompressedScheduleError, "already exists"):
                stage_inputs(inputs, work)

    def test_staging_rejects_work_directory_outside_os_temp(self):
        with self.assertRaisesRegex(CompressedScheduleError, "OS temp"):
            stage_inputs(
                SourceInputs(*(Path("missing") for _ in range(9))),
                Path.cwd() / "not-a-valid-test-directory",
            )


class GuardAndFaultTests(unittest.TestCase):
    def test_materializer_keys_are_mapped_to_contract_provider_ids(self):
        icon_manifest = {"provider": ICON_PROVIDER}
        cams_manifest = {"provider": CAMS_PROVIDER}
        pollen_manifest = {"provider": CAMS_POLLEN_PROVIDER}
        bundle = {
            "icon": {"documents": {}, "manifest": icon_manifest},
            "cams": {"documents": {}, "manifest": cams_manifest},
            "cams_pollen": {"documents": {}, "manifest": pollen_manifest},
        }

        self.assertIs(icon_manifest, _manifest(bundle, ICON_PROVIDER))
        self.assertIs(cams_manifest, _manifest(bundle, CAMS_PROVIDER))
        self.assertIs(pollen_manifest, _manifest(bundle, CAMS_POLLEN_PROVIDER))
        self.assertEqual({}, _provider_bundle(bundle, ICON_PROVIDER)["documents"])

    def test_network_guard_blocks_external_connect_and_dns_without_network_io(self):
        with LoopbackOnlyNetworkGuard():
            sock = socket.socket()
            self.addCleanup(sock.close)
            with self.assertRaisesRegex(OSError, "non-loopback"):
                sock.connect(("203.0.113.1", 9))
            with self.assertRaisesRegex(OSError, "DNS"):
                socket.getaddrinfo("example.invalid", 443)

    def test_icon_fault_fires_once_before_delegating_latest_cas(self):
        class Store:
            def __init__(self):
                self.calls = []

            def compare_and_swap(self, key, body, **kwargs):
                self.calls.append((key, body, kwargs))
                return "written"

        store = Store()
        guarded = FailBeforeLatestCasStore(store, "weather/v1/icon2i/latest.json")
        with self.assertRaises(InjectedIconCrash):
            guarded.compare_and_swap(
                "weather/v1/icon2i/latest.json",
                b"first",
                expected_etag='"old"',
            )
        self.assertEqual([], store.calls)
        self.assertEqual(
            "written",
            guarded.compare_and_swap(
                "weather/v1/icon2i/latest.json",
                b"second",
                expected_etag='"old"',
            ),
        )
        self.assertEqual(1, len(store.calls))

    def test_monitor_reads_atomic_cams_family_and_release_over_http(self):
        old_run_id = "20260903T000000Z"
        run_id = "20260904T000000Z"

        class Publisher:
            @staticmethod
            def read_latest(_provider):
                return None

        with tempfile.TemporaryDirectory(prefix="compressed-monitor-") as temporary:
            store = SQLiteObjectStore(Path(temporary) / "objects.sqlite3")

            def json_bytes(value):
                return json.dumps(
                    value,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")

            def put_json(key, value):
                return store.put(
                    key,
                    json_bytes(value),
                    content_type="application/json",
                    metadata={},
                )

            def family_documents(source_run_id):
                release = {
                    "family": "cams",
                    "source_run_id": source_run_id,
                    "components": {
                        "core": {
                            "provider": CAMS_PROVIDER,
                            "source_run_id": source_run_id,
                        },
                        "pollen": {
                            "provider": CAMS_POLLEN_PROVIDER,
                            "source_run_id": source_run_id,
                        },
                    },
                }
                release_body = json_bytes(release)
                latest = {
                    "family": "cams",
                    "latest": {
                        "source_run_id": source_run_id,
                        "release_path": f"runs/{source_run_id}/release.json",
                        "release_json_bytes": len(release_body),
                        "release_sha256": hashlib.sha256(release_body).hexdigest(),
                    },
                }
                return latest, release

            municipality = {"municipality": {"istat_code": "093033"}}
            put_json(
                f"weather/v1/{ICON_PROVIDER}/latest.json",
                {
                    "provider": ICON_PROVIDER,
                    "latest": {"source_run_id": run_id},
                },
            )
            put_json(
                f"weather/v1/{ICON_PROVIDER}/runs/{run_id}/municipalities/093033.json",
                municipality,
            )
            old_latest, old_release = family_documents(old_run_id)
            new_latest, new_release = family_documents(run_id)
            family_head = put_json(
                "weather/v1/families/cams/latest.json",
                old_latest,
            )
            put_json(
                f"weather/v1/families/cams/runs/{old_run_id}/release.json",
                old_release,
            )
            put_json(
                f"weather/v1/families/cams/runs/{run_id}/release.json",
                new_release,
            )
            for provider in (CAMS_PROVIDER, CAMS_POLLEN_PROVIDER):
                for source_run_id in (old_run_id, run_id):
                    put_json(
                        f"weather/v1/{provider}/runs/{source_run_id}/"
                        "municipalities/093033.json",
                        municipality,
                    )

            with LoopbackDataPlane(store, 0, ("http://127.0.0.1:5174",)) as plane:
                monitor = ContinuityMonitor(plane.port, Publisher())
                self.assertEqual(
                    {
                        ICON_PROVIDER: run_id,
                        CAMS_PROVIDER: old_run_id,
                        CAMS_POLLEN_PROVIDER: old_run_id,
                    },
                    monitor.check_once(),
                )
                store.compare_and_swap(
                    "weather/v1/families/cams/latest.json",
                    json_bytes(new_latest),
                    expected_etag=family_head.etag,
                    content_type="application/json",
                    metadata={},
                )
                self.assertEqual(
                    {
                        ICON_PROVIDER: run_id,
                        CAMS_PROVIDER: run_id,
                        CAMS_POLLEN_PROVIDER: run_id,
                    },
                    monitor.check_once(),
                )


class SequenceTests(unittest.TestCase):
    def test_exact_fault_retry_sequence_keeps_a_latest_at_every_gate(self):
        old_icon = "20260903T120000Z"
        new_icon = "20260904T000000Z"
        old_cams = "20260903T000000Z"
        new_cams = "20260904T000000Z"
        baseline = {
            ICON_PROVIDER: old_icon,
            CAMS_PROVIDER: old_cams,
            CAMS_POLLEN_PROVIDER: old_cams,
        }
        cams_staged_invisible = {
            ICON_PROVIDER: old_icon,
            CAMS_PROVIDER: old_cams,
            CAMS_POLLEN_PROVIDER: old_cams,
        }
        cams_complete = {
            ICON_PROVIDER: old_icon,
            CAMS_PROVIDER: new_cams,
            CAMS_POLLEN_PROVIDER: new_cams,
        }
        final = {
            ICON_PROVIDER: new_icon,
            CAMS_PROVIDER: new_cams,
            CAMS_POLLEN_PROVIDER: new_cams,
        }

        class Backend:
            def __init__(self):
                self.latest = dict(baseline)
                self.calls = []

            def expected_runs(self):
                return baseline, cams_staged_invisible, cams_complete, final

            def verified_latest(self):
                return dict(self.latest)

            def icon_first_tick(self):
                self.calls.append("icon_first")
                return _publication(ICON_PROVIDER, old_icon, idempotent=True, updated=False, reused=215, manifest_reused=True)

            def cams_fault(self):
                self.calls.append("cams_fault")
                self.latest = dict(cams_staged_invisible)
                return {
                    "state": "VALIDATED",
                    "transitions": ["VALIDATED"],
                    "provider_latest_visible": False,
                }

            def cams_retry(self):
                self.calls.append("cams_retry")
                self.latest = dict(cams_complete)
                return {"state": "PUBLISHED", "core": {"idempotent": True}}

            def icon_fault(self):
                self.calls.append("icon_fault")
                return {"fault": "before_latest_cas", "immutable_manifest_present": True}

            def icon_retry(self):
                self.calls.append("icon_retry")
                self.latest = dict(final)
                return _publication(ICON_PROVIDER, new_icon, reused=215, manifest_reused=True)

            def cams_state_summary(self):
                return {"state": "PUBLISHED"}

        class Monitor:
            def __init__(self, backend):
                self.backend = backend
                self.checks = 0

            def assert_healthy(self):
                self.checks += 1
                return dict(self.backend.latest)

            def summary(self):
                return {"checks": self.checks, "failure_count": 0, "failures": []}

        with tempfile.TemporaryDirectory(prefix="compressed-sequence-") as temporary:
            journal = RunJournal(Path(temporary), ())
            backend = Backend()
            monitor = Monitor(backend)
            result = run_sequence(
                backend,
                journal,
                monitor,
                step_delay_seconds=0,
                final_observation_seconds=0,
            )

            self.assertEqual(
                ["icon_first", "cams_fault", "cams_retry", "icon_fault", "icon_retry"],
                backend.calls,
            )
            self.assertEqual(final, result["latest"])
            self.assertEqual(
                [
                    "baseline_served",
                    "icon_first_idempotent",
                    "cams_expected_crash_after_core_stage",
                    "cams_retry_completed",
                    "icon_expected_crash_before_latest_cas",
                    "icon_retry_completed",
                    "final_observation_completed",
                ],
                [event["event"] for event in journal.events],
            )
            lines = [json.loads(line) for line in journal.events_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(list(range(1, 8)), [line["sequence"] for line in lines])


if __name__ == "__main__":
    unittest.main()

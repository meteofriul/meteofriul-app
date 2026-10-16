"""Contained orchestration tests for the local weather/v1 entrypoint."""

from __future__ import annotations

import contextlib
from datetime import datetime, timezone
import io
from pathlib import Path
from types import SimpleNamespace
import unittest

from local_pipeline.contract_publisher import ContractPublicationVerificationError
from local_pipeline.contract_v1 import (
    CAMS_POLLEN_PROVIDER,
    CAMS_PROVIDER,
    ICON_PROVIDER,
    load_catalog,
)

import serve_contract_v1 as entrypoint


class FakeStore:
    def __init__(self, path, events):
        self.path = path
        self.events = events
        self.closed = False

    def close(self):
        self.closed = True
        self.events.append("store-close")

    def get(self, key):
        if key.startswith("weather/v1/families/cams/runs/"):
            return SimpleNamespace(
                body=(b'{"validation_sha256":"' + (b"c" * 64) + b'"}')
            )
        raise AssertionError(f"unexpected fake object read: {key}")


class FakeServer:
    def __init__(self, events, *, host="127.0.0.1", port=43123):
        self.events = events
        self.server_address = (host, port)
        self.closed = False
        self.served = False

    def serve_forever(self):
        self.served = True
        self.events.append("serve")
        raise KeyboardInterrupt

    def server_close(self):
        self.closed = True
        self.events.append("server-close")


class FakePublisher:
    def __init__(
        self,
        store,
        catalog,
        events,
        *,
        fail_provider=None,
        initial_latest=None,
        corrupt_verified=(),
        supersede_provider=None,
        advance_after_publish_provider=None,
    ):
        self.store = store
        self.catalog = catalog
        self.events = events
        self.fail_provider = fail_provider
        self.latest = dict(initial_latest or {})
        self.corrupt_verified = set(corrupt_verified)
        self.supersede_provider = supersede_provider
        self.advance_after_publish_provider = advance_after_publish_provider
        self.family_latest = None
        if CAMS_PROVIDER in self.latest and CAMS_POLLEN_PROVIDER in self.latest:
            core_run = self.latest[CAMS_PROVIDER]["latest"]["source_run_id"]
            pollen_run = self.latest[CAMS_POLLEN_PROVIDER]["latest"]["source_run_id"]
            if core_run == pollen_run:
                self.family_latest = {
                    "family": "cams",
                    "published_at": "2026-09-03T10:00:00Z",
                    "latest": {
                        "source_run_id": core_run,
                        "release_path": f"runs/{core_run}/release.json",
                    },
                }
        self.latest_etags = {
            provider: f'etag:{document["latest"]["source_run_id"]}'
            for provider, document in self.latest.items()
        }

    @staticmethod
    def cams_family_root():
        return "weather/v1/families/cams"

    def publish_run(self, provider, documents, manifest, *, published_at):
        self.events.append(f"publish:{provider}")
        if provider == self.fail_provider:
            raise entrypoint.ContractPublicationError(
                "synthetic provider publication failure"
            )
        if documents != {"fixture": provider.encode()}:
            raise AssertionError("entrypoint changed materialized documents")
        if manifest["provider"] != provider:
            raise AssertionError("entrypoint mixed provider manifests")
        source_run_id = manifest["source_run_id"]
        active_run_id = (
            "20260904T000000Z"
            if provider == self.supersede_provider
            else source_run_id
        )
        self.latest[provider] = {
            "provider": provider,
            "latest": {"source_run_id": active_run_id},
        }
        self.latest_etags[provider] = f"etag:{active_run_id}"
        return SimpleNamespace(
            provider=provider,
            source_run_id=source_run_id,
            latest_etag=self.latest_etags[provider],
            latest_updated=True,
            superseded=active_run_id != source_run_id,
        )

    def read_latest_if_etag(self, provider, expected_etag):
        self.events.append(f"match:{provider}")
        if provider == self.advance_after_publish_provider:
            active_run_id = "20260904T000000Z"
            self.latest[provider] = {
                "provider": provider,
                "latest": {"source_run_id": active_run_id},
            }
            self.latest_etags[provider] = f"etag:{active_run_id}"
            self.advance_after_publish_provider = None
        if self.latest_etags.get(provider) != expected_etag:
            return None
        return self.latest.get(provider)

    def read_verified_latest(self, provider):
        self.events.append(f"verify:{provider}")
        if provider in self.corrupt_verified:
            raise ContractPublicationVerificationError(
                "synthetic incomplete retained run"
            )
        return self.latest.get(provider)

    def stage_run(self, provider, documents, manifest):
        self.events.append(f"stage:{provider}")
        if provider == self.fail_provider:
            raise entrypoint.ContractPublicationError(
                "synthetic provider staging failure"
            )
        if documents != {"fixture": provider.encode()}:
            raise AssertionError("entrypoint changed materialized documents")
        if manifest["provider"] != provider:
            raise AssertionError("entrypoint mixed provider manifests")
        return SimpleNamespace(
            provider=provider,
            source_run_id=manifest["source_run_id"],
            manifest_sha256=("a" if provider == CAMS_PROVIDER else "b") * 64,
        )

    def release_cams_family(
        self, core_stage, pollen_stage, *, validation_sha256, published_at
    ):
        self.events.append("release:cams")
        self.last_family_published_at = published_at
        if self.fail_provider == "families/cams":
            raise entrypoint.ContractPublicationError(
                "synthetic CAMS family release failure"
            )
        if core_stage.source_run_id != pollen_stage.source_run_id:
            raise AssertionError("entrypoint released mixed CAMS runs")
        if len(validation_sha256) != 64 or not published_at.endswith("Z"):
            raise AssertionError("entrypoint omitted CAMS release evidence")
        source_run_id = core_stage.source_run_id
        self.family_latest = {
            "family": "cams",
            "published_at": published_at,
            "latest": {"source_run_id": source_run_id},
        }
        return SimpleNamespace(
            source_run_id=source_run_id,
            superseded=False,
        )

    def read_verified_cams_family_latest(self):
        self.events.append("verify:families/cams")
        if self.corrupt_verified.intersection(
            {CAMS_PROVIDER, CAMS_POLLEN_PROVIDER, "families/cams"}
        ):
            raise ContractPublicationVerificationError(
                "synthetic incomplete retained CAMS family"
            )
        return self.family_latest


class FakePublishedReader:
    def __init__(self, store, catalog, *, providers):
        self.store = store
        self.catalog = catalog
        self.providers = frozenset(providers)


class ContractV1EntrypointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog()

    def config(self, **changes):
        values = {
            "icon_payload": Path("fixtures/icon.json"),
            "icon_report": Path("fixtures/icon-report.json"),
            "cams_payload": Path("fixtures/cams.json"),
            "cams_report": Path("fixtures/cams-report.json"),
            "object_db": Path("state/weather-objects.sqlite3"),
            "port": 0,
            "published_at": None,
        }
        values.update(changes)
        return entrypoint.EntrypointConfig(**values)

    @staticmethod
    def latest(provider, run_id="20260902T000000Z"):
        return {"provider": provider, "latest": {"source_run_id": run_id}}

    def dependencies(
        self,
        events,
        *,
        fail_provider=None,
        fail_families=(),
        initial_latest=None,
        corrupt_verified=(),
        supersede_provider=None,
        advance_after_publish_provider=None,
        host="127.0.0.1",
    ):
        captured = {}

        def catalog_loader():
            events.append("catalog")
            return self.catalog

        def icon_materializer(**kwargs):
            events.append("materialize:icon")
            captured["icon_materializer"] = kwargs
            if "icon" in fail_families:
                raise entrypoint.SnapshotMaterializationError(
                    "synthetic corrupt ICON source"
                )
            return {
                "catalog": self.catalog,
                "icon": {
                    "documents": {"fixture": ICON_PROVIDER.encode()},
                    "manifest": {
                        "provider": ICON_PROVIDER,
                        "source_run_id": "20260903T000000Z",
                    },
                },
            }

        def cams_materializer(**kwargs):
            events.append("materialize:cams")
            captured["cams_materializer"] = kwargs
            if "cams" in fail_families:
                raise entrypoint.SnapshotMaterializationError(
                    "synthetic corrupt CAMS source"
                )
            return {
                "catalog": self.catalog,
                "cams": {
                    "documents": {"fixture": CAMS_PROVIDER.encode()},
                    "manifest": {
                        "provider": CAMS_PROVIDER,
                        "source_run_id": "20260903T000000Z",
                    },
                },
                "cams_pollen": {
                    "documents": {"fixture": CAMS_POLLEN_PROVIDER.encode()},
                    "manifest": {
                        "provider": CAMS_POLLEN_PROVIDER,
                        "source_run_id": "20260903T000000Z",
                    },
                },
            }

        def store_factory(path):
            events.append("store")
            captured["store"] = FakeStore(path, events)
            return captured["store"]

        def publisher_factory(store, catalog):
            events.append("publisher")
            captured["publisher"] = FakePublisher(
                store,
                catalog,
                events,
                fail_provider=fail_provider,
                initial_latest=initial_latest,
                corrupt_verified=corrupt_verified,
                supersede_provider=supersede_provider,
                advance_after_publish_provider=advance_after_publish_provider,
            )
            return captured["publisher"]

        def server_factory(store, *, port):
            events.append("server")
            captured["server_store"] = store
            captured["server_port"] = port
            captured["server"] = FakeServer(events, host=host)
            return captured["server"]

        def reader_factory(store, catalog, *, providers):
            events.append("reader")
            captured["reader"] = FakePublishedReader(
                store, catalog, providers=providers
            )
            return captured["reader"]

        return captured, {
            "catalog_loader": catalog_loader,
            "icon_materializer": icon_materializer,
            "cams_materializer": cams_materializer,
            "store_factory": store_factory,
            "publisher_factory": publisher_factory,
            "reader_factory": reader_factory,
            "server_factory": server_factory,
            "clock": lambda: datetime(2026, 9, 3, 15, 4, 5, 987, tzinfo=timezone.utc),
        }

    def test_materializes_publishes_all_providers_then_opens_only_loopback(self):
        events = []
        captured, dependencies = self.dependencies(events)
        config = self.config()
        service = entrypoint.build_service(config, **dependencies)

        self.assertEqual(
            events,
            [
                "catalog",
                "store",
                "publisher",
                "materialize:icon",
                f"publish:{ICON_PROVIDER}",
                f"match:{ICON_PROVIDER}",
                "materialize:cams",
                f"stage:{CAMS_PROVIDER}",
                f"stage:{CAMS_POLLEN_PROVIDER}",
                "verify:families/cams",
                "release:cams",
                "verify:families/cams",
                "reader",
                "server",
            ],
        )
        icon_materializer = captured["icon_materializer"]
        cams_materializer = captured["cams_materializer"]
        self.assertIs(icon_materializer["catalog"], self.catalog)
        self.assertIs(cams_materializer["catalog"], self.catalog)
        self.assertEqual(
            config.icon_payload.resolve(), icon_materializer["icon_archive"]
        )
        self.assertEqual(config.icon_report.resolve(), icon_materializer["icon_report"])
        self.assertEqual(config.cams_payload.resolve(), cams_materializer["cams_payload"])
        self.assertEqual(config.cams_report.resolve(), cams_materializer["cams_report"])
        self.assertEqual(config.object_db.resolve(), captured["store"].path)
        self.assertEqual(0, captured["server_port"])
        self.assertEqual("http://127.0.0.1:43123/weather/v1/", service.url)
        self.assertEqual(
            {ICON_PROVIDER, CAMS_PROVIDER, CAMS_POLLEN_PROVIDER},
            set(captured["server_store"].providers),
        )
        self.assertEqual(
            {ICON_PROVIDER, CAMS_PROVIDER, CAMS_POLLEN_PROVIDER, "families/cams"},
            set(service.publications),
        )
        self.assertEqual(
            {"published"},
            {status["status"] for status in service.provider_statuses.values()},
        )
        self.assertFalse(captured["server"].served)

        output = []
        entrypoint.serve_service(service, emit=output.append)
        self.assertTrue(captured["server"].served)
        self.assertTrue(captured["server"].closed)
        self.assertTrue(captured["store"].closed)
        self.assertTrue(any(service.url in line for line in output))

    def test_one_cams_stage_failure_hides_both_products_but_not_icon(self):
        events = []
        captured, dependencies = self.dependencies(events, fail_provider=CAMS_PROVIDER)
        service = entrypoint.build_service(self.config(), **dependencies)

        self.assertIn("server", events)
        self.assertFalse(captured["store"].closed)
        self.assertEqual(
            {ICON_PROVIDER}, set(service.latest)
        )
        self.assertEqual("unavailable", service.provider_statuses[CAMS_PROVIDER]["status"])
        self.assertEqual(
            "unavailable", service.provider_statuses[CAMS_POLLEN_PROVIDER]["status"]
        )
        service.close()

    def test_pollen_stage_failure_never_releases_a_partial_cams_family(self):
        events = []
        _captured, dependencies = self.dependencies(
            events, fail_provider=CAMS_POLLEN_PROVIDER
        )
        service = entrypoint.build_service(self.config(), **dependencies)

        self.assertEqual({ICON_PROVIDER}, set(service.latest))
        self.assertNotIn("release:cams", events)
        self.assertEqual(
            {"unavailable"},
            {
                service.provider_statuses[provider]["status"]
                for provider in (CAMS_PROVIDER, CAMS_POLLEN_PROVIDER)
            },
        )
        service.close()

    def test_release_failure_retains_the_previous_cams_pair_together(self):
        events = []
        previous = {
            CAMS_PROVIDER: self.latest(CAMS_PROVIDER),
            CAMS_POLLEN_PROVIDER: self.latest(CAMS_POLLEN_PROVIDER),
        }
        _captured, dependencies = self.dependencies(
            events,
            fail_provider="families/cams",
            initial_latest=previous,
        )
        service = entrypoint.build_service(self.config(), **dependencies)

        self.assertEqual(
            {CAMS_PROVIDER, CAMS_POLLEN_PROVIDER},
            set(service.latest).intersection(
                {CAMS_PROVIDER, CAMS_POLLEN_PROVIDER}
            ),
        )
        for provider in (CAMS_PROVIDER, CAMS_POLLEN_PROVIDER):
            self.assertEqual("retained", service.provider_statuses[provider]["status"])
            self.assertEqual(
                "20260902T000000Z",
                service.provider_statuses[provider]["active_run_id"],
            )
        service.close()

    def test_restart_reuses_the_immutable_family_publication_time(self):
        events = []
        current = {
            CAMS_PROVIDER: self.latest(CAMS_PROVIDER, "20260903T000000Z"),
            CAMS_POLLEN_PROVIDER: self.latest(
                CAMS_POLLEN_PROVIDER, "20260903T000000Z"
            ),
        }
        captured, dependencies = self.dependencies(
            events,
            initial_latest=current,
        )
        service = entrypoint.build_service(self.config(), **dependencies)

        self.assertEqual(
            "2026-09-03T10:00:00Z",
            captured["publisher"].last_family_published_at,
        )
        self.assertEqual("published", service.provider_statuses[CAMS_PROVIDER]["status"])
        service.close()

    def test_corrupt_cams_family_still_starts_with_icon(self):
        events = []
        captured, dependencies = self.dependencies(events, fail_families={"cams"})
        service = entrypoint.build_service(self.config(), **dependencies)

        self.assertEqual({ICON_PROVIDER}, set(service.latest))
        self.assertEqual("published", service.provider_statuses[ICON_PROVIDER]["status"])
        self.assertEqual("unavailable", service.provider_statuses[CAMS_PROVIDER]["status"])
        self.assertEqual(
            "unavailable", service.provider_statuses[CAMS_POLLEN_PROVIDER]["status"]
        )
        self.assertNotIn(f"stage:{CAMS_PROVIDER}", events)
        self.assertEqual({ICON_PROVIDER}, set(captured["server_store"].providers))
        output = []
        entrypoint.serve_service(service, emit=output.append)
        self.assertTrue(captured["server"].served)
        self.assertTrue(any("cams_europe: non disponibile" in line for line in output))

    def test_cams_object_store_failure_isolated_from_published_icon(self):
        events = []
        captured, dependencies = self.dependencies(events)
        original_factory = dependencies["publisher_factory"]

        def publisher_factory(store, catalog):
            publisher = original_factory(store, catalog)

            def unavailable_family():
                events.append("store-error:families/cams")
                raise entrypoint.ObjectStoreError(
                    "synthetic family-scoped backing-store failure"
                )

            publisher.read_verified_cams_family_latest = unavailable_family
            return publisher

        dependencies["publisher_factory"] = publisher_factory
        service = entrypoint.build_service(self.config(), **dependencies)

        self.assertEqual({ICON_PROVIDER}, set(service.latest))
        self.assertEqual("published", service.provider_statuses[ICON_PROVIDER]["status"])
        for provider in (CAMS_PROVIDER, CAMS_POLLEN_PROVIDER):
            self.assertEqual("unavailable", service.provider_statuses[provider]["status"])
            self.assertIn("recovery failed", service.provider_statuses[provider]["reason"])
        self.assertEqual(2, events.count("store-error:families/cams"))
        self.assertIn("server", events)
        self.assertFalse(captured["store"].closed)
        service.close()

    def test_corrupt_icon_family_still_starts_with_both_cams_products(self):
        events = []
        captured, dependencies = self.dependencies(events, fail_families={"icon"})
        service = entrypoint.build_service(self.config(), **dependencies)

        self.assertEqual({CAMS_PROVIDER, CAMS_POLLEN_PROVIDER}, set(service.latest))
        self.assertEqual("unavailable", service.provider_statuses[ICON_PROVIDER]["status"])
        self.assertNotIn(f"publish:{ICON_PROVIDER}", events)
        self.assertEqual(
            {CAMS_PROVIDER, CAMS_POLLEN_PROVIDER},
            set(captured["server_store"].providers),
        )
        output = []
        entrypoint.serve_service(service, emit=output.append)
        self.assertTrue(captured["server"].served)
        self.assertTrue(any("icon2i: non disponibile" in line for line in output))

    def test_failed_family_retains_only_fully_verified_previous_runs(self):
        events = []
        previous = {
            CAMS_PROVIDER: self.latest(CAMS_PROVIDER),
            CAMS_POLLEN_PROVIDER: self.latest(CAMS_POLLEN_PROVIDER),
        }
        _captured, dependencies = self.dependencies(
            events,
            fail_families={"cams"},
            initial_latest=previous,
        )
        service = entrypoint.build_service(self.config(), **dependencies)

        self.assertEqual(
            {ICON_PROVIDER, CAMS_PROVIDER, CAMS_POLLEN_PROVIDER}, set(service.latest)
        )
        self.assertEqual("retained", service.provider_statuses[CAMS_PROVIDER]["status"])
        self.assertEqual(
            "20260902T000000Z",
            service.provider_statuses[CAMS_PROVIDER]["active_run_id"],
        )
        service.close()

    def test_incomplete_previous_run_is_not_retained(self):
        events = []
        previous = {ICON_PROVIDER: self.latest(ICON_PROVIDER)}
        _captured, dependencies = self.dependencies(
            events,
            fail_families={"icon"},
            initial_latest=previous,
            corrupt_verified={ICON_PROVIDER},
        )
        service = entrypoint.build_service(self.config(), **dependencies)

        self.assertNotIn(ICON_PROVIDER, service.latest)
        self.assertEqual("unavailable", service.provider_statuses[ICON_PROVIDER]["status"])
        self.assertIn("recovery failed", service.provider_statuses[ICON_PROVIDER]["reason"])
        service.close()

    def test_no_verified_provider_closes_store_and_never_opens_socket(self):
        events = []
        captured, dependencies = self.dependencies(
            events, fail_families={"icon", "cams"}
        )
        with self.assertRaisesRegex(
            entrypoint.ContractV1EntrypointError, "no provider"
        ):
            entrypoint.build_service(self.config(), **dependencies)
        self.assertTrue(captured["store"].closed)
        self.assertNotIn("server", events)

    def test_concurrently_newer_latest_is_accepted_after_full_verification(self):
        events = []
        _captured, dependencies = self.dependencies(
            events, supersede_provider=ICON_PROVIDER
        )
        service = entrypoint.build_service(self.config(), **dependencies)

        self.assertEqual("superseded", service.provider_statuses[ICON_PROVIDER]["status"])
        self.assertEqual(
            "20260904T000000Z",
            service.provider_statuses[ICON_PROVIDER]["active_run_id"],
        )
        self.assertNotIn(f"match:{ICON_PROVIDER}", events)
        self.assertIn(f"verify:{ICON_PROVIDER}", events)
        service.close()

    def test_pointer_advance_after_publish_falls_back_to_full_verification(self):
        events = []
        _captured, dependencies = self.dependencies(
            events,
            advance_after_publish_provider=ICON_PROVIDER,
        )
        service = entrypoint.build_service(self.config(), **dependencies)

        self.assertEqual("superseded", service.provider_statuses[ICON_PROVIDER]["status"])
        self.assertEqual(
            "20260904T000000Z",
            service.provider_statuses[ICON_PROVIDER]["active_run_id"],
        )
        self.assertIn(f"match:{ICON_PROVIDER}", events)
        self.assertIn(f"verify:{ICON_PROVIDER}", events)
        self.assertLess(
            events.index(f"match:{ICON_PROVIDER}"),
            events.index(f"verify:{ICON_PROVIDER}"),
        )
        service.close()

    def test_stale_candidate_retains_a_newer_verified_latest(self):
        events = []
        newer = {ICON_PROVIDER: self.latest(ICON_PROVIDER, "20260904T000000Z")}
        _captured, dependencies = self.dependencies(
            events,
            fail_provider=ICON_PROVIDER,
            initial_latest=newer,
        )
        service = entrypoint.build_service(self.config(), **dependencies)

        self.assertEqual("retained", service.provider_statuses[ICON_PROVIDER]["status"])
        self.assertEqual(
            "20260904T000000Z",
            service.provider_statuses[ICON_PROVIDER]["active_run_id"],
        )
        service.close()

    def test_non_loopback_factory_is_rejected_and_closed(self):
        events = []
        captured, dependencies = self.dependencies(events, host="0.0.0.0")
        with self.assertRaisesRegex(entrypoint.ContractV1EntrypointError, "loopback"):
            entrypoint.build_service(self.config(), **dependencies)
        self.assertTrue(captured["server"].closed)
        self.assertTrue(captured["store"].closed)

    def test_catalog_mismatch_isolated_to_its_provider_family(self):
        events = []
        _captured, dependencies = self.dependencies(events)

        def mismatched_cams_materializer(**_kwargs):
            events.append("materialize:cams-mismatch")
            return {"catalog": object(), "cams": {}, "cams_pollen": {}}

        dependencies["cams_materializer"] = mismatched_cams_materializer
        service = entrypoint.build_service(self.config(), **dependencies)
        self.assertEqual({ICON_PROVIDER}, set(service.latest))
        self.assertEqual("unavailable", service.provider_statuses[CAMS_PROVIDER]["status"])
        service.close()

    def test_configuration_rejects_collisions_and_requires_explicit_cli_paths_and_port(self):
        collision = self.config(object_db=Path("fixtures/icon.json"))
        with self.assertRaisesRegex(entrypoint.ContractV1EntrypointError, "overwrite"):
            entrypoint.build_service(collision)

        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            entrypoint.parse_config([])
        config = entrypoint.parse_config(
            [
                "--icon-payload",
                "i.json",
                "--icon-report",
                "ir.json",
                "--cams-payload",
                "c.json",
                "--cams-report",
                "cr.json",
                "--object-db",
                "objects.sqlite3",
                "--port",
                "8787",
                "--published-at",
                "2026-09-03T15:04:05Z",
            ]
        )
        self.assertEqual(8787, config.port)
        self.assertEqual("2026-09-03T15:04:05Z", config.published_at)
        self.assertNotIn("--host", entrypoint.build_parser().format_help())


if __name__ == "__main__":
    unittest.main()

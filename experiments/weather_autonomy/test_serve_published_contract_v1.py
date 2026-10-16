"""Contained tests for the strict read-only weather/v1 process boundary."""

from __future__ import annotations

import contextlib
import io
from pathlib import Path
import unittest

from local_pipeline.contract_v1 import (
    CAMS_POLLEN_PROVIDER,
    CAMS_PROVIDER,
    ICON_PROVIDER,
    load_catalog,
)

import serve_published_contract_v1 as entrypoint


class FakeReadOnlyStore:
    def __init__(self, path, events):
        self.path = path
        self.events = events
        self.closed = False

    def head(self, _key):
        raise AssertionError("reader factory owns verification in this test")

    def get(self, _key):
        raise AssertionError("reader factory owns verification in this test")

    def close(self):
        self.closed = True
        self.events.append("store-close")


class FakePublishedReader:
    def __init__(self, store, catalog, events):
        self.store = store
        self.catalog = catalog
        self.events = events
        self.closed = False
        self.provider_statuses = {
            ICON_PROVIDER: {
                "status": "verified",
                "active_run_id": "20260904T000000Z",
                "error_type": None,
            },
            CAMS_PROVIDER: {
                "status": "unavailable",
                "active_run_id": None,
                "error_type": "ObjectNotFound",
            },
            CAMS_POLLEN_PROVIDER: {
                "status": "unavailable",
                "active_run_id": None,
                "error_type": "ObjectNotFound",
            },
        }

    def head(self, key):
        return self.store.head(key)

    def get(self, key):
        return self.store.get(key)

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.events.append("reader-close")
        self.store.close()


class FakeServer:
    def __init__(self, events, host="127.0.0.1"):
        self.events = events
        self.server_address = (host, 43124)
        self.closed = False
        self.served = False

    def serve_forever(self):
        self.served = True
        self.events.append("serve")
        raise KeyboardInterrupt

    def server_close(self):
        self.closed = True
        self.events.append("server-close")


class PublishedDataPlaneEntrypointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog()

    @staticmethod
    def config(**changes):
        values = {"object_db": Path("state/objects.sqlite3"), "port": 0}
        values.update(changes)
        return entrypoint.ReaderConfig(**values)

    def dependencies(self, events, *, host="127.0.0.1"):
        captured = {}

        def catalog_loader():
            events.append("catalog")
            return self.catalog

        def store_factory(path):
            events.append("read-only-store")
            captured["store"] = FakeReadOnlyStore(path, events)
            return captured["store"]

        def reader_factory(store, catalog):
            events.append("referenced-reader")
            captured["reader"] = FakePublishedReader(store, catalog, events)
            return captured["reader"]

        def server_factory(reader, *, port):
            events.append("server")
            captured["server_reader"] = reader
            captured["port"] = port
            captured["server"] = FakeServer(events, host=host)
            return captured["server"]

        return captured, {
            "catalog_loader": catalog_loader,
            "store_factory": store_factory,
            "reader_factory": reader_factory,
            "server_factory": server_factory,
        }

    def test_starts_reader_without_materializer_publisher_or_job_inputs(self):
        events = []
        captured, dependencies = self.dependencies(events)
        service = entrypoint.build_service(self.config(), **dependencies)
        self.assertEqual(
            ["catalog", "read-only-store", "referenced-reader", "server"],
            events,
        )
        self.assertEqual(Path("state/objects.sqlite3"), captured["store"].path)
        self.assertIs(captured["reader"], captured["server_reader"])
        self.assertEqual(0, captured["port"])
        self.assertEqual(
            "http://127.0.0.1:43124/weather/v1/",
            service.url,
        )
        self.assertFalse(hasattr(captured["store"], "put"))
        self.assertFalse(hasattr(captured["store"], "compare_and_swap"))

        output = []
        entrypoint.serve_service(service, emit=output.append)
        self.assertTrue(captured["server"].served)
        self.assertTrue(captured["server"].closed)
        self.assertTrue(captured["reader"].closed)
        self.assertTrue(captured["store"].closed)
        self.assertIn(
            "icon2i: 20260904T000000Z · verified",
            output,
        )
        self.assertIn("cams (core + pollini): non disponibile", output)
        self.assertTrue(any("strettamente read-only" in line for line in output))

    def test_status_output_never_presents_uncorrelated_cams_components_as_valid(self):
        events = []
        captured, dependencies = self.dependencies(events)
        service = entrypoint.build_service(self.config(), **dependencies)
        captured["reader"].provider_statuses[CAMS_PROVIDER] = {
            "status": "verified",
            "active_run_id": "20260904T000000Z",
            "error_type": None,
        }
        captured["reader"].provider_statuses[CAMS_POLLEN_PROVIDER] = {
            "status": "verified",
            "active_run_id": "20260905T000000Z",
            "error_type": None,
        }

        output = []
        entrypoint.serve_service(service, emit=output.append)

        self.assertIn("cams (core + pollini): stato non correlato", output)
        self.assertFalse(
            any(
                line.startswith("cams (core + pollini):") and "· verified" in line
                for line in output
            )
        )

    def test_non_loopback_server_is_rejected_and_everything_is_closed(self):
        events = []
        captured, dependencies = self.dependencies(events, host="0.0.0.0")
        with self.assertRaisesRegex(entrypoint.PublishedDataPlaneError, "loopback"):
            entrypoint.build_service(self.config(), **dependencies)
        self.assertTrue(captured["server"].closed)
        self.assertTrue(captured["reader"].closed)
        self.assertTrue(captured["store"].closed)

    def test_cli_requires_only_existing_object_store_and_port(self):
        config = entrypoint.parse_config(
            ["--object-db", "objects.sqlite3", "--port", "8767"]
        )
        self.assertEqual(Path("objects.sqlite3"), config.object_db)
        self.assertEqual(8767, config.port)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            entrypoint.parse_config([])

    def test_configuration_fails_before_opening_store(self):
        events = []
        _captured, dependencies = self.dependencies(events)
        with self.assertRaisesRegex(entrypoint.PublishedDataPlaneError, "port"):
            entrypoint.build_service(self.config(port=70000), **dependencies)
        self.assertEqual([], events)


if __name__ == "__main__":
    unittest.main()

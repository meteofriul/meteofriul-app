"""Tests for the socket-free local snapshot writer boundary."""

from __future__ import annotations

import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from local_pipeline.contract_v1 import (
    CAMS_POLLEN_PROVIDER,
    CAMS_PROVIDER,
    ICON_PROVIDER,
)

import publish_snapshots_v1 as writer


class SnapshotWriterTests(unittest.TestCase):
    @staticmethod
    def config() -> writer.SnapshotWriterConfig:
        return writer.SnapshotWriterConfig(
            icon_payload=Path("icon.json"),
            icon_report=Path("icon-report.json"),
            cams_payload=Path("cams.json"),
            cams_report=Path("cams-report.json"),
            object_db=Path("objects.sqlite3"),
        )

    @staticmethod
    def service(*, missing: str | None = None, split_cams: bool = False):
        run = "20260904T000000Z"
        latest = {
            provider: {
                "latest": {
                    "source_run_id": (
                        "20260903T000000Z"
                        if split_cams and provider == CAMS_POLLEN_PROVIDER
                        else run
                    )
                }
            }
            for provider in (ICON_PROVIDER, CAMS_PROVIDER, CAMS_POLLEN_PROVIDER)
            if provider != missing
        }
        statuses = {
            provider: {"status": "published"}
            for provider in latest
        }
        service = SimpleNamespace(
            latest=latest,
            provider_statuses=statuses,
            closed=False,
        )

        def close():
            service.closed = True
            service.server.server_close()

        service.close = close
        return service

    def builder(self, service, observed):
        def build(config, *, server_factory):
            observed["config"] = config
            service.server = server_factory(object(), port=config.port)
            observed["boundary"] = service.server
            return service

        return build

    def test_publishes_all_three_products_without_a_listening_socket(self):
        observed = {}
        service = self.service()
        result = writer.publish_snapshots(
            self.config(),
            service_builder=self.builder(service, observed),
        )

        self.assertEqual("ready", result["status"])
        self.assertFalse(result["socket_opened"])
        self.assertEqual(0, observed["config"].port)
        self.assertEqual(("127.0.0.1", 0), observed["boundary"].server_address)
        self.assertTrue(service.closed)
        self.assertTrue(observed["boundary"].closed)
        self.assertEqual(
            "20260904T000000Z",
            result["providers"][CAMS_PROVIDER]["source_run_id"],
        )

    def test_incomplete_or_split_family_fails_closed_and_closes(self):
        for service in (
            self.service(missing=CAMS_POLLEN_PROVIDER),
            self.service(split_cams=True),
        ):
            with self.subTest(service=service):
                with self.assertRaises(writer.SnapshotWriterError):
                    writer.publish_snapshots(
                        self.config(),
                        service_builder=self.builder(service, {}),
                    )
                self.assertTrue(service.closed)

    def test_cli_emits_one_safe_canonical_result(self):
        stream = io.StringIO()
        exit_code = writer.main([], stream=stream)
        document = json.loads(stream.getvalue())
        self.assertEqual(2, exit_code)
        self.assertEqual("invalid_cli_arguments", document["reason_code"])
        self.assertNotIn("usage", stream.getvalue().lower())
        self.assertEqual(1, len(stream.getvalue().splitlines()))

    def test_parser_requires_only_snapshots_and_object_database(self):
        config = writer.parse_config(
            [
                "--icon-payload", "icon.json",
                "--icon-report", "icon-report.json",
                "--cams-payload", "cams.json",
                "--cams-report", "cams-report.json",
                "--object-db", "objects.sqlite3",
            ]
        )
        self.assertEqual(Path("objects.sqlite3"), config.object_db)
        self.assertNotIn("--port", writer.build_parser().format_help())


if __name__ == "__main__":
    unittest.main()

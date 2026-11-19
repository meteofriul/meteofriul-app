import json
import unittest
from datetime import date, datetime, timezone
from unittest.mock import Mock, patch

from google.api_core.exceptions import NotFound

from app.events.source_controls import (
    decode_controls, empty_controls, paused_names, read_controls,
    reserve_verification, save_control,
)


class SourceControlsTests(unittest.TestCase):
    def test_missing_file_defaults_to_all_active(self):
        blob = Mock()
        blob.reload.side_effect = NotFound("missing")
        self.assertEqual(read_controls(blob), (empty_controls(), 0))

    def test_pause_until_is_inclusive_and_expires(self):
        controls = {"sources": {"A": {"enabled": True, "pausedUntil": "2026-11-17"},
                                "B": {"enabled": False, "pausedUntil": None}}}
        self.assertEqual(paused_names(controls, today=date(2026, 11, 17)), {"A", "B"})
        self.assertEqual(paused_names(controls, today=date(2026, 11, 18)), {"B"})

    def test_save_requires_revision_and_registered_source(self):
        blob = Mock(generation=8, size=80)
        blob.download_as_bytes.return_value = json.dumps(empty_controls()).encode()
        saved = save_control(blob, name="Teatro Verdi Trieste", enabled=False,
                             paused_until=None, reason="Fonte non raggiungibile",
                             actor="owner", expected_revision=0,
                             allowed_sources={"Teatro Verdi Trieste"})
        self.assertEqual(saved["revision"], 1)
        self.assertFalse(saved["sources"]["Teatro Verdi Trieste"]["enabled"])
        self.assertEqual(blob.upload_from_string.call_args.kwargs["if_generation_match"], 8)
        with self.assertRaisesRegex(RuntimeError, "revision conflict"):
            save_control(blob, name="Teatro Verdi Trieste", enabled=True,
                         paused_until=None, reason="Nuova prova", actor="owner",
                         expected_revision=2, allowed_sources={"Teatro Verdi Trieste"})
        with self.assertRaisesRegex(ValueError, "unknown source"):
            save_control(blob, name="https://attacker.test", enabled=False,
                         paused_until=None, reason="Prova", actor="owner",
                         expected_revision=0, allowed_sources={"Teatro Verdi Trieste"})

    def test_rejects_corrupt_controls(self):
        with self.assertRaises(ValueError):
            decode_controls(b'{"schema":"wrong","revision":0,"sources":{}}')
        with self.assertRaises(ValueError):
            decode_controls(b"")

    def test_verification_reservation_blocks_repeated_job_requests(self):
        now = datetime(2026, 11, 15, 10, tzinfo=timezone.utc)
        blob = Mock(generation=2, size=100)
        blob.download_as_bytes.return_value = json.dumps(empty_controls()).encode()
        saved = reserve_verification(blob, name="Barcolana", actor="owner",
                                     allowed_sources={"Barcolana"}, now=now)
        self.assertEqual(saved["revision"], 1)
        blob.download_as_bytes.return_value = json.dumps(saved).encode()
        with self.assertRaisesRegex(RuntimeError, "cooldown"):
            reserve_verification(blob, name="Barcolana", actor="owner",
                                 allowed_sources={"Barcolana"}, now=now)


class SelectionTests(unittest.TestCase):
    def test_daily_skips_paused_but_single_source_can_probe_it(self):
        from app.events.pilot_catalog import PILOT_PROJECT
        from app.events.pilot_cloud import publish
        from app.events.pilot_sources import source_adapters
        client = Mock(project=PILOT_PROJECT)
        blob = client.bucket.return_value.blob.return_value
        blob.generation = 1
        blob.size = 80
        blob.download_as_bytes.return_value = b'{"schema":"pilot-events-v1","sources":{}}'
        controls = {"schema": "event-source-controls-v1", "revision": 1,
                    "sources": {"Teatro Verdi Trieste": {"enabled": False}}}
        with patch("app.events.pilot_cloud.read_controls", return_value=(controls, 1)), \
             patch("app.events.pilot_cloud.collect", side_effect=RuntimeError("stop")) as collect:
            with self.assertRaisesRegex(RuntimeError, "stop"):
                publish(client, project=PILOT_PROJECT)
            self.assertNotIn("Teatro Verdi Trieste", collect.call_args.args[1])
            with self.assertRaisesRegex(RuntimeError, "stop"):
                publish(client, project=PILOT_PROJECT, source="Teatro Verdi Trieste")
            self.assertEqual(set(collect.call_args.args[1]), {"Teatro Verdi Trieste"})
            self.assertEqual(len(source_adapters(PILOT_PROJECT)), 15)

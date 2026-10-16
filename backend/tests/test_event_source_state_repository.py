import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.repositories.event_sources import (
    EVENT_SOURCE_STATE_SCHEMA,
    EventSourceStateRepository,
    EventSourceStateRepositoryUnavailable,
)


class EventSourceStateRepositoryTests(unittest.TestCase):
    def test_local_state_round_trip_is_atomic_and_does_not_need_firestore(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "event-sources.json"
            repository = EventSourceStateRepository(
                lambda: self.fail("Firestore must not be called"),
                local_state_path=path,
            )
            state = {
                "schema_version": EVENT_SOURCE_STATE_SCHEMA,
                "publication_enabled": False,
                "approved": [],
            }

            self.assertEqual(repository.save(state), "local_file")
            loaded, storage = repository.load()

            self.assertEqual(storage, "local_file")
            self.assertEqual(loaded, state)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), state)
            self.assertEqual(list(path.parent.glob("*.tmp")), [])

    def test_invalid_local_json_fails_closed(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "event-sources.json"
            path.write_text("not json", encoding="utf-8")
            repository = EventSourceStateRepository(
                lambda: None,
                local_state_path=path,
            )

            with self.assertRaisesRegex(
                EventSourceStateRepositoryUnavailable,
                "event_source_local_state_invalid",
            ):
                repository.load()

    def test_missing_firestore_fails_closed(self):
        repository = EventSourceStateRepository(lambda: None)

        with self.assertRaisesRegex(
            EventSourceStateRepositoryUnavailable,
            "event_source_firestore_unavailable",
        ):
            repository.load()

    def test_unknown_schema_is_not_written(self):
        with TemporaryDirectory() as directory:
            repository = EventSourceStateRepository(
                lambda: None,
                local_state_path=Path(directory) / "event-sources.json",
            )

            with self.assertRaisesRegex(ValueError, "event_source_state_schema_invalid"):
                repository.save({"schema_version": "unknown"})


if __name__ == "__main__":
    unittest.main()

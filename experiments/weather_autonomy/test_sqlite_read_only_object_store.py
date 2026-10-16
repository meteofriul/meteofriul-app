"""Offline capability tests for the local read-only object-store adapter."""

from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from local_pipeline.object_store_ports import ObjectReader, ObjectStore
from local_pipeline.sqlite_object_store import ObjectNotFound, ObjectStoreError, SQLiteObjectStore
from local_pipeline.sqlite_read_only_object_store import SQLiteReadOnlyObjectStore


KEY = "weather/v1/icon2i/latest.json"


class SQLiteReadOnlyObjectStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="weather-read-only-store-")
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "objects.sqlite3"
        self.writer = SQLiteObjectStore(self.path)
        self.body = json.dumps({"revision": 1}, separators=(",", ":")).encode()
        self.head = self.writer.put(
            KEY,
            self.body,
            content_type="application/json",
            metadata={"kind": "latest"},
        )

    def test_reader_has_only_the_read_capability_and_preserves_bytes(self):
        before = self.path.read_bytes()
        reader = SQLiteReadOnlyObjectStore(self.path)
        self.assertIsInstance(reader, ObjectReader)
        self.assertNotIsInstance(reader, ObjectStore)
        self.assertFalse(hasattr(reader, "put"))
        self.assertFalse(hasattr(reader, "compare_and_swap"))
        self.assertEqual(self.head, reader.head(KEY))
        self.assertEqual(self.body, reader.get(KEY).body)
        self.assertEqual(before, self.path.read_bytes())

    def test_query_only_connection_rejects_every_mutation(self):
        reader = SQLiteReadOnlyObjectStore(self.path)
        with closing(reader._connect()) as connection:
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute("DELETE FROM objects")
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute("CREATE TABLE forbidden (value INTEGER)")
        self.assertEqual(self.body, self.writer.get(KEY).body)

    def test_missing_database_fails_without_creating_a_file(self):
        missing = Path(self.temporary.name) / "missing.sqlite3"
        with self.assertRaisesRegex(ObjectStoreError, "missing"):
            SQLiteReadOnlyObjectStore(missing)
        self.assertFalse(missing.exists())

    def test_invalid_schema_and_unknown_key_fail_closed(self):
        invalid = Path(self.temporary.name) / "invalid.sqlite3"
        with closing(sqlite3.connect(invalid)) as connection:
            with connection:
                connection.execute("CREATE TABLE unrelated (value INTEGER)")
        with self.assertRaisesRegex(ObjectStoreError, "schema is invalid"):
            SQLiteReadOnlyObjectStore(invalid)

        reader = SQLiteReadOnlyObjectStore(self.path)
        with self.assertRaises(ObjectNotFound):
            reader.get("weather/v1/icon2i/runs/20260905T000000Z/manifest.json")

    def test_short_lived_reads_observe_a_separate_writer_cas(self):
        reader = SQLiteReadOnlyObjectStore(self.path)
        replacement = json.dumps({"revision": 2}, separators=(",", ":")).encode()
        self.writer.compare_and_swap(
            KEY,
            replacement,
            expected_etag=self.head.etag,
            content_type="application/json",
            metadata={"kind": "latest"},
        )
        self.assertEqual(replacement, reader.get(KEY).body)


if __name__ == "__main__":
    unittest.main()

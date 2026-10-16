"""Capability-based ports for weather object storage.

The public data plane receives only :class:`ObjectReader`.  Publication
adapters implement the larger :class:`ObjectStore`, but those methods are not
part of the reader capability and therefore cannot be reached accidentally by
the serving process.
"""

from __future__ import annotations

from typing import Mapping, Protocol, runtime_checkable

from .sqlite_object_store import ObjectHead, StoredObject


@runtime_checkable
class ObjectReader(Protocol):
    def head(self, key: str) -> ObjectHead: ...

    def get(self, key: str) -> StoredObject: ...


@runtime_checkable
class ObjectStore(ObjectReader, Protocol):
    def put(
        self,
        key: str,
        body: bytes | bytearray | memoryview,
        *,
        content_type: str = "application/octet-stream",
        metadata: Mapping[str, object] | None = None,
    ) -> ObjectHead: ...

    def compare_and_swap(
        self,
        key: str,
        body: bytes | bytearray | memoryview,
        *,
        expected_etag: str | None,
        content_type: str = "application/octet-stream",
        metadata: Mapping[str, object] | None = None,
    ) -> ObjectHead: ...

    def exists(self, key: str) -> bool: ...


__all__ = ["ObjectReader", "ObjectStore"]

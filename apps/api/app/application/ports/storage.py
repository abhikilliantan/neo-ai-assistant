"""Storage provider port — opaque-key blob store for original uploaded files
(ADR 0002).

Deliberately DUMB and tenant-agnostic: it stores, reads, and deletes bytes by an
opaque `key` and knows nothing about organisations. Tenancy is enforced one
layer above — the caller mints org-scoped keys and re-verifies the tenant via
the RLS-locked `documents` row before every read (ADR 0002, "Tenant isolation
outside the database"). RLS on the pointer table transitively protects the bytes.

`backend_id` is the provider's name, persisted per document row for provenance,
mirroring `embedding_model` / `chunker`. Object-storage backends (S3/MinIO/Azure)
land in later slices behind this same Protocol.
"""

from __future__ import annotations

from typing import Protocol


class StorageProvider(Protocol):
    @property
    def backend_id(self) -> str: ...

    async def put(self, *, key: str, data: bytes, content_type: str) -> None: ...

    async def get(self, *, key: str) -> bytes: ...

    async def delete(self, *, key: str) -> None: ...  # idempotent

    async def exists(self, *, key: str) -> bool: ...

"""Storage provider builder — config-driven selection (ADR 0002).

Mirrors `build_document_parser` / `build_chat_provider`: one selector, fail-fast
on the unknown branch. Slice 1 ships only the filesystem backend; S3/MinIO/Azure
are added here later behind the same `StorageProvider` port.
"""

from __future__ import annotations

from app.application.ports.storage import StorageProvider
from app.infrastructure.config import Settings
from app.infrastructure.storage.filesystem import LocalFilesystemStorage


def build_storage_provider(settings: Settings) -> StorageProvider:
    if settings.document_storage_backend == "filesystem":
        return LocalFilesystemStorage(root=settings.document_storage_root)
    raise RuntimeError(f"Unknown DOCUMENT_STORAGE_BACKEND: {settings.document_storage_backend!r}")


__all__ = ["LocalFilesystemStorage", "build_storage_provider"]

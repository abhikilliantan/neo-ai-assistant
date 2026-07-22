"""Storage provider builder + boot-time writability probe (ADR 0002).

`build_storage_provider` mirrors `build_document_parser` / `build_chat_provider`:
one selector, fail-fast on the unknown branch. Slice 1 ships only the filesystem
backend; S3/MinIO/Azure are added here later behind the same `StorageProvider`
port.

`probe_storage_writable` is the slice-1 hardening: a one-time write→read→delete
against the real storage root at startup so a misprovisioned/read-only volume
refuses the boot with a clear message, instead of 500-ing a user's first upload.
"""

from __future__ import annotations

import contextlib

from app.application.ports.storage import StorageProvider
from app.infrastructure.config import Settings
from app.infrastructure.storage.filesystem import LocalFilesystemStorage

# Reserved, NON-tenant key. Real objects live under `org/{org}/{uuid}`; this
# `_neo_internal/` namespace can never collide with a tenant object.
_PROBE_KEY = "_neo_internal/_startup_writability_probe"
_PROBE_SENTINEL = b"neo-storage-writability-probe"


def build_storage_provider(settings: Settings) -> StorageProvider:
    if settings.document_storage_backend == "filesystem":
        return LocalFilesystemStorage(root=settings.document_storage_root)
    raise RuntimeError(f"Unknown DOCUMENT_STORAGE_BACKEND: {settings.document_storage_backend!r}")


async def probe_storage_writable(storage: StorageProvider, *, root: str) -> None:
    """Fail-fast boot check: write→read→delete a reserved sentinel. Raises a fatal
    RuntimeError (naming the storage root + the underlying OS error) if any step
    fails, so the container refuses to start rather than booting broken. The
    sentinel is ALWAYS deleted, including on the failure path.
    """
    try:
        await storage.put(
            key=_PROBE_KEY, data=_PROBE_SENTINEL, content_type="application/octet-stream"
        )
        got = await storage.get(key=_PROBE_KEY)
    except Exception as e:
        with contextlib.suppress(Exception):
            await storage.delete(key=_PROBE_KEY)
        raise RuntimeError(
            f"storage root {root!r} failed the startup writability probe — the "
            f"container will not start. Ensure the storage volume exists and is "
            f"writable by the app user. Underlying error: {e!r}"
        ) from e

    # I/O succeeded — always remove the sentinel, then validate integrity.
    with contextlib.suppress(Exception):
        await storage.delete(key=_PROBE_KEY)
    if got != _PROBE_SENTINEL:
        raise RuntimeError(
            f"storage root {root!r} failed the startup writability probe — read-back "
            f"returned different bytes than were written."
        )


__all__ = ["LocalFilesystemStorage", "build_storage_provider", "probe_storage_writable"]

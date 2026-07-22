"""Local filesystem StorageProvider (ADR 0002, slice 1).

The SINGLE backend for this slice — the one that runs in the current Docker dev
stack, keyed under a configured root on a mounted volume. Object-storage backends
land later behind the same `StorageProvider` port; this backend stays permanently
as the dev/CI/single-node-on-prem implementation.

Root-confined: keys map to paths UNDER a fixed root. Keys are server-minted
(`org/{org_uuid}/{storage_uuid}`) so traversal is impossible by construction, but
`_path` re-checks defensively anyway. File I/O runs in a worker thread so it never
blocks the event loop.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

_BACKEND_ID = "filesystem"


class LocalFilesystemStorage:
    def __init__(self, *, root: str | Path) -> None:
        # Construction is side-effect-free (no mkdir) so building the provider at
        # startup never touches the filesystem — the root (and subdirs) are created
        # lazily on the first `put`. The root is a mounted volume in the container.
        self._root = Path(root).resolve()

    @property
    def backend_id(self) -> str:
        return _BACKEND_ID

    def _path(self, key: str) -> Path:
        # Server-minted keys are safe; confine to root defensively regardless.
        if not key or key.startswith("/") or ".." in key.split("/"):
            raise ValueError(f"unsafe storage key: {key!r}")
        path = (self._root / key).resolve()
        if path != self._root and self._root not in path.parents:
            raise ValueError(f"storage key escapes root: {key!r}")
        return path

    async def put(self, *, key: str, data: bytes, content_type: str) -> None:
        # content_type is accepted for interface parity (object stores persist it
        # as object metadata); the filesystem backend keeps it on the DB row only.
        path = self._path(key)

        def _write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

        await asyncio.to_thread(_write)

    async def get(self, *, key: str) -> bytes:
        path = self._path(key)
        return await asyncio.to_thread(path.read_bytes)

    async def delete(self, *, key: str) -> None:
        path = self._path(key)
        await asyncio.to_thread(lambda: path.unlink(missing_ok=True))

    async def exists(self, *, key: str) -> bool:
        return await asyncio.to_thread(self._path(key).is_file)

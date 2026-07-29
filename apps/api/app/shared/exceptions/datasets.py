"""Domain exceptions for structured-data ingestion (Capability 1, Slice 1b).

Parsing UNTRUSTED spreadsheets is an attack surface (zip bombs, XXE, pathological
sizes). These make the parser's resource limits part of its contract. The route
maps `DatasetIngestError` (and subclasses) to 422; an unsupported file type is
rejected earlier with the shared `UnsupportedContentTypeError` (→415).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


class DatasetIngestError(Exception):
    """Base class for spreadsheet-ingestion failures. Mapped to HTTP 422."""


class EmptySpreadsheetError(DatasetIngestError):
    """The sheet has no rows (or no row at the requested header index)."""


class NoHeaderError(DatasetIngestError):
    """The header row exists but is entirely empty — no columns to detect."""


class SpreadsheetTooLargeError(DatasetIngestError):
    """The sheet exceeds the row or column cap for untrusted uploads."""


class SpreadsheetDecodeError(DatasetIngestError):
    """A CSV upload could not be decoded as UTF-8 (tried utf-8-sig)."""


class DuplicateDatasetNameError(Exception):
    """A same-name active dataset already exists for the tenant and the caller
    did not set `replace_dataset_id` or opt into a duplicate. Mapped to HTTP 409;
    carries the existing dataset's id/name so the UI can prompt replace-or-create.
    NOT a `DatasetIngestError` — this is a resolvable conflict, not a bad file."""

    def __init__(self, existing_id: UUID, existing_name: str) -> None:
        super().__init__(f"a dataset named {existing_name!r} already exists")
        self.existing_id = existing_id
        self.existing_name = existing_name

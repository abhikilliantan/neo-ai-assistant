"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { Database, Loader2, Table2, Upload } from "lucide-react";
import { useRef, useState } from "react";
import type { ApiErrorEnvelope, DatasetIngestResponse, DatasetSummary } from "@neo/shared-types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/cn";
import { formatRelative } from "@/lib/relative-time";
import { getDataset, ingestDataset, listDatasets } from "@/services/datasets";

// A same-name upload without a chosen replace comes back 409 with the existing
// dataset in `error.details` — surfaced as an inline replace-or-create prompt.
type DuplicateConflict = { id: string; name: string };

function duplicateConflict(err: unknown): DuplicateConflict | null {
  if (!axios.isAxiosError(err) || err.response?.status !== 409) return null;
  const body = err.response?.data as ApiErrorEnvelope | undefined;
  if (body?.error?.code !== "duplicate_dataset_name") return null;
  const d = body.error.details;
  if (!d || typeof d.existing_dataset_id !== "string") return null;
  return { id: d.existing_dataset_id, name: String(d.existing_dataset_name ?? "") };
}

// Spreadsheet types the backend accepts (.xlsx / .csv + their MIME types).
const ACCEPT =
  ".xlsx,.csv," + "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv";

export function DatasetsView() {
  return (
    <div className="space-y-6">
      <UploadCard />
      <DatasetList />
    </div>
  );
}

// --- upload -----------------------------------------------------------------

function UploadCard() {
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [sheetName, setSheetName] = useState("");
  const [headerRow, setHeaderRow] = useState(""); // 0-based; blank → backend default 0
  const [replaceId, setReplaceId] = useState(""); // "" → create new; else replace in place
  const [result, setResult] = useState<DatasetIngestResponse | null>(null);

  // Populates the "Replace existing dataset" select; shares the list query cache.
  const { data: datasets } = useQuery({ queryKey: ["datasets"], queryFn: listDatasets });

  const upload = useMutation({
    mutationFn: (override?: { replaceDatasetId?: string; allowDuplicateName?: boolean }) => {
      if (!file) throw new Error("no file");
      const headerRowIndex = headerRow.trim() === "" ? undefined : Number(headerRow);
      return ingestDataset({
        file,
        name,
        sheetName,
        headerRowIndex,
        replaceDatasetId: override?.replaceDatasetId ?? (replaceId || undefined),
        allowDuplicateName: override?.allowDuplicateName,
      });
    },
    onSuccess: (data) => {
      setResult(data);
      // Clear the form for the next upload; keep the success card visible.
      setFile(null);
      setName("");
      setSheetName("");
      setHeaderRow("");
      setReplaceId("");
      if (inputRef.current) inputRef.current.value = "";
      void queryClient.invalidateQueries({ queryKey: ["datasets"] });
    },
  });

  const conflict = upload.isError ? duplicateConflict(upload.error) : null;

  const headerRowInvalid =
    headerRow.trim() !== "" && (!Number.isInteger(Number(headerRow)) || Number(headerRow) < 0);
  const canSubmit = file != null && !headerRowInvalid && !upload.isPending;

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (canSubmit) upload.mutate(undefined); // plain submit; overrides come from the conflict prompt
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Upload a dataset</CardTitle>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" onSubmit={onSubmit} noValidate>
          <div className="space-y-1.5">
            <label htmlFor="dataset-file" className="text-sm font-medium text-foreground">
              Spreadsheet (.xlsx or .csv)
            </label>
            <input
              id="dataset-file"
              ref={inputRef}
              type="file"
              accept={ACCEPT}
              disabled={upload.isPending}
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className={cn(
                "block w-full text-sm text-muted-foreground",
                "file:mr-3 file:rounded-control file:border-0 file:bg-accent-grad",
                "file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-on-accent",
                "file:shadow-glow hover:file:brightness-110",
                "disabled:cursor-not-allowed disabled:opacity-50",
              )}
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <Field
              id="dataset-name"
              label="Name (optional)"
              placeholder="Defaults to filename"
              value={name}
              onChange={setName}
              disabled={upload.isPending}
            />
            <Field
              id="dataset-sheet"
              label="Sheet name (optional)"
              placeholder="First sheet"
              value={sheetName}
              onChange={setSheetName}
              disabled={upload.isPending}
            />
            <Field
              id="dataset-header"
              label="Header row (0-based)"
              placeholder="0"
              value={headerRow}
              onChange={setHeaderRow}
              disabled={upload.isPending}
              inputMode="numeric"
            />
          </div>
          {headerRowInvalid && (
            <p className="text-sm text-danger">Header row must be a whole number (0 or greater).</p>
          )}

          {datasets && datasets.length > 0 && (
            <div className="space-y-1.5">
              <label htmlFor="dataset-replace" className="text-sm font-medium text-foreground">
                Replace existing dataset (optional)
              </label>
              <select
                id="dataset-replace"
                value={replaceId}
                disabled={upload.isPending}
                onChange={(e) => setReplaceId(e.target.value)}
                className="block w-full rounded-control border border-glass-border bg-glass px-3 py-2 text-sm text-foreground disabled:cursor-not-allowed disabled:opacity-50"
              >
                <option value="">Create a new dataset</option>
                {datasets.map((d) => (
                  <option key={d.dataset_id} value={d.dataset_id}>
                    {d.name} ({d.row_count} rows)
                  </option>
                ))}
              </select>
              {replaceId && (
                <p className="text-sm text-muted-foreground">
                  Its columns and rows will be replaced with this file.
                </p>
              )}
            </div>
          )}

          <div className="flex items-center gap-3">
            <Button type="submit" disabled={!canSubmit}>
              {upload.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Upload className="h-4 w-4" />
              )}
              {upload.isPending ? "Uploading…" : "Upload"}
            </Button>
            {upload.isPending && (
              <span className="text-sm text-muted-foreground">
                Parsing the spreadsheet — this can take a few seconds.
              </span>
            )}
          </div>

          {conflict ? (
            <div className="space-y-2 rounded-card border border-accent/40 bg-glass-hi p-3">
              <p className="text-sm text-foreground">
                A dataset named “{conflict.name}” already exists — replace it or create a new one?
              </p>
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  disabled={upload.isPending}
                  onClick={() => upload.mutate({ replaceDatasetId: conflict.id })}
                >
                  Replace it
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  disabled={upload.isPending}
                  onClick={() => upload.mutate({ allowDuplicateName: true })}
                >
                  Create new
                </Button>
              </div>
            </div>
          ) : (
            upload.isError && (
              <p className="text-sm text-danger">{uploadErrorMessage(upload.error)}</p>
            )
          )}
        </form>

        {result && (
          <div className="mt-4 space-y-2 rounded-card border border-success/40 bg-success/10 p-3">
            <p className="text-sm font-medium text-foreground">
              Ingested “{result.name}” — {result.row_count} row
              {result.row_count === 1 ? "" : "s"}, {result.columns.length} column
              {result.columns.length === 1 ? "" : "s"}.
            </p>
            <div className="flex flex-wrap gap-1.5">
              {result.columns.map((c) => (
                <ColumnPill key={c.key} name={c.name} role={c.semantic_role} type={c.data_type} />
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Field({
  id,
  label,
  placeholder,
  value,
  onChange,
  disabled,
  inputMode,
}: {
  id: string;
  label: string;
  placeholder?: string;
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
  inputMode?: "numeric";
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="text-sm font-medium text-foreground">
        {label}
      </label>
      <Input
        id={id}
        value={value}
        placeholder={placeholder}
        disabled={disabled}
        inputMode={inputMode}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}

// --- list + detail ----------------------------------------------------------

function DatasetList() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { data, isLoading, isError } = useQuery({
    queryKey: ["datasets"],
    queryFn: listDatasets,
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Your datasets</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {isError && <p className="text-sm text-danger">Failed to load datasets.</p>}
        {data && data.length === 0 && (
          <div className="flex flex-col items-center gap-1 py-8 text-center">
            <Database className="h-8 w-8 text-muted-foreground" />
            <p className="text-sm font-medium">No datasets yet</p>
            <p className="text-sm text-muted-foreground">
              Upload a tracker or spreadsheet above to make it queryable by Neo.
            </p>
          </div>
        )}
        {data && data.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-glass-border text-left text-xs uppercase tracking-wide text-faint">
                  <th className="px-3 py-2 font-medium">Name</th>
                  <th className="px-3 py-2 font-medium">Rows</th>
                  <th className="px-3 py-2 font-medium">Sheet</th>
                  <th className="px-3 py-2 font-medium">Created</th>
                </tr>
              </thead>
              <tbody>
                {data.map((d) => (
                  <DatasetRow
                    key={d.dataset_id}
                    dataset={d}
                    selected={selectedId === d.dataset_id}
                    onSelect={() =>
                      setSelectedId((prev) => (prev === d.dataset_id ? null : d.dataset_id))
                    }
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}

        {selectedId && <DatasetColumns id={selectedId} />}
      </CardContent>
    </Card>
  );
}

function DatasetRow({
  dataset,
  selected,
  onSelect,
}: {
  dataset: DatasetSummary;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <tr
      onClick={onSelect}
      className={cn(
        "cursor-pointer border-b border-glass-border/60 transition-colors",
        selected ? "glass-hi" : "hover:bg-glass",
      )}
    >
      <td className="px-3 py-2 font-medium text-foreground">{dataset.name}</td>
      <td className="px-3 py-2 text-muted-foreground">{dataset.row_count}</td>
      <td className="px-3 py-2 text-muted-foreground">{dataset.sheet_name ?? "—"}</td>
      <td className="px-3 py-2 text-muted-foreground">{formatRelative(dataset.created_at)}</td>
    </tr>
  );
}

function DatasetColumns({ id }: { id: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["datasets", id],
    queryFn: () => getDataset(id),
  });

  return (
    <div className="rounded-card border border-glass-border bg-glass p-3">
      {isLoading && <p className="text-sm text-muted-foreground">Loading columns…</p>}
      {isError && <p className="text-sm text-danger">Failed to load columns.</p>}
      {data && (
        <div className="space-y-2">
          <p className="text-sm font-medium text-foreground">
            {data.name} — columns ({data.columns.length})
          </p>
          <div className="flex flex-wrap gap-1.5">
            {data.columns.map((c) => (
              <ColumnPill key={c.key} name={c.name} role={c.semantic_role} type={c.data_type} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ColumnPill({ name, role, type }: { name: string; role: string; type: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-control border border-glass-border bg-glass-hi px-2 py-1 text-xs">
      <Table2 className="h-3 w-3 text-faint" aria-hidden />
      <span className="font-medium text-foreground">{name}</span>
      <span className="font-mono text-faint">{type}</span>
      {role !== "none" && <span className="font-mono text-accent">{role}</span>}
    </span>
  );
}

// --- helpers ----------------------------------------------------------------

function uploadErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const status = err.response?.status;
    if (status === 413) return "This file is too large to upload.";
    if (status === 415) return "That file type isn’t supported — upload an .xlsx or .csv file.";
    if (status === 422)
      return "Neo couldn’t read that spreadsheet. Check the sheet name and header row, or that the file isn’t empty.";
    const body = err.response?.data as ApiErrorEnvelope | undefined;
    if (body?.error?.message) return body.error.message;
  }
  return "Upload failed. Please try again.";
}

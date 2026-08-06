"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { FileText, Loader2, Search, Trash2, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";
import type { ApiErrorEnvelope, Document, DocumentSearchResult } from "@neo/shared-types";
import { cn } from "@/lib/cn";
import { formatRelative } from "@/lib/relative-time";
import { GlowCard, SectionHeader } from "@/features/redesign/components";
import {
  deleteDocument,
  listDocuments,
  searchDocuments,
  uploadDocument,
} from "@/services/documents";

const MAX_UPLOAD_MB = 25;
const ACCEPT =
  ".pdf,.txt,.md,.docx,application/pdf,text/plain,text/markdown," +
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

// Browsers often report an empty File.type for .md (and sometimes .txt), which
// the backend's content-type allowlist rejects with 415. Re-stamp the part's
// type from the extension so a valid file isn't refused for a missing label.
const EXT_TYPE: Record<string, string> = {
  md: "text/markdown",
  markdown: "text/markdown",
  txt: "text/plain",
  pdf: "application/pdf",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
};
function withResolvedType(file: File): File {
  const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
  const wanted = EXT_TYPE[ext];
  return wanted && file.type !== wanted ? new File([file], file.name, { type: wanted }) : file;
}

export function DocumentsView() {
  return (
    <div className="mx-auto max-w-[1100px] space-y-6">
      <SectionHeader
        title="Documents"
        subtitle="Upload files so NEO can read and answer from them — with citations — in AI Chat."
      />
      <UploadAndList />
      <SearchCard />
    </div>
  );
}

// --- upload + list ----------------------------------------------------------

function UploadAndList() {
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["documents"],
    queryFn: listDocuments,
  });

  // Upload files sequentially (each runs a synchronous parse→chunk→embed on the
  // server, so parallel uploads would just contend). Invalidate once at the end.
  const upload = useMutation({
    mutationFn: async (files: File[]) => {
      for (const f of files) await uploadDocument(withResolvedType(f));
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["documents"] }),
  });

  const del = useMutation({
    mutationFn: (id: string) => deleteDocument(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents"] }),
  });

  function pick(list: FileList | null) {
    const files = list ? Array.from(list) : [];
    if (files.length) upload.mutate(files);
  }

  return (
    <GlowCard className="p-6">
      {/* Dropzone */}
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        multiple
        className="hidden"
        onChange={(e) => {
          pick(e.target.files);
          e.target.value = ""; // allow re-picking the same file after an error
        }}
        disabled={upload.isPending}
      />
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          if (!upload.isPending) pick(e.dataTransfer.files);
        }}
        disabled={upload.isPending}
        className={cn(
          "flex w-full flex-col items-center justify-center gap-2 rounded-xl border border-dashed px-6 py-10 text-center transition-colors",
          dragging
            ? "border-rd-cyan bg-rd-cyan/10"
            : "border-rd-border hover:border-rd-border-hover hover:bg-rd-panel/40",
          upload.isPending && "cursor-not-allowed opacity-60",
        )}
      >
        <span className="flex h-11 w-11 items-center justify-center rounded-full bg-rd-grad">
          <UploadCloud className="h-5 w-5 text-white" aria-hidden />
        </span>
        <span className="text-sm font-medium text-rd-heading">
          Drag & drop files, or <span className="text-rd-cyan">browse</span>
        </span>
        <span className="text-xs text-rd-muted">
          PDF, Word (.docx), Markdown (.md), or text (.txt) · up to {MAX_UPLOAD_MB} MB
        </span>
      </button>

      {upload.isPending && (
        <div className="mt-4 space-y-2">
          <div className="flex items-center gap-2 text-sm text-rd-body">
            <Loader2 className="h-4 w-4 shrink-0 animate-spin text-rd-cyan" aria-hidden />
            Uploading — parsing, chunking and embedding on the server…
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-rd-panel">
            <div className="h-full w-1/3 animate-pulse rounded-full bg-rd-grad" />
          </div>
        </div>
      )}
      {upload.isError && (
        <p className="mt-4 rounded-control border border-rd-rose/40 bg-rd-rose/10 px-3 py-2 text-sm text-rd-rose">
          {uploadErrorMessage(upload.error)}
        </p>
      )}

      {/* List */}
      <div className="mt-6">
        <p className="mb-3 text-sm font-semibold text-rd-heading">Your documents</p>
        {isLoading && <p className="text-sm text-rd-muted">Loading…</p>}
        {isError && <p className="text-sm text-rd-rose">Failed to load documents.</p>}
        {data && data.length === 0 && !upload.isPending && (
          <div className="flex flex-col items-center gap-1 rounded-control border border-rd-border bg-rd-panel/40 py-8 text-center">
            <FileText className="h-7 w-7 text-rd-muted" aria-hidden />
            <p className="text-sm font-medium text-rd-heading">No documents yet</p>
            <p className="text-sm text-rd-muted">
              Upload a file above to make it searchable by NEO.
            </p>
          </div>
        )}
        {data && data.length > 0 && (
          <ul className="space-y-2">
            {data.map((doc) => (
              <DocumentRow
                key={doc.id}
                doc={doc}
                onDelete={() => del.mutate(doc.id)}
                deleting={del.isPending && del.variables === doc.id}
              />
            ))}
          </ul>
        )}
      </div>
    </GlowCard>
  );
}

function DocumentRow({
  doc,
  onDelete,
  deleting,
}: {
  doc: Document;
  onDelete: () => void;
  deleting: boolean;
}) {
  const [confirming, setConfirming] = useState(false);
  return (
    <li className="flex items-start justify-between gap-3 rounded-control border border-rd-border bg-rd-panel/40 px-3 py-2.5">
      <div className="flex min-w-0 flex-1 items-start gap-3">
        <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-rd-border bg-rd-panel">
          <FileText className="h-4 w-4 text-rd-cyan" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-rd-heading">{doc.filename}</p>
          <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-rd-muted">
            <StatusPill status={doc.status} />
            <span>{shortType(doc.content_type)}</span>
            <span aria-hidden>·</span>
            <span>{formatBytes(doc.byte_size)}</span>
            <span aria-hidden>·</span>
            <span>
              {doc.chunk_count} chunk{doc.chunk_count === 1 ? "" : "s"}
            </span>
            <span aria-hidden>·</span>
            <span>{formatRelative(doc.created_at)}</span>
          </div>
        </div>
      </div>
      {confirming ? (
        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={onDelete}
            disabled={deleting}
            className="rounded-control border border-rd-rose/40 bg-rd-rose/10 px-2.5 py-1 text-xs font-medium text-rd-rose disabled:opacity-50"
          >
            {deleting ? "Deleting…" : "Confirm"}
          </button>
          <button
            type="button"
            onClick={() => setConfirming(false)}
            disabled={deleting}
            className="rounded-control px-2 py-1 text-xs text-rd-muted hover:text-rd-heading disabled:opacity-50"
          >
            Cancel
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setConfirming(true)}
          aria-label={`Delete ${doc.filename}`}
          className="shrink-0 rounded-control border border-rd-border p-1.5 text-rd-muted transition-colors hover:border-rd-rose/40 hover:text-rd-rose"
        >
          <Trash2 className="h-4 w-4" aria-hidden />
        </button>
      )}
    </li>
  );
}

function StatusPill({ status }: { status: string }) {
  const ready = /ready|complete|indexed|done/i.test(status);
  return (
    <span
      className={cn(
        "rounded-full border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide",
        ready
          ? "border-rd-green/40 bg-rd-green/10 text-rd-green"
          : "border-rd-amber/40 bg-rd-amber/10 text-rd-amber",
      )}
    >
      {status}
    </span>
  );
}

// --- search -----------------------------------------------------------------

function SearchCard() {
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState("");

  const { data, isFetching, isError } = useQuery({
    queryKey: ["documents", "search", submitted],
    queryFn: () => searchDocuments({ query: submitted }),
    enabled: submitted.length > 0,
  });

  return (
    <GlowCard className="p-6">
      <p className="mb-3 text-sm font-semibold text-rd-heading">Search documents</p>
      <form
        className="flex items-center gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          const q = query.trim();
          if (q) setSubmitted(q);
        }}
        noValidate
      >
        <div className="relative min-w-0 flex-1">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-rd-muted"
            aria-hidden
          />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask about anything in your documents…"
            aria-label="Search documents"
            className="h-11 w-full rounded-control border border-rd-border bg-rd-panel/60 pl-9 pr-3 text-sm text-rd-heading placeholder:text-rd-muted focus:border-rd-border-hover focus:outline-none focus:ring-2 focus:ring-rd-cyan/30"
          />
        </div>
        <button
          type="submit"
          disabled={query.trim() === ""}
          className="h-11 shrink-0 rounded-control bg-rd-grad px-4 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-40"
        >
          Search
        </button>
      </form>

      <div className="mt-4">
        {submitted === "" && (
          <p className="text-sm text-rd-muted">
            Semantic search across your organization&apos;s documents. NEO returns the passages it
            is most confident about, each with a citation.
          </p>
        )}
        {submitted !== "" && isFetching && <p className="text-sm text-rd-muted">Searching…</p>}
        {submitted !== "" && isError && (
          <p className="text-sm text-rd-rose">Search failed. Please try again.</p>
        )}
        {submitted !== "" && !isFetching && !isError && data && data.length === 0 && (
          <div className="rounded-control border border-rd-border bg-rd-panel/40 px-3 py-3 text-sm">
            <p className="font-medium text-rd-heading">No confident matches</p>
            <p className="text-rd-muted">
              NEO only shows passages it is reasonably sure about. Try rephrasing, or check the
              document was uploaded.
            </p>
          </div>
        )}
        {submitted !== "" && !isFetching && data && data.length > 0 && (
          <ul className="space-y-2">
            {data.map((r) => (
              <ResultRow
                key={`${r.document_id}:${r.position.char_start}-${r.position.char_end}`}
                result={r}
              />
            ))}
          </ul>
        )}
      </div>
    </GlowCard>
  );
}

function ResultRow({ result }: { result: DocumentSearchResult }) {
  return (
    <li className="space-y-2 rounded-control border border-rd-border bg-rd-panel/40 p-3">
      <p className="whitespace-pre-wrap break-words text-sm text-rd-body">{result.text}</p>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-rd-muted">
        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-rd-cyan/15 text-rd-cyan">
          <FileText className="h-3 w-3" aria-hidden />
        </span>
        <span className="font-medium text-rd-heading">{result.filename}</span>
        <span aria-hidden>·</span>
        {/* citation rendered VERBATIM from the API — the server owns the
            "p. 3 / section X" logic; the client never re-derives it. */}
        <span className="font-mono text-rd-cyan">{result.citation}</span>
        <span aria-hidden>·</span>
        <span>{Math.round(result.similarity * 100)}% match</span>
      </div>
    </li>
  );
}

// --- helpers ----------------------------------------------------------------

function uploadErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const status = err.response?.status;
    if (status === 413) return `This file is too large. The maximum is ${MAX_UPLOAD_MB} MB.`;
    if (status === 415)
      return "That file type isn’t accepted. Upload a PDF, Word (.docx), Markdown (.md), or text (.txt) file.";
    if (status === 422)
      return "NEO couldn’t read that file. It may be corrupt, empty, or password-protected.";
    const body = err.response?.data as ApiErrorEnvelope | undefined;
    if (body?.error?.message) return body.error.message;
  }
  return "Upload failed. Please try again.";
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(kb < 10 ? 1 : 0)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

function shortType(contentType: string): string {
  const map: Record<string, string> = {
    "application/pdf": "PDF",
    "text/plain": "Text",
    "text/markdown": "Markdown",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "Word",
  };
  return map[contentType] ?? contentType;
}

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { FileText, Loader2, Search, Upload } from "lucide-react";
import { useRef, useState } from "react";
import type { ApiErrorEnvelope, Document, DocumentSearchResult } from "@neo/shared-types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { formatRelative } from "@/lib/relative-time";
import {
  deleteDocument,
  listDocuments,
  searchDocuments,
  uploadDocument,
} from "@/services/documents";

// File types the backend accepts (mirrors the upload content-type allowlist).
const ACCEPT =
  ".pdf,.txt,.md,.docx,application/pdf,text/plain,text/markdown," +
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

export function DocumentsView() {
  return (
    <div className="space-y-6">
      <UploadAndListCard />
      <SearchCard />
    </div>
  );
}

// --- upload + list ----------------------------------------------------------

function UploadAndListCard() {
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["documents"],
    queryFn: listDocuments,
  });

  const upload = useMutation({
    mutationFn: (file: File) => uploadDocument(file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents"] }),
  });

  const del = useMutation({
    mutationFn: (id: string) => deleteDocument(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents"] }),
  });

  function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-picking the same file after an error
    if (file) upload.mutate(file);
  }

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>Your documents</CardTitle>
        <div>
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            className="hidden"
            onChange={onPick}
            disabled={upload.isPending}
          />
          <Button size="sm" onClick={() => inputRef.current?.click()} disabled={upload.isPending}>
            <Upload className="h-4 w-4" />
            Upload
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {upload.isPending && (
          <div className="flex items-center gap-2 rounded-md border bg-muted px-3 py-2 text-sm">
            <Loader2 className="h-4 w-4 shrink-0 animate-spin" />
            <span className="min-w-0 break-words">
              Uploading{upload.variables ? ` “${upload.variables.name}”` : ""}… parsing, chunking
              and embedding. This can take a few seconds.
            </span>
          </div>
        )}
        {upload.isError && (
          <p className="text-sm text-red-500">{uploadErrorMessage(upload.error)}</p>
        )}

        {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {isError && <p className="text-sm text-red-500">Failed to load documents.</p>}
        {data && data.length === 0 && !upload.isPending && (
          <div className="flex flex-col items-center gap-1 py-8 text-center">
            <FileText className="h-8 w-8 text-muted-foreground" />
            <p className="text-sm font-medium">No documents yet</p>
            <p className="text-sm text-muted-foreground">
              Upload a PDF, Word, text, or Markdown file to make it searchable by Neo.
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
      </CardContent>
    </Card>
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
    <li className="flex items-start justify-between gap-3 rounded-md border px-3 py-2">
      <div className="min-w-0 flex-1 space-y-1">
        <p className="break-words text-sm font-medium">{doc.filename}</p>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
          <span>{shortType(doc.content_type)}</span>
          <span>·</span>
          <span>{formatBytes(doc.byte_size)}</span>
          <span>·</span>
          <span>
            {doc.chunk_count} chunk{doc.chunk_count === 1 ? "" : "s"}
          </span>
          <span>·</span>
          <span>{formatRelative(doc.created_at)}</span>
        </div>
      </div>
      {confirming ? (
        <div className="flex shrink-0 items-center gap-2">
          <span className="text-xs text-muted-foreground">Delete?</span>
          <Button variant="outline" size="sm" onClick={onDelete} disabled={deleting}>
            {deleting ? "Deleting…" : "Confirm"}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setConfirming(false)}
            disabled={deleting}
          >
            Cancel
          </Button>
        </div>
      ) : (
        <Button
          variant="outline"
          size="sm"
          className="shrink-0"
          onClick={() => setConfirming(true)}
          aria-label={`Delete ${doc.filename}`}
        >
          Delete
        </Button>
      )}
    </li>
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

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (q) setSubmitted(q);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Search documents</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <form className="flex items-center gap-2" onSubmit={onSubmit} noValidate>
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask about anything in your documents…"
            aria-label="Search documents"
          />
          <Button type="submit" size="sm" disabled={query.trim() === ""}>
            <Search className="h-4 w-4" />
            Search
          </Button>
        </form>

        {submitted === "" && (
          <p className="text-sm text-muted-foreground">
            Search across all of your organization&apos;s documents. Neo returns the passages
            it&apos;s most confident about, with a citation for each.
          </p>
        )}
        {submitted !== "" && isFetching && (
          <p className="text-sm text-muted-foreground">Searching…</p>
        )}
        {submitted !== "" && isError && (
          <p className="text-sm text-red-500">Search failed. Please try again.</p>
        )}
        {submitted !== "" && !isFetching && !isError && data && data.length === 0 && (
          <div className="rounded-md border bg-muted px-3 py-3 text-sm">
            <p className="font-medium">No confident matches</p>
            <p className="text-muted-foreground">
              Neo only shows passages it&apos;s reasonably sure about, so weak matches are hidden.
              Try rephrasing, or check that the document has been uploaded.
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
      </CardContent>
    </Card>
  );
}

function ResultRow({ result }: { result: DocumentSearchResult }) {
  return (
    <li className="space-y-1 rounded-md border px-3 py-2">
      <p className="break-words text-sm">{result.text}</p>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
        <span className="font-medium text-foreground">{result.filename}</span>
        <span>·</span>
        {/* citation is rendered VERBATIM from the API — the server owns the
            "p. 3 / pp. 2-3 / section X" logic (DocumentPosition.render). No page
            or section string is ever derived on the client. */}
        <span>{result.citation}</span>
        <span>·</span>
        <span>{Math.round(result.similarity * 100)}% match</span>
      </div>
    </li>
  );
}

// --- helpers ----------------------------------------------------------------

function uploadErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const status = err.response?.status;
    if (status === 413) return "This file is too large to upload.";
    if (status === 415)
      return "That file type isn’t supported. Upload a PDF, Word (.docx), text, or Markdown file.";
    if (status === 422)
      return "Neo couldn’t read that file. It may be corrupt, empty, or password-protected.";
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

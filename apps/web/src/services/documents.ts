import type { Document, DocumentSearchRequest, DocumentSearchResult } from "@neo/shared-types";
import { http } from "@/services/http";

export async function listDocuments(): Promise<Document[]> {
  const { data } = await http.get<Document[]>("/api/v1/documents");
  return data;
}

export async function uploadDocument(file: File): Promise<Document> {
  const form = new FormData();
  form.append("file", file);
  // Content-Type unset so the browser adds multipart/form-data + boundary
  // (the http instance defaults to application/json, which would break the part).
  // Upload runs parse→chunk→embed server-side before responding — the slowest
  // call in the product — so allow well beyond the default 30s timeout.
  const { data } = await http.post<Document>("/api/v1/documents", form, {
    headers: { "Content-Type": undefined },
    timeout: 120_000,
  });
  return data;
}

export async function deleteDocument(id: string): Promise<void> {
  await http.delete(`/api/v1/documents/${id}`);
}

export async function searchDocuments(
  body: DocumentSearchRequest,
): Promise<DocumentSearchResult[]> {
  const { data } = await http.post<DocumentSearchResult[]>("/api/v1/documents/search", body);
  return data;
}

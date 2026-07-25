import type { DatasetDetail, DatasetIngestResponse, DatasetSummary } from "@neo/shared-types";
import { http } from "@/services/http";

export async function listDatasets(): Promise<DatasetSummary[]> {
  const { data } = await http.get<DatasetSummary[]>("/api/v1/datasets");
  return data;
}

export async function getDataset(id: string): Promise<DatasetDetail> {
  const { data } = await http.get<DatasetDetail>(`/api/v1/datasets/${id}`);
  return data;
}

export type IngestArgs = {
  file: File;
  name?: string;
  sheetName?: string;
  headerRowIndex?: number; // 0-based
};

export async function ingestDataset(args: IngestArgs): Promise<DatasetIngestResponse> {
  const form = new FormData();
  form.append("file", args.file);
  // Only append optional fields when set — omitted parts let the backend Form
  // defaults apply (name→filename, sheet_name→first sheet, header_row_index→0).
  if (args.name && args.name.trim()) form.append("name", args.name.trim());
  if (args.sheetName && args.sheetName.trim()) form.append("sheet_name", args.sheetName.trim());
  if (args.headerRowIndex != null) form.append("header_row_index", String(args.headerRowIndex));

  // Content-Type unset so the browser adds multipart/form-data + boundary (the
  // http instance defaults to application/json, which would break the part).
  // Parsing runs server-side before responding, so allow beyond the 30s default.
  const { data } = await http.post<DatasetIngestResponse>("/api/v1/datasets/ingest", form, {
    headers: { "Content-Type": undefined },
    timeout: 120_000,
  });
  return data;
}

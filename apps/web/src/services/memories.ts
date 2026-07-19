import type { Memory, Preference } from "@neo/shared-types";
import { http } from "@/services/http";

export async function listMemories(): Promise<Memory[]> {
  const { data } = await http.get<Memory[]>("/api/v1/memories");
  return data;
}

export async function deleteMemory(id: string): Promise<void> {
  await http.delete(`/api/v1/memories/${id}`);
}

export async function listPreferences(): Promise<Preference[]> {
  const { data } = await http.get<Preference[]>("/api/v1/preferences");
  return data;
}

export async function upsertPreference(key: string, value: unknown): Promise<Preference> {
  const { data } = await http.put<Preference>(`/api/v1/preferences/${encodeURIComponent(key)}`, {
    value,
  });
  return data;
}

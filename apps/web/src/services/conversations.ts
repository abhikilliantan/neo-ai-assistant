import type { ConversationDetail, ConversationSummary } from "@neo/shared-types";
import { http } from "@/services/http";

export async function listConversations(): Promise<ConversationSummary[]> {
  const { data } = await http.get<ConversationSummary[]>("/api/v1/conversations");
  return data;
}

export async function getConversation(id: string): Promise<ConversationDetail> {
  const { data } = await http.get<ConversationDetail>(`/api/v1/conversations/${id}`);
  return data;
}

export async function deleteConversation(id: string): Promise<void> {
  await http.delete(`/api/v1/conversations/${id}`);
}

export async function renameConversation(id: string, title: string): Promise<ConversationSummary> {
  const { data } = await http.patch<ConversationSummary>(`/api/v1/conversations/${id}`, {
    title,
  });
  return data;
}

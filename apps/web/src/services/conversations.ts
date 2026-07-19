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

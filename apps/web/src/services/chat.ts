import type { ChatMessage, ChatResponse } from "@neo/shared-types";
import { http } from "@/services/http";

export async function sendChat(messages: ChatMessage[]): Promise<ChatResponse> {
  const { data } = await http.post<ChatResponse>("/api/v1/chat", { messages });
  return data;
}

import type { Agent } from "@neo/shared-types";
import { http } from "@/services/http";

export async function listAgents(): Promise<Agent[]> {
  const { data } = await http.get<Agent[]>("/api/v1/agents");
  return data;
}

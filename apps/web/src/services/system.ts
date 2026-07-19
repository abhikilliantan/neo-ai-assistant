import type { HealthStatus } from "@neo/shared-types";
import { http } from "@/services/http";

export async function fetchHealth(): Promise<HealthStatus> {
  const { data } = await http.get<HealthStatus>("/health");
  return data;
}

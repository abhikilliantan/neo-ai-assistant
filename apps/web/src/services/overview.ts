import type { CompanyOverview, CompanySummary } from "@neo/shared-types";
import { http } from "@/services/http";

export async function listCompanies(): Promise<CompanySummary[]> {
  const { data } = await http.get<CompanySummary[]>("/api/v1/companies");
  return data;
}

export async function getCompanyOverview(companyId: string): Promise<CompanyOverview> {
  const { data } = await http.get<CompanyOverview>(`/api/v1/companies/${companyId}/overview`);
  return data;
}

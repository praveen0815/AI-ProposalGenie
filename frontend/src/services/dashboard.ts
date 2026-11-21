import { apiClient } from "./api";
import type { DashboardSummary, StatusCount, TrendPoint } from "../types/dashboard";

export async function getDashboardSummary(companyId: string): Promise<DashboardSummary> {
  const response = await apiClient.get<DashboardSummary>("/api/v1/dashboard/summary", { params: { company_id: companyId } });
  return response.data;
}

export async function getProposalTrends(companyId: string): Promise<TrendPoint[]> {
  const response = await apiClient.get<{ months: TrendPoint[] }>("/api/v1/dashboard/proposal-trends", {
    params: { company_id: companyId },
  });
  return response.data.months;
}

export async function getStatusDistribution(companyId: string): Promise<StatusCount[]> {
  const response = await apiClient.get<{ statuses: StatusCount[] }>("/api/v1/dashboard/status-distribution", {
    params: { company_id: companyId },
  });
  return response.data.statuses;
}

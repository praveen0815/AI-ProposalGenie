import { healthPath } from "../config";
import type { HealthReport } from "../types/health";
import { apiClient } from "./api";

export async function getHealth(): Promise<HealthReport> {
  const response = await apiClient.get<HealthReport>(healthPath);
  return response.data;
}

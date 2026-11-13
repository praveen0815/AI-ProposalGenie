export type ServiceStatus = "up" | "down";
export type OverallStatus = "ok" | "degraded";

export interface HealthCheck {
  name: string;
  status: ServiceStatus;
  latency_ms: number | null;
  detail: string | null;
}

export interface HealthReport {
  status: OverallStatus;
  app: string;
  version: string;
  environment: string;
  checked_at: string;
  checks: HealthCheck[];
}

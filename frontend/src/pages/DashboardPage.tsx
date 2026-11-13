import { RefreshCw } from "lucide-react";

import { CompanyBanner } from "../components/company/CompanyBanner";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { ErrorState } from "../components/ui/ErrorState";
import { PageHeader } from "../components/ui/PageHeader";
import { Spinner } from "../components/ui/Spinner";
import { StatusBadge } from "../components/ui/StatusBadge";
import { useHealthStatus } from "../context/HealthProvider";
import { apiBaseUrl, healthPath } from "../config";
import { formatLatency, formatTimestamp, serviceLabel } from "../lib/format";

export function DashboardPage() {
  const { report, error, loading, reload } = useHealthStatus();

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Overview"
        title="Dashboard"
        description="Live status reported by the ProposalGenie API. Counts and drafts are not shown because proposal storage is not part of this release."
        action={
          <Button variant="secondary" onClick={() => void reload()} disabled={loading}>
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} aria-hidden="true" />
            {loading && report ? "Refreshing" : "Refresh"}
          </Button>
        }
      />

      <CompanyBanner />

      {loading && !report && !error ? <Spinner label="Checking PostgreSQL, Redis, and the API" /> : null}
      {error && !report ? <ErrorState message={error} onRetry={() => void reload()} /> : null}

      {report ? (
        <div className="space-y-4" data-testid="health-status">
          <div className="flex flex-wrap items-center gap-3">
            <StatusBadge status={report.status} />
            <p className="text-sm text-slate-400">Last checked {formatTimestamp(report.checked_at)}</p>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {report.checks.map((check) => (
              <Card key={check.name}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="text-sm font-semibold text-white">{serviceLabel(check.name)}</h2>
                    <p className="mt-1 text-xs uppercase tracking-wide text-slate-500">{check.name}</p>
                  </div>
                  <StatusBadge status={check.status} />
                </div>
                <dl className="mt-5 grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <dt className="text-slate-500">Latency</dt>
                    <dd className="mt-1 font-medium tabular-nums text-slate-100" data-testid={`${check.name}-latency`}>
                      {formatLatency(check.latency_ms)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">Detail</dt>
                    <dd className="mt-1 font-medium text-slate-100" data-testid={`${check.name}-status`}>
                      {check.detail ?? "Reachable"}
                    </dd>
                  </div>
                </dl>
              </Card>
            ))}
          </div>
          <Card>
            <h2 className="text-sm font-semibold text-white">Application</h2>
            <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <dt className="text-slate-500">Name</dt>
                <dd className="mt-1 font-medium text-slate-100">{report.app}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Version</dt>
                <dd className="mt-1 font-medium text-slate-100">{report.version}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Environment</dt>
                <dd className="mt-1 font-medium text-slate-100">{report.environment}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Health endpoint</dt>
                <dd className="mt-1 break-all font-medium text-slate-100">
                  {apiBaseUrl}
                  {healthPath}
                </dd>
              </div>
            </dl>
          </Card>
        </div>
      ) : null}
    </div>
  );
}

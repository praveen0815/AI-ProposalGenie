import { Card } from "../components/ui/Card";
import { ErrorState } from "../components/ui/ErrorState";
import { PageHeader } from "../components/ui/PageHeader";
import { Spinner } from "../components/ui/Spinner";
import { StatusBadge } from "../components/ui/StatusBadge";
import { apiBaseUrl, healthPath } from "../config";
import { useHealthStatus } from "../context/HealthProvider";
import { formatLatency, serviceLabel } from "../lib/format";

export function SettingsPage() {
  const { report, error, loading, reload } = useHealthStatus();

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Configuration"
        title="Settings"
        description="Public client settings and the live service check. Database and Redis credentials stay on the server."
      />
      <Card>
        <h2 className="text-sm font-semibold text-white">Client</h2>
        <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-slate-500">API base URL</dt>
            <dd className="mt-1 break-all font-medium text-slate-100">{apiBaseUrl}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Health path</dt>
            <dd className="mt-1 font-medium text-slate-100">{healthPath}</dd>
          </div>
        </dl>
      </Card>

      {loading && !report && !error ? <Spinner label="Loading service status" /> : null}
      {error && !report ? <ErrorState message={error} onRetry={() => void reload()} /> : null}

      {report ? (
        <Card>
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-sm font-semibold text-white">Service status</h2>
            <StatusBadge status={report.status} />
          </div>
          <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-slate-500">Application</dt>
              <dd className="mt-1 font-medium text-slate-100">
                {report.app} {report.version}
              </dd>
            </div>
            <div>
              <dt className="text-slate-500">Environment</dt>
              <dd className="mt-1 font-medium text-slate-100">{report.environment}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Dependencies</dt>
              <dd className="mt-1 space-y-1 font-medium text-slate-100">
                {report.checks.map((check) => (
                  <p key={check.name}>
                    {serviceLabel(check.name)} · {check.status} · {formatLatency(check.latency_ms)}
                  </p>
                ))}
              </dd>
            </div>
          </dl>
        </Card>
      ) : null}
    </div>
  );
}

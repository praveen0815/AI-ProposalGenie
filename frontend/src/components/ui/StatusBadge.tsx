import type { OverallStatus, ServiceStatus } from "../../types/health";

type BadgeStatus = ServiceStatus | OverallStatus;

const labels: Record<BadgeStatus, string> = {
  ok: "Operational",
  degraded: "Degraded",
  up: "Up",
  down: "Down",
};

interface StatusBadgeProps {
  status: BadgeStatus;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const healthy = status === "ok" || status === "up";
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full px-2.5 py-1 text-xs font-semibold ${
        healthy ? "bg-emerald-400/10 text-emerald-300" : "bg-amber-400/10 text-amber-200"
      }`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${healthy ? "bg-emerald-300" : "bg-amber-300"}`} />
      {labels[status]}
    </span>
  );
}

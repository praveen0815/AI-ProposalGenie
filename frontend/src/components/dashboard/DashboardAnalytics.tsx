import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { BarChart3 } from "lucide-react";

import { useCompany } from "../../context/CompanyProvider";
import { apiErrorMessage } from "../../lib/apiError";
import { getDashboardSummary, getProposalTrends, getStatusDistribution } from "../../services/dashboard";
import type { DashboardSummary, StatusCount, TrendPoint } from "../../types/dashboard";
import { statusLabel } from "../../pages/proposalStatus";
import { Card } from "../ui/Card";
import { EmptyState } from "../ui/EmptyState";
import { ErrorState } from "../ui/ErrorState";
import { Spinner } from "../ui/Spinner";

export function DashboardAnalytics() {
  const { current, loading: companyLoading } = useCompany();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [trends, setTrends] = useState<TrendPoint[]>([]);
  const [statuses, setStatuses] = useState<StatusCount[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!current) {
      setSummary(null);
      return;
    }
    let active = true;
    setLoading(true);
    setError(null);
    Promise.all([getDashboardSummary(current.id), getProposalTrends(current.id), getStatusDistribution(current.id)])
      .then(([nextSummary, nextTrends, nextStatuses]) => {
        if (!active) {
          return;
        }
        setSummary(nextSummary);
        setTrends(nextTrends);
        setStatuses(nextStatuses.filter((item) => item.count > 0));
      })
      .catch((caught: unknown) => {
        if (active) {
          setError(apiErrorMessage(caught, "The dashboard could not be loaded."));
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [current]);

  if (companyLoading || loading) {
    return <Spinner label="Loading proposal analytics" />;
  }
  if (!current) {
    return (
      <EmptyState
        icon={BarChart3}
        title="No company selected"
        description="Create a company before proposal analytics can be shown."
      />
    );
  }
  if (error) {
    return <ErrorState title="Analytics unavailable" message={error} />;
  }
  if (!summary || summary.total === 0) {
    return (
      <EmptyState
        icon={BarChart3}
        title="No proposals yet"
        description="Counts, conversion, and budget totals appear here after the first proposal is created. Nothing on this page is sample data."
        action={
          <Link to="/proposals/new" className="text-sm font-semibold text-cyan-200">
            Create a proposal
          </Link>
        }
      />
    );
  }

  const cards = [
    ["Total", summary.total],
    ["Drafts", summary.draft],
    ["Awaiting review", summary.awaiting_review],
    ["Approved", summary.approved],
    ["Sent", summary.sent],
    ["Archived", summary.archived],
  ] as const;
  const conversion = summary.conversion_rate === null ? "Not enough approved proposals" : `${(Number(summary.conversion_rate) * 100).toFixed(1)}% sent`;

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {cards.map(([label, value]) => (
          <Card key={label}>
            <p className="text-sm text-slate-400">{label}</p>
            <p className="mt-2 text-3xl font-semibold tabular-nums text-white">{value}</p>
          </Card>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <h2 className="text-sm font-semibold text-white">Proposals created by month</h2>
          <div className="mt-4 h-60">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={trends}>
                <CartesianGrid stroke="rgba(255,255,255,0.08)" vertical={false} />
                <XAxis dataKey="month" tick={{ fill: "#94a3b8", fontSize: 11 }} interval={1} />
                <YAxis allowDecimals={false} tick={{ fill: "#94a3b8", fontSize: 11 }} width={28} />
                <Tooltip />
                <Bar dataKey="count" name="Proposals" fill="#67e8f9" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card>
          <h2 className="text-sm font-semibold text-white">Status distribution</h2>
          <div className="mt-4 h-60">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={statuses.map((item) => ({ status: statusLabel(item.status), count: item.count }))}>
                <CartesianGrid stroke="rgba(255,255,255,0.08)" vertical={false} />
                <XAxis dataKey="status" tick={{ fill: "#94a3b8", fontSize: 11 }} interval={0} />
                <YAxis allowDecimals={false} tick={{ fill: "#94a3b8", fontSize: 11 }} width={28} />
                <Tooltip />
                <Bar dataKey="count" name="Proposals" fill="#22d3ee" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <h2 className="text-sm font-semibold text-white">Conversion</h2>
          <p className="mt-2 text-2xl font-semibold text-white">{conversion}</p>
          <p className="mt-2 text-sm text-slate-400">Sent proposals divided by approved and sent proposals.</p>
        </Card>
        <Card>
          <h2 className="text-sm font-semibold text-white">Budgets</h2>
          {summary.budgets.length === 0 ? (
            <p className="mt-3 text-sm text-slate-400">No cost lines have been saved.</p>
          ) : (
            <ul className="mt-3 space-y-2">
              {summary.budgets.map((budget) => (
                <li key={budget.currency} className="flex items-center justify-between text-sm text-slate-200">
                  <span>{budget.currency}</span>
                  <span className="tabular-nums">
                    {budget.grand_total} · {budget.proposal_count} proposal{budget.proposal_count === 1 ? "" : "s"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
      <Card>
        <h2 className="text-sm font-semibold text-white">Recent activity</h2>
        <ul className="mt-3 space-y-2">
          {summary.recent.map((proposal) => (
            <li key={proposal.id}>
              <Link to={`/proposals/${proposal.id}`} className="flex flex-wrap items-center justify-between gap-2 text-sm text-slate-200 hover:text-cyan-100">
                <span>{proposal.title}</span>
                <span className="text-slate-400">
                  {statusLabel(proposal.status)} · {new Date(proposal.updated_at).toLocaleString()}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

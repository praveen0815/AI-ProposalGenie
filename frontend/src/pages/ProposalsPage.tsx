import { FileText } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { buttonClasses } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState } from "../components/ui/ErrorState";
import { PageHeader } from "../components/ui/PageHeader";
import { Spinner } from "../components/ui/Spinner";
import { useCompany } from "../context/CompanyProvider";
import { apiErrorMessage } from "../lib/apiError";
import { listProposals } from "../services/proposals";
import type { ProposalSummary } from "../types/proposal";
import { statusLabel } from "./proposalStatus";

export function ProposalsPage() {
  const { current, loading: companyLoading } = useCompany();
  const [proposals, setProposals] = useState<ProposalSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!current) {
      setProposals([]);
      return;
    }
    let active = true;
    setLoading(true);
    setError(null);
    listProposals(current.id)
      .then((rows) => {
        if (active) {
          setProposals(rows);
        }
      })
      .catch((caught: unknown) => {
        if (active) {
          setError(apiErrorMessage(caught, "The proposal list could not be loaded."));
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

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Library"
        title="Proposals"
        description="Drafts and generated proposals for the selected company."
        action={
          <Link to="/proposals/new" className={buttonClasses("primary")}>
            Create proposal
          </Link>
        }
      />
      {companyLoading || loading ? <Spinner label="Loading proposals" /> : null}
      {error ? <ErrorState message={error} /> : null}
      {!companyLoading && !loading && !error && proposals.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="No proposals yet"
          description="Create a proposal when you have a client, a project, and a company profile. The list stays empty until one is saved."
          action={
            <Link to="/proposals/new" className={buttonClasses("secondary")}>
              Create proposal
            </Link>
          }
        />
      ) : null}
      <ul className="space-y-3">
        {proposals.map((proposal) => (
          <li key={proposal.id}>
            <Link to={`/proposals/${proposal.id}`} className="block rounded-2xl border border-white/10 bg-[#101c31] px-5 py-4 hover:border-cyan-300/40">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-base font-semibold text-white">{proposal.title}</h2>
                  <p className="mt-1 text-sm text-slate-400">{proposal.client_name ?? "Client not recorded"}</p>
                </div>
                <span className="rounded-full bg-white/5 px-3 py-1 text-xs font-semibold text-cyan-100">{statusLabel(proposal.status)}</span>
              </div>
              {proposal.generation_error ? <p className="mt-3 text-sm text-rose-100">{proposal.generation_error}</p> : null}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

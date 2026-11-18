import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { AgentWorkflow } from "../components/proposals/AgentWorkflow";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { ErrorState } from "../components/ui/ErrorState";
import { PageHeader } from "../components/ui/PageHeader";
import { Spinner } from "../components/ui/Spinner";
import { apiErrorMessage } from "../lib/apiError";
import { generateProposal, getProposal } from "../services/proposals";
import type { ProposalDetail } from "../types/proposal";
import { statusLabel } from "./proposalStatus";

export function ProposalDetailPage() {
  const { proposalId } = useParams();
  const [proposal, setProposal] = useState<ProposalDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!proposalId) {
      return;
    }
    let active = true;
    setLoading(true);
    setError(null);
    getProposal(proposalId)
      .then((detail) => {
        if (active) {
          setProposal(detail);
        }
      })
      .catch((caught: unknown) => {
        if (active) {
          setError(apiErrorMessage(caught, "The proposal could not be loaded."));
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
  }, [proposalId]);

  async function regenerate() {
    if (!proposalId) {
      return;
    }
    setGenerating(true);
    setError(null);
    try {
      const detail = await generateProposal(proposalId);
      setProposal(detail);
    } catch (caught) {
      setError(apiErrorMessage(caught, "The proposal could not be generated."));
      const refreshed = await getProposal(proposalId).catch(() => null);
      if (refreshed) {
        setProposal(refreshed);
      }
    } finally {
      setGenerating(false);
    }
  }

  if (loading) {
    return <Spinner label="Loading proposal" />;
  }
  if (!proposal) {
    return <ErrorState title="Proposal unavailable" message={error ?? "The proposal could not be loaded."} />;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={statusLabel(proposal.status)}
        title={proposal.title}
        description={proposal.client_name ? `Prepared for ${proposal.client_name}.` : "Client name was not recorded."}
        action={
          <Button onClick={() => void regenerate()} disabled={generating}>
            {proposal.sections.length ? "Regenerate" : "Generate"}
          </Button>
        }
      />
      {generating ? (
        <p role="status" className="flex items-center gap-2 text-sm text-cyan-100">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-cyan-300/30 border-t-cyan-300" />
          Generating the proposal from the company profile and retrieved documents.
        </p>
      ) : null}
      {error ? <ErrorState title="Generation failed" message={error} /> : null}
      {proposal.generation_error && !error ? <ErrorState title="Generation failed" message={proposal.generation_error} /> : null}
      {proposalId ? (
        <AgentWorkflow
          proposalId={proposalId}
          onFinished={() => {
            getProposal(proposalId)
              .then(setProposal)
              .catch(() => undefined);
          }}
        />
      ) : null}
      <Card>
        <dl className="grid gap-4 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-slate-400">Model</dt>
            <dd className="mt-1 text-white">{proposal.model_name ?? "Not generated"}</dd>
          </div>
          <div>
            <dt className="text-slate-400">Company documents</dt>
            <dd className="mt-1 text-white">{retrievalLabel(proposal.retrieval_status)}</dd>
          </div>
          <div>
            <dt className="text-slate-400">Tokens</dt>
            <dd className="mt-1 text-white">{proposal.token_usage?.total_tokens ?? "Not reported"}</dd>
          </div>
        </dl>
        {proposal.source_references.length ? (
          <p className="mt-4 text-sm text-slate-300">
            Retrieved sources: {proposal.source_references.map((source) => source.filename).join(", ")}
          </p>
        ) : null}
      </Card>
      {proposal.sections.length === 0 ? (
        <Card>
          <h2 className="text-base font-semibold text-white">No sections yet</h2>
          <p className="mt-2 text-sm leading-6 text-slate-400">
            This draft is saved. Generate it when the company profile is ready. The page does not show sample proposal text.
          </p>
          <Link to="/company" className="mt-4 inline-block text-sm font-semibold text-cyan-200">
            Review company profile
          </Link>
        </Card>
      ) : (
        proposal.sections.map((section) => (
          <Card key={section.id}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-base font-semibold text-white">{section.title}</h2>
              <span className="rounded-full bg-white/5 px-3 py-1 text-xs font-semibold text-slate-300">AI draft</span>
            </div>
            {section.needs_review ? (
              <p className="mt-3 text-sm text-amber-100">Needs review{section.review_notes ? `: ${section.review_notes}` : "."}</p>
            ) : null}
            <p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-slate-200">{section.body}</p>
            {section.source_references.length ? (
              <p className="mt-4 text-xs text-cyan-100">
                Verified company documents: {section.source_references.map((source) => source.filename).join(", ")}
              </p>
            ) : null}
          </Card>
        ))
      )}
    </div>
  );
}

function retrievalLabel(status: string | null): string {
  if (status === "available") {
    return "Matching documents were retrieved";
  }
  if (status === "empty") {
    return "No matching documents";
  }
  if (status === "unavailable") {
    return "Retrieval was unavailable";
  }
  return "Not retrieved";
}

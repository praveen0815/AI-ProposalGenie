import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { AgentWorkflow } from "../components/proposals/AgentWorkflow";
import { ProposalExports } from "../components/proposals/ProposalExports";
import { ProposalWorkspace } from "../components/proposals/ProposalWorkspace";
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
      {proposal.sections.length === 0 && proposal.status !== "GENERATING" ? (
        <p className="text-sm text-slate-400">
          This draft has no sections yet. Add one below, or{" "}
          <Link to="/company" className="font-semibold text-cyan-200">
            review the company profile
          </Link>{" "}
          before generating.
        </p>
      ) : null}
      <ProposalExports proposalId={proposal.id} status={proposal.status} revision={proposal.content_revision} />
      <ProposalWorkspace proposal={proposal} onProposal={setProposal} />
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

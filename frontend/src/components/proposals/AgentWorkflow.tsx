import { useCallback, useEffect, useState } from "react";

import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { apiErrorMessage } from "../../lib/apiError";
import { getAgentHistory, getAgentStatus, resumeAgentWorkflow, runAgentWorkflow } from "../../services/agents";
import type { AgentEvent, AgentStatus } from "../../types/agent";

const nodeTone: Record<string, string> = {
  pending: "bg-white/5 text-slate-400",
  running: "bg-cyan-300/15 text-cyan-100",
  completed: "bg-emerald-300/10 text-emerald-100",
  failed: "bg-rose-400/10 text-rose-100",
};

interface AgentWorkflowProps {
  proposalId: string;
  onFinished: () => void;
}

export function AgentWorkflow({ proposalId, onFinished }: AgentWorkflowProps) {
  const [workflow, setWorkflow] = useState<AgentStatus | null>(null);
  const [history, setHistory] = useState<AgentEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const [next, events] = await Promise.all([getAgentStatus(proposalId), getAgentHistory(proposalId)]);
    setWorkflow(next);
    setHistory(events);
    return next;
  }, [proposalId]);

  useEffect(() => {
    let active = true;
    refresh().catch((caught: unknown) => {
      if (active) {
        setError(apiErrorMessage(caught, "The agent workflow could not be loaded."));
      }
    });
    return () => {
      active = false;
    };
  }, [refresh]);

  useEffect(() => {
    if (workflow?.status !== "RUNNING" && !busy) {
      return;
    }
    const timer = window.setInterval(() => {
      refresh().catch(() => undefined);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [workflow?.status, busy, refresh]);

  async function start(action: "run" | "resume") {
    setBusy(true);
    setError(null);
    try {
      const next = action === "run" ? await runAgentWorkflow(proposalId) : await resumeAgentWorkflow(proposalId);
      setWorkflow(next);
      await refresh();
      onFinished();
    } catch (caught) {
      setError(apiErrorMessage(caught, "The agent workflow could not be completed."));
      await refresh().catch(() => undefined);
    } finally {
      setBusy(false);
    }
  }

  const review = workflow?.review;
  const findings = [
    ...(review?.corrections ?? []),
    ...(review?.unsupported_claims ?? []),
    ...(review?.contradictions ?? []),
    ...(review?.unmet_requirements ?? []),
  ];

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-white">Agent workflow</h2>
          <p className="mt-1 text-sm text-slate-400">
            {workflow ? statusText(workflow) : "Loading the workflow status."}
          </p>
        </div>
        <div className="flex gap-2">
          {workflow?.status === "FAILED" ? (
            <Button onClick={() => void start("resume")} disabled={busy}>
              Resume
            </Button>
          ) : (
            <Button onClick={() => void start("run")} disabled={busy || workflow?.status === "RUNNING"}>
              {workflow?.status === "COMPLETED" ? "Run again" : "Run agents"}
            </Button>
          )}
        </div>
      </div>
      {busy || workflow?.status === "RUNNING" ? (
        <p role="status" className="mt-4 flex items-center gap-2 text-sm text-cyan-100">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-cyan-300/30 border-t-cyan-300" />
          {workflow?.current_node ? `Working on ${labelFor(workflow)}.` : "Starting the workflow."}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="mt-4 text-sm text-rose-100">
          {error}
        </p>
      ) : null}
      {workflow?.error && workflow.status === "FAILED" ? <p className="mt-3 text-sm text-rose-100">{workflow.error}</p> : null}
      <ol className="mt-5 space-y-2">
        {(workflow?.nodes ?? []).map((node) => (
          <li key={node.key} className="flex items-center justify-between gap-3 rounded-xl border border-white/10 px-3 py-2">
            <span className="text-sm text-white">{node.label}</span>
            <span className={`rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${nodeTone[node.status]}`}>{node.status}</span>
          </li>
        ))}
      </ol>
      {workflow?.external_research_status ? (
        <p className="mt-4 text-sm text-slate-300">External research: {researchText(workflow.external_research_status)}</p>
      ) : null}
      {workflow?.sources.length ? (
        <ul className="mt-3 space-y-1 text-sm text-cyan-100">
          {workflow.sources.map((source) => (
            <li key={`${source.kind}-${source.label}-${source.url}`}>
              {source.label}
              {source.url ? ` · ${source.url}` : ""}
            </li>
          ))}
        </ul>
      ) : null}
      {findings.length ? (
        <div className="mt-4">
          <h3 className="text-sm font-semibold text-amber-100">Review findings</h3>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-200">
            {findings.map((finding) => (
              <li key={finding}>{finding}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {workflow?.review_limit_reached ? (
        <p className="mt-3 text-sm text-amber-100">The review limit was reached. The saved draft still needs review.</p>
      ) : null}
      {history.length ? (
        <div className="mt-5 border-t border-white/10 pt-4">
          <h3 className="text-sm font-semibold text-white">Execution history</h3>
          <ul className="mt-2 space-y-1 text-sm text-slate-400">
            {history.map((event) => (
              <li key={event.id}>{event.message}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </Card>
  );
}

function statusText(workflow: AgentStatus): string {
  if (workflow.status === "NOT_STARTED") {
    return "This proposal has not been run through the agents.";
  }
  if (workflow.status === "RUNNING") {
    return "The workflow is running. Status comes from the server.";
  }
  if (workflow.status === "COMPLETED") {
    return "The workflow finished and saved the proposal sections.";
  }
  return "The workflow stopped and can be resumed.";
}

function labelFor(workflow: AgentStatus): string {
  return workflow.nodes.find((node) => node.key === workflow.current_node)?.label ?? "the current step";
}

function researchText(status: string): string {
  if (status === "not_configured") {
    return "no external source is configured, so none was queried.";
  }
  if (status === "completed") {
    return "the configured source returned results.";
  }
  if (status === "failed") {
    return "the configured source did not respond.";
  }
  return status;
}

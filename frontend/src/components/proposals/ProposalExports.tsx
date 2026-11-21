import { useEffect, useState } from "react";

import { apiErrorMessage } from "../../lib/apiError";
import { createExport, downloadExport, listExports } from "../../services/exports";
import type { ProposalStatus } from "../../types/proposal";
import type { ProposalExportRecord } from "../../types/export";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";

const exportable: ProposalStatus[] = ["REVIEW", "APPROVED", "SENT"];

interface ProposalExportsProps {
  proposalId: string;
  status: ProposalStatus;
  revision: number;
}

export function ProposalExports({ proposalId, status, revision }: ProposalExportsProps) {
  const [exports, setExports] = useState<ProposalExportRecord[]>([]);
  const [busy, setBusy] = useState<"pdf" | "docx" | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const allowed = exportable.includes(status);

  useEffect(() => {
    let active = true;
    listExports(proposalId)
      .then((rows) => {
        if (active) {
          setExports(rows);
        }
      })
      .catch((caught: unknown) => {
        if (active) {
          setMessage(apiErrorMessage(caught, "Exports could not be loaded."));
        }
      });
    return () => {
      active = false;
    };
  }, [proposalId, revision]);

  async function generate(format: "pdf" | "docx") {
    setBusy(format);
    setMessage(null);
    try {
      const created = await createExport(proposalId, format);
      setExports((current) => [created, ...current.filter((item) => item.id !== created.id)]);
    } catch (caught) {
      setMessage(apiErrorMessage(caught, `The ${format.toUpperCase()} could not be exported.`));
    } finally {
      setBusy(null);
    }
  }

  async function download(record: ProposalExportRecord) {
    setMessage(null);
    try {
      await downloadExport(proposalId, record.id, record.filename);
    } catch (caught) {
      setMessage(apiErrorMessage(caught, "The file could not be downloaded."));
    }
  }

  return (
    <Card>
      <h2 className="text-base font-semibold text-white">Export</h2>
      <p className="mt-2 text-sm text-slate-400">
        {allowed
          ? "PDF and Word files use the current proposal, budget, and company branding."
          : "Submit the proposal for review before exporting it."}
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button disabled={!allowed || busy !== null} onClick={() => void generate("pdf")}>
          {busy === "pdf" ? "Creating PDF" : "Export PDF"}
        </Button>
        <Button variant="secondary" disabled={!allowed || busy !== null} onClick={() => void generate("docx")}>
          {busy === "docx" ? "Creating DOCX" : "Export DOCX"}
        </Button>
      </div>
      {busy ? (
        <p role="status" className="mt-3 text-sm text-cyan-100">
          Preparing the document.
        </p>
      ) : null}
      {message ? <p className="mt-3 text-sm text-amber-100">{message}</p> : null}
      {exports.length === 0 ? <p className="mt-4 text-sm text-slate-400">No exports yet.</p> : null}
      <ul className="mt-4 space-y-2">
        {exports.map((record) => (
          <li key={record.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-white/10 px-3 py-2">
            <div>
              <p className="text-sm font-semibold text-white">{record.filename}</p>
              <p className="text-xs text-slate-400">
                {record.format} · {new Date(record.created_at).toLocaleString()}
                {record.stale || record.content_revision !== revision ? " · Proposal changed since this file" : ""}
              </p>
            </div>
            <Button variant="secondary" onClick={() => void download(record)}>
              Download
            </Button>
          </li>
        ))}
      </ul>
    </Card>
  );
}

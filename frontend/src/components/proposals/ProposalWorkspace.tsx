import { useEffect, useMemo, useRef, useState } from "react";

import { apiErrorMessage } from "../../lib/apiError";
import {
  applyApproval,
  compareVersions,
  confirmCost,
  createVersion,
  getCosts,
  listApprovals,
  listVersions,
  regenerateSection,
  restoreVersion,
  saveCosts,
  saveDraft,
  suggestCosts,
} from "../../services/workspace";
import type { ProposalDetail, ProposalStatus } from "../../types/proposal";
import type { ApprovalEvent, CostLine, CostSheet, VersionComparison, VersionSummary } from "../../types/workspace";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";

interface EditorSection {
  key: string;
  id?: string;
  title: string;
  body: string;
  aiBody: string | null;
  origin: string;
}

interface CostDraft {
  key: string;
  id?: string;
  name: string;
  category: string;
  quantity: string;
  unit: string;
  unitPrice: string;
  duration: string;
  taxPercent: string;
  discountPercent: string;
  source: "ESTIMATED" | "CONFIRMED";
  subtotal: string;
}

interface ProposalWorkspaceProps {
  proposal: ProposalDetail;
  onProposal: (proposal: ProposalDetail) => void;
}

export function ProposalWorkspace({ proposal, onProposal }: ProposalWorkspaceProps) {
  const [title, setTitle] = useState(proposal.title);
  const [sections, setSections] = useState<EditorSection[]>(() => sectionsFrom(proposal));
  const [revision, setRevision] = useState(proposal.content_revision);
  const [activeKey, setActiveKey] = useState(sections[0]?.key ?? "");
  const [dirty, setDirty] = useState(false);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "conflict" | "error">("idle");
  const savingRef = useRef(false);
  const [message, setMessage] = useState<string | null>(null);
  const [versions, setVersions] = useState<VersionSummary[]>([]);
  const [versionNote, setVersionNote] = useState("");
  const [leftId, setLeftId] = useState("");
  const [rightId, setRightId] = useState("");
  const [comparison, setComparison] = useState<VersionComparison | null>(null);
  const [suggestion, setSuggestion] = useState<{ sectionKey: string; body: string; previous: string } | null>(null);
  const [currency, setCurrency] = useState("USD");
  const [costs, setCosts] = useState<CostDraft[]>([]);
  const [totals, setTotals] = useState<CostSheet | null>(null);
  const [approvals, setApprovals] = useState<ApprovalEvent[]>([]);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setTitle(proposal.title);
    const next = sectionsFrom(proposal);
    setSections(next);
    setRevision(proposal.content_revision);
    setActiveKey((current) => (next.some((section) => section.key === current) ? current : next[0]?.key ?? ""));
    setDirty(false);
    setSaveState("idle");
  }, [proposal.id, proposal.content_revision]);

  useEffect(() => {
    let active = true;
    Promise.all([listVersions(proposal.id), getCosts(proposal.id), listApprovals(proposal.id)])
      .then(([versionList, sheet, events]) => {
        if (!active) {
          return;
        }
        setVersions(versionList);
        setLeftId(versionList[1]?.id ?? versionList[0]?.id ?? "");
        setRightId(versionList[0]?.id ?? "");
        applySheet(sheet, setCurrency, setCosts, setTotals);
        setApprovals(events);
      })
      .catch((caught: unknown) => {
        if (active) {
          setMessage(apiErrorMessage(caught, "The workspace could not be loaded."));
        }
      });
    return () => {
      active = false;
    };
  }, [proposal.id, proposal.content_revision, proposal.status]);

  useEffect(() => {
    if (!dirty || proposal.status === "GENERATING" || saveState === "conflict" || saveState === "error" || savingRef.current) {
      return;
    }
    const timer = window.setTimeout(() => {
      void persist("saved");
    }, 800);
    return () => window.clearTimeout(timer);
  }, [dirty, title, sections, revision, proposal.id, proposal.status, saveState]);

  const active = sections.find((section) => section.key === activeKey) ?? sections[0];
  const editable = proposal.status !== "GENERATING";
  const saveLabel = useMemo(() => {
    if (saveState === "saving") {
      return "Saving draft";
    }
    if (saveState === "conflict" || saveState === "error") {
      return "Save needs attention";
    }
    if (dirty) {
      return "Unsaved changes";
    }
    if (saveState === "saved") {
      return "Draft saved";
    }
    return "No unsaved changes";
  }, [dirty, saveState]);

  async function persist(nextState: "saved" | "idle") {
    if (savingRef.current) {
      return;
    }
    savingRef.current = true;
    setSaveState("saving");
    setMessage(null);
    try {
      const saved = await saveDraft(proposal.id, {
        title: title.trim(),
        expected_revision: revision,
        sections: sections.map((section) => ({
          id: section.id,
          title: section.title.trim() || "Untitled section",
          body: section.body,
        })),
      });
      setRevision(saved.content_revision);
      setSections(sectionsFrom(saved));
      setDirty(false);
      setSaveState(nextState);
      onProposal(saved);
    } catch (caught) {
      const text = apiErrorMessage(caught, "The draft could not be saved.");
      setSaveState(text.toLowerCase().includes("updated somewhere else") ? "conflict" : "error");
      setMessage(text);
    } finally {
      savingRef.current = false;
    }
  }

  function editSection(key: string, patch: Partial<EditorSection>) {
    setSections((current) => current.map((section) => (section.key === key ? { ...section, ...patch } : section)));
    setDirty(true);
    setSaveState("idle");
  }

  function moveSection(key: string, direction: -1 | 1) {
    setSections((current) => {
      const index = current.findIndex((section) => section.key === key);
      const target = index + direction;
      if (index < 0 || target < 0 || target >= current.length) {
        return current;
      }
      const next = [...current];
      const [item] = next.splice(index, 1);
      next.splice(target, 0, item);
      return next;
    });
    setDirty(true);
    setSaveState("idle");
  }

  async function regenerate(confirmOverwrite: boolean) {
    if (!active?.id) {
      setMessage("Save the section before regenerating it.");
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      const result = await regenerateSection(proposal.id, active.id, confirmOverwrite);
      if (!result.applied) {
        setSuggestion({ sectionKey: active.key, body: result.suggested_body, previous: result.previous_body });
        return;
      }
      setSuggestion(null);
      if (result.proposal) {
        onProposal(result.proposal);
      }
    } catch (caught) {
      setMessage(apiErrorMessage(caught, "The section could not be regenerated."));
    } finally {
      setBusy(false);
    }
  }

  async function saveVersion() {
    if (dirty) {
      await persist("idle");
    }
    setBusy(true);
    try {
      await createVersion(proposal.id, versionNote.trim() || "Saved from the editor");
      setVersionNote("");
      setVersions(await listVersions(proposal.id));
      setMessage(null);
    } catch (caught) {
      setMessage(apiErrorMessage(caught, "The version could not be saved."));
    } finally {
      setBusy(false);
    }
  }

  async function restore(versionId: string) {
    setBusy(true);
    try {
      onProposal(await restoreVersion(proposal.id, versionId));
      setVersions(await listVersions(proposal.id));
      setSuggestion(null);
    } catch (caught) {
      setMessage(apiErrorMessage(caught, "The version could not be restored."));
    } finally {
      setBusy(false);
    }
  }

  async function compare() {
    if (!leftId || !rightId) {
      return;
    }
    setBusy(true);
    try {
      setComparison(await compareVersions(proposal.id, leftId, rightId));
    } catch (caught) {
      setMessage(apiErrorMessage(caught, "The versions could not be compared."));
    } finally {
      setBusy(false);
    }
  }

  async function storeCosts() {
    setBusy(true);
    try {
      const sheet = await saveCosts(proposal.id, {
        currency,
        lines: costs
          .filter((line) => line.name.trim())
          .map((line) => ({
            ...(line.id ? { id: line.id } : {}),
            name: line.name,
            category: line.category || "General",
            quantity: line.quantity || "1",
            unit: line.unit || "unit",
            unit_price: line.unitPrice || "0",
            duration: line.duration || "1",
            tax_percent: line.taxPercent || "0",
            discount_percent: line.discountPercent || "0",
            source: line.source,
          })),
      });
      applySheet(sheet, setCurrency, setCosts, setTotals);
    } catch (caught) {
      setMessage(apiErrorMessage(caught, "The estimate could not be saved."));
    } finally {
      setBusy(false);
    }
  }

  async function suggest() {
    setBusy(true);
    try {
      const sheet = await suggestCosts(proposal.id, currency);
      applySheet(sheet, setCurrency, setCosts, setTotals);
    } catch (caught) {
      setMessage(apiErrorMessage(caught, "An estimate could not be suggested."));
    } finally {
      setBusy(false);
    }
  }

  async function approveLine(lineId: string) {
    setBusy(true);
    try {
      const sheet = await confirmCost(proposal.id, lineId);
      applySheet(sheet, setCurrency, setCosts, setTotals);
    } catch (caught) {
      setMessage(apiErrorMessage(caught, "The line could not be confirmed."));
    } finally {
      setBusy(false);
    }
  }

  async function decide(action: string) {
    setBusy(true);
    try {
      const updated = await applyApproval(proposal.id, action, comment);
      setComment("");
      onProposal(updated);
      setApprovals(await listApprovals(proposal.id));
    } catch (caught) {
      setMessage(apiErrorMessage(caught, "The status could not be changed."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <p role="status" className="text-sm font-medium text-cyan-100">
        {saveLabel}
      </p>
      {message ? <p className="text-sm text-amber-100">{message}</p> : null}
      <div className="grid gap-6 lg:grid-cols-[240px_minmax(0,1fr)]">
        <Card className="h-fit">
          <h2 className="text-sm font-semibold text-white">Sections</h2>
          <nav aria-label="Proposal sections" className="mt-3 space-y-1">
            {sections.map((section) => (
              <button
                key={section.key}
                type="button"
                aria-current={section.key === active?.key ? "true" : undefined}
                className={`w-full rounded-lg px-3 py-2 text-left text-sm ${section.key === active?.key ? "bg-cyan-300/15 text-cyan-100" : "text-slate-300 hover:bg-white/5"}`}
                onClick={() => setActiveKey(section.key)}
              >
                {section.title || "Untitled section"}
              </button>
            ))}
          </nav>
          <Button
            variant="secondary"
            className="mt-4 w-full"
            disabled={!editable}
            onClick={() => {
              const key = crypto.randomUUID();
              setSections((current) => [...current, { key, title: "New section", body: "", aiBody: null, origin: "custom" }]);
              setActiveKey(key);
              setDirty(true);
              setSaveState("idle");
            }}
          >
            Add section
          </Button>
        </Card>
        <Card>
          <label className="field-label" htmlFor="proposal-title">
            Proposal title
          </label>
          <input
            id="proposal-title"
            className="field"
            value={title}
            disabled={!editable}
            onChange={(event) => {
              setTitle(event.target.value);
              setDirty(true);
              setSaveState("idle");
            }}
          />
          {active ? (
            <div className="mt-5 space-y-3">
              <label className="field-label" htmlFor="section-title">
                Section title
              </label>
              <input
                id="section-title"
                className="field"
                value={active.title}
                disabled={!editable}
                onChange={(event) => editSection(active.key, { title: event.target.value })}
              />
              <label className="field-label" htmlFor="section-body">
                Section content
              </label>
              <textarea
                id="section-body"
                className="field min-h-56"
                value={active.body}
                disabled={!editable}
                onChange={(event) => editSection(active.key, { body: event.target.value, origin: active.origin === "custom" ? "custom" : "user" })}
              />
              <p className="text-xs text-slate-400">
                {active.origin === "ai" ? "AI draft" : active.origin === "custom" ? "Custom section" : "Edited by you"}
                {active.aiBody && active.aiBody !== active.body ? " · Different from the last AI draft" : ""}
              </p>
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" disabled={!editable} onClick={() => moveSection(active.key, -1)}>
                  Move up
                </Button>
                <Button variant="secondary" disabled={!editable} onClick={() => moveSection(active.key, 1)}>
                  Move down
                </Button>
                <Button variant="secondary" disabled={!editable || busy || !active.id} onClick={() => void regenerate(false)}>
                  Regenerate section
                </Button>
                <Button
                  variant="ghost"
                  disabled={!editable}
                  onClick={() => {
                    setSections((current) => current.filter((section) => section.key !== active.key));
                    setDirty(true);
                    setSaveState("idle");
                  }}
                >
                  Delete section
                </Button>
                <Button variant="secondary" disabled={!editable || !dirty} onClick={() => void persist("saved")}>
                  Save draft
                </Button>
              </div>
            </div>
          ) : (
            <p className="mt-4 text-sm text-slate-400">Add a section to start editing.</p>
          )}
          {suggestion && suggestion.sectionKey === active?.key ? (
            <div className="mt-5 grid gap-3 md:grid-cols-2">
              <div>
                <h3 className="text-sm font-semibold text-white">Your edit</h3>
                <p className="mt-2 whitespace-pre-wrap text-sm text-slate-300">{suggestion.previous}</p>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white">AI suggestion</h3>
                <p className="mt-2 whitespace-pre-wrap text-sm text-slate-300">{suggestion.body}</p>
              </div>
              <Button disabled={busy} onClick={() => void regenerate(true)}>
                Replace with AI suggestion
              </Button>
            </div>
          ) : null}
        </Card>
      </div>

      <Card>
        <h2 className="text-base font-semibold text-white">Version history</h2>
        <div className="mt-4 flex flex-col gap-3 sm:flex-row">
          <label className="field-label grow" htmlFor="version-note">
            Change description
            <input
              id="version-note"
              className="field"
              value={versionNote}
              placeholder="What changed in this version?"
              onChange={(event) => setVersionNote(event.target.value)}
            />
          </label>
          <Button className="sm:self-end" disabled={!editable || busy} onClick={() => void saveVersion()}>
            Save version
          </Button>
        </div>
        {versions.length === 0 ? <p className="mt-4 text-sm text-slate-400">No saved versions yet.</p> : null}
        <ul className="mt-4 space-y-2">
          {versions.map((version) => (
            <li key={version.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-white/10 px-3 py-2">
              <div>
                <p className="text-sm font-semibold text-white">Version {version.version_number}</p>
                <p className="text-xs text-slate-400">
                  {version.change_description || "No description"} · {new Date(version.created_at).toLocaleString()}
                </p>
              </div>
              <Button variant="secondary" disabled={!editable || busy} onClick={() => void restore(version.id)}>
                Restore
              </Button>
            </li>
          ))}
        </ul>
        {versions.length > 1 ? (
          <div className="mt-4 grid gap-3 md:grid-cols-[1fr_1fr_auto]">
            <label className="field-label" htmlFor="compare-left">
              Earlier version
              <select id="compare-left" className="field" value={leftId} onChange={(event) => setLeftId(event.target.value)}>
                {versions.map((version) => (
                  <option key={version.id} value={version.id}>
                    Version {version.version_number}
                  </option>
                ))}
              </select>
            </label>
            <label className="field-label" htmlFor="compare-right">
              Later version
              <select id="compare-right" className="field" value={rightId} onChange={(event) => setRightId(event.target.value)}>
                {versions.map((version) => (
                  <option key={version.id} value={version.id}>
                    Version {version.version_number}
                  </option>
                ))}
              </select>
            </label>
            <Button className="md:self-end" variant="secondary" disabled={busy} onClick={() => void compare()}>
              Compare
            </Button>
          </div>
        ) : null}
        {comparison ? (
          <ul className="mt-4 space-y-3">
            {comparison.changes.map((change) => (
              <li key={`${change.title}-${change.change}`} className="rounded-lg bg-white/5 p-3 text-sm">
                <p className="font-semibold text-white">
                  {change.title} · {change.change}
                </p>
                {change.left ? <p className="mt-2 whitespace-pre-wrap text-slate-400">{change.left}</p> : null}
                {change.right ? <p className="mt-2 whitespace-pre-wrap text-slate-200">{change.right}</p> : null}
              </li>
            ))}
          </ul>
        ) : null}
      </Card>

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-base font-semibold text-white">Budget</h2>
          <p className="text-sm text-slate-300">
            {totals ? `${totals.estimated_count} estimated · ${totals.confirmed_count} confirmed` : "No lines yet"}
          </p>
        </div>
        <p className="mt-2 text-sm text-slate-400">Suggested prices stay estimated until you confirm them.</p>
        <label className="field-label mt-4 max-w-xs" htmlFor="currency">
          Currency
          <input id="currency" className="field uppercase" maxLength={3} value={currency} onChange={(event) => setCurrency(event.target.value.toUpperCase())} />
        </label>
        <div className="mt-4 space-y-3">
          {costs.map((line) => (
            <div key={line.key} className="grid gap-2 rounded-lg border border-white/10 p-3 md:grid-cols-4">
              <label className="field-label">
                Resource
                <input className="field" value={line.name} onChange={(event) => updateCost(setCosts, line.key, { name: event.target.value })} />
              </label>
              <label className="field-label">
                Category
                <input className="field" value={line.category} onChange={(event) => updateCost(setCosts, line.key, { category: event.target.value })} />
              </label>
              <label className="field-label">
                Quantity
                <input className="field" inputMode="decimal" value={line.quantity} onChange={(event) => updateCost(setCosts, line.key, { quantity: event.target.value })} />
              </label>
              <label className="field-label">
                Unit
                <input className="field" value={line.unit} onChange={(event) => updateCost(setCosts, line.key, { unit: event.target.value })} />
              </label>
              <label className="field-label">
                Unit price
                <input className="field" inputMode="decimal" value={line.unitPrice} onChange={(event) => updateCost(setCosts, line.key, { unitPrice: event.target.value })} />
              </label>
              <label className="field-label">
                Duration
                <input className="field" inputMode="decimal" value={line.duration} onChange={(event) => updateCost(setCosts, line.key, { duration: event.target.value })} />
              </label>
              <label className="field-label">
                Tax %
                <input className="field" inputMode="decimal" value={line.taxPercent} onChange={(event) => updateCost(setCosts, line.key, { taxPercent: event.target.value })} />
              </label>
              <label className="field-label">
                Discount %
                <input className="field" inputMode="decimal" value={line.discountPercent} onChange={(event) => updateCost(setCosts, line.key, { discountPercent: event.target.value })} />
              </label>
              <p className="text-sm text-slate-300 md:col-span-2">
                {line.source === "CONFIRMED" ? "Confirmed" : "Estimated"}
                {line.subtotal ? ` · Subtotal ${line.subtotal}` : ""}
              </p>
              {line.source === "ESTIMATED" && line.id ? (
                <Button variant="secondary" disabled={busy} onClick={() => void approveLine(line.id!)}>
                  Confirm price
                </Button>
              ) : null}
            </div>
          ))}
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button
            variant="secondary"
            onClick={() =>
              setCosts((current) => [
                ...current,
                {
                  key: crypto.randomUUID(),
                  name: "",
                  category: "General",
                  quantity: "1",
                  unit: "unit",
                  unitPrice: "0",
                  duration: "1",
                  taxPercent: "0",
                  discountPercent: "0",
                  source: "CONFIRMED",
                  subtotal: "",
                },
              ])
            }
          >
            Add resource
          </Button>
          <Button variant="secondary" disabled={busy} onClick={() => void suggest()}>
            Suggest estimate
          </Button>
          <Button disabled={busy} onClick={() => void storeCosts()}>
            Save budget
          </Button>
        </div>
        {totals ? (
          <p className="mt-4 text-sm text-white">
            Grand total {totals.grand_total} {totals.currency ?? currency} · Tax {totals.tax} · Discount {totals.discount}
          </p>
        ) : null}
      </Card>

      <Card>
        <h2 className="text-base font-semibold text-white">Approval</h2>
        <label className="field-label mt-4" htmlFor="approval-comment">
          Comment
          <textarea id="approval-comment" className="field min-h-20" value={comment} onChange={(event) => setComment(event.target.value)} />
        </label>
        <div className="mt-4 flex flex-wrap gap-2">
          {actionsFor(proposal.status).map((action) => (
            <Button key={action.value} variant={action.value === "REJECT" ? "ghost" : "secondary"} disabled={busy} onClick={() => void decide(action.value)}>
              {action.label}
            </Button>
          ))}
        </div>
        <ul className="mt-4 space-y-2">
          {approvals.map((event) => (
            <li key={event.id} className="text-sm text-slate-300">
              {event.action.replaceAll("_", " ")} · {event.from_status} to {event.to_status}
              {event.comment ? ` · ${event.comment}` : ""} · {new Date(event.created_at).toLocaleString()}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

function sectionsFrom(proposal: ProposalDetail): EditorSection[] {
  return proposal.sections.map((section) => ({
    key: section.id,
    id: section.id,
    title: section.title,
    body: section.body,
    aiBody: section.ai_body,
    origin: section.origin || "user",
  }));
}

function applySheet(
  sheet: CostSheet,
  setCurrency: (value: string) => void,
  setCosts: (value: CostDraft[]) => void,
  setTotals: (value: CostSheet) => void,
) {
  if (sheet.currency) {
    setCurrency(sheet.currency);
  }
  setCosts(sheet.lines.map(costFromLine));
  setTotals(sheet);
}

function costFromLine(line: CostLine): CostDraft {
  return {
    key: line.id,
    id: line.id,
    name: line.name,
    category: line.category,
    quantity: line.quantity,
    unit: line.unit,
    unitPrice: line.unit_price,
    duration: line.duration,
    taxPercent: line.tax_percent,
    discountPercent: line.discount_percent,
    source: line.source,
    subtotal: line.subtotal,
  };
}

function updateCost(setCosts: (updater: (current: CostDraft[]) => CostDraft[]) => void, key: string, patch: Partial<CostDraft>) {
  setCosts((current) => current.map((line) => (line.key === key ? { ...line, ...patch } : line)));
}

function actionsFor(status: ProposalStatus): Array<{ value: string; label: string }> {
  if (status === "DRAFT" || status === "REJECTED") {
    return [
      { value: "SUBMIT", label: "Submit for review" },
      { value: "ARCHIVE", label: "Archive" },
    ];
  }
  if (status === "REVIEW") {
    return [
      { value: "APPROVE", label: "Approve" },
      { value: "REQUEST_CHANGES", label: "Request changes" },
      { value: "REJECT", label: "Reject" },
      { value: "ARCHIVE", label: "Archive" },
    ];
  }
  if (status === "APPROVED") {
    return [
      { value: "SEND", label: "Mark as sent" },
      { value: "ARCHIVE", label: "Archive" },
    ];
  }
  if (status === "SENT") {
    return [{ value: "ARCHIVE", label: "Archive" }];
  }
  return [];
}

import { Building2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { PageHeader } from "../components/ui/PageHeader";
import { Spinner } from "../components/ui/Spinner";
import { TextAreaField, TextField } from "../components/ui/TextField";
import { useCompany } from "../context/CompanyProvider";
import { apiErrorMessage } from "../lib/apiError";
import { createProposal, generateProposal } from "../services/proposals";

const steps = ["Client", "Requirements", "Budget and timeline", "Instructions", "Generate"];

interface Draft {
  client_name: string;
  client_industry: string;
  client_requirements: string;
  project_title: string;
  project_description: string;
  business_objectives: string;
  scope_of_work: string;
  deliverables: string;
  timeline: string;
  budget_range: string;
  currency: string;
  payment_terms: string;
  additional_instructions: string;
}

const emptyDraft: Draft = {
  client_name: "",
  client_industry: "",
  client_requirements: "",
  project_title: "",
  project_description: "",
  business_objectives: "",
  scope_of_work: "",
  deliverables: "",
  timeline: "",
  budget_range: "",
  currency: "",
  payment_terms: "",
  additional_instructions: "",
};

function filled(value: string): string | undefined {
  const trimmed = value.trim();
  return trimmed ? trimmed : undefined;
}

export function CreateProposalPage() {
  const { current, loading } = useCompany();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [error, setError] = useState<string | null>(null);
  const [phase, setPhase] = useState<"saving" | "generating" | null>(null);
  const [proposalId, setProposalId] = useState<string | null>(null);

  function update(field: keyof Draft, value: string) {
    setDraft((currentDraft) => ({ ...currentDraft, [field]: value }));
  }

  function next() {
    if (step === 0 && !draft.client_name.trim()) {
      setError("Enter the client name.");
      return;
    }
    if (step === 1 && (!draft.project_title.trim() || !draft.client_requirements.trim())) {
      setError("Enter a project title and the client requirements.");
      return;
    }
    setError(null);
    setStep((value) => Math.min(value + 1, steps.length - 1));
  }

  async function generate() {
    if (!current) {
      return;
    }
    setError(null);
    try {
      let id = proposalId;
      if (!id) {
        setPhase("saving");
        const created = await createProposal({
          company_id: current.id,
          client_name: draft.client_name.trim(),
          client_industry: filled(draft.client_industry),
          client_requirements: draft.client_requirements.trim(),
          project_title: draft.project_title.trim(),
          project_description: filled(draft.project_description),
          business_objectives: filled(draft.business_objectives),
          scope_of_work: filled(draft.scope_of_work),
          deliverables: filled(draft.deliverables),
          timeline: filled(draft.timeline),
          budget_range: filled(draft.budget_range),
          currency: filled(draft.currency)?.toUpperCase(),
          payment_terms: filled(draft.payment_terms),
          additional_instructions: filled(draft.additional_instructions),
        });
        id = created.id;
        setProposalId(id);
      }
      setPhase("generating");
      const generated = await generateProposal(id);
      navigate(`/proposals/${generated.id}`);
    } catch (caught) {
      setError(apiErrorMessage(caught, "The proposal could not be generated."));
    } finally {
      setPhase(null);
    }
  }

  if (loading) {
    return <Spinner label="Loading company" />;
  }
  if (!current) {
    return (
      <EmptyState
        icon={Building2}
        title="Create a company first"
        description="Proposal generation uses the selected company profile. Create a company, then return to this form."
        action={
          <Link to="/company/new" className="text-sm font-semibold text-cyan-200">
            Create company
          </Link>
        }
      />
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Draft"
        title="Create proposal"
        description="Each step saves nothing until you generate. Optional fields that you leave blank are marked for review instead of being invented."
      />
      <ol className="flex flex-wrap gap-2">
        {steps.map((label, index) => (
          <li
            key={label}
            className={`rounded-full px-3 py-1 text-xs font-semibold ${index === step ? "bg-cyan-300 text-slate-950" : "bg-white/5 text-slate-400"}`}
          >
            {index + 1}. {label}
          </li>
        ))}
      </ol>
      <Card>
        <div className="space-y-4">
          {step === 0 ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <TextField id="client-name" label="Client name" value={draft.client_name} onChange={(event) => update("client_name", event.target.value)} />
              <TextField id="client-industry" label="Client industry" value={draft.client_industry} onChange={(event) => update("client_industry", event.target.value)} />
            </div>
          ) : null}
          {step === 1 ? (
            <div className="space-y-4">
              <TextField id="project-title" label="Project title" value={draft.project_title} onChange={(event) => update("project_title", event.target.value)} />
              <TextAreaField id="project-description" label="Project description" rows={4} value={draft.project_description} onChange={(event) => update("project_description", event.target.value)} />
              <TextAreaField id="client-requirements" label="Client requirements" rows={5} value={draft.client_requirements} onChange={(event) => update("client_requirements", event.target.value)} />
              <TextAreaField id="objectives" label="Business objectives" rows={3} value={draft.business_objectives} onChange={(event) => update("business_objectives", event.target.value)} />
              <TextAreaField id="scope" label="Scope of work" rows={3} value={draft.scope_of_work} onChange={(event) => update("scope_of_work", event.target.value)} />
              <TextAreaField id="deliverables" label="Deliverables" rows={3} value={draft.deliverables} onChange={(event) => update("deliverables", event.target.value)} />
            </div>
          ) : null}
          {step === 2 ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <TextField id="timeline" label="Timeline" value={draft.timeline} onChange={(event) => update("timeline", event.target.value)} />
              <TextField id="budget" label="Budget range" value={draft.budget_range} onChange={(event) => update("budget_range", event.target.value)} />
              <TextField id="currency" label="Currency" value={draft.currency} maxLength={3} onChange={(event) => update("currency", event.target.value)} placeholder="USD" />
              <TextField id="payment-terms" label="Payment terms" value={draft.payment_terms} onChange={(event) => update("payment_terms", event.target.value)} />
            </div>
          ) : null}
          {step === 3 ? (
            <TextAreaField
              id="instructions"
              label="Additional instructions"
              rows={6}
              value={draft.additional_instructions}
              onChange={(event) => update("additional_instructions", event.target.value)}
            />
          ) : null}
          {step === 4 ? (
            <div className="space-y-3 text-sm leading-6 text-slate-300">
              <p>
                <span className="text-slate-400">Client. </span>
                {draft.client_name}
                {draft.client_industry.trim() ? ` · ${draft.client_industry}` : ""}
              </p>
              <p>
                <span className="text-slate-400">Project. </span>
                {draft.project_title}
              </p>
              <p className="whitespace-pre-wrap">{draft.client_requirements}</p>
              <p className="text-slate-400">
                Generation uses {current.name}, the details above, and any matching company documents. It does not invent missing budget, experience, or case studies.
              </p>
            </div>
          ) : null}
          {phase ? (
            <p role="status" className="flex items-center gap-2 text-sm text-cyan-100">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-cyan-300/30 border-t-cyan-300" />
              {phase === "saving" ? "Saving the proposal draft." : "Generating the proposal from the company profile and retrieved documents."}
            </p>
          ) : null}
          {error ? (
            <p role="alert" className="text-sm text-rose-100">
              {error}
            </p>
          ) : null}
          <div className="flex flex-wrap gap-3 border-t border-white/10 pt-4">
            {step > 0 ? (
              <Button type="button" variant="secondary" onClick={() => setStep((value) => value - 1)} disabled={phase !== null}>
                Back
              </Button>
            ) : null}
            {step < steps.length - 1 ? (
              <Button type="button" onClick={next}>
                Continue
              </Button>
            ) : (
              <Button type="button" onClick={() => void generate()} disabled={phase !== null}>
                {proposalId ? "Try generation again" : "Generate proposal"}
              </Button>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
}

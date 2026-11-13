import { useState } from "react";
import type { FormEvent } from "react";

import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";

export function CreateProposalPage() {
  const [notice, setNotice] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setNotice("Proposal generation is not available in this release.");
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Draft"
        title="Create proposal"
        description="The form shows the details a later release will collect. It does not call an AI service or save a proposal."
      />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(16rem,1fr)]">
        <Card>
          <form className="space-y-4" onSubmit={handleSubmit}>
            <div>
              <label className="field-label" htmlFor="proposal-title">
                Proposal title
              </label>
              <input id="proposal-title" name="title" className="field" placeholder="Website redesign" />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="field-label" htmlFor="client-name">
                  Client name
                </label>
                <input id="client-name" name="client" className="field" placeholder="Northwind Labs" />
              </div>
              <div>
                <label className="field-label" htmlFor="industry">
                  Industry
                </label>
                <input id="industry" name="industry" className="field" placeholder="Healthcare" />
              </div>
            </div>
            <div>
              <label className="field-label" htmlFor="summary">
                Opportunity summary
              </label>
              <textarea
                id="summary"
                name="summary"
                rows={6}
                className="field resize-y"
                placeholder="What the client needs, the timeline, and any constraints."
              />
            </div>
            <div className="flex flex-col gap-3 border-t border-white/10 pt-4 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-slate-400">Generation stays disabled until a later release.</p>
              <Button type="submit" disabled>
                Generate proposal
              </Button>
            </div>
            {notice ? (
              <p role="status" className="text-sm text-amber-100">
                {notice}
              </p>
            ) : null}
          </form>
        </Card>
        <Card>
          <h2 className="text-sm font-semibold text-white">Not included yet</h2>
          <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-400">
            <li>AI drafting</li>
            <li>Company knowledge retrieval</li>
            <li>Saving a proposal</li>
            <li>PDF export</li>
          </ul>
        </Card>
      </div>
    </div>
  );
}

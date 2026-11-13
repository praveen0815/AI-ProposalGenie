import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { TextAreaField, TextField } from "../components/ui/TextField";
import { useCompany } from "../context/CompanyProvider";
import { apiErrorMessage } from "../lib/apiError";
import { createCompany } from "../services/companies";

function emptyToNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

export function CompanyCreatePage() {
  const navigate = useNavigate();
  const { refresh, select } = useCompany();
  const [name, setName] = useState("");
  const [industry, setIndustry] = useState("");
  const [website, setWebsite] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const created = await createCompany({
        name,
        industry: emptyToNull(industry),
        website: emptyToNull(website),
        description: emptyToNull(description),
      });
      await refresh();
      select(created.id);
      navigate("/company", { replace: true });
    } catch (caught) {
      setError(apiErrorMessage(caught, "The company could not be created."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Company"
        title="Create company"
        description="You become the owner. Other people can be added after they register. No invitation email is sent."
      />
      <Card>
        <form className="space-y-4" onSubmit={(event) => void handleSubmit(event)}>
          <TextField id="company-name" label="Company name" required value={name} onChange={(event) => setName(event.target.value)} />
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField id="company-industry" label="Industry" value={industry} onChange={(event) => setIndustry(event.target.value)} />
            <TextField id="company-website" label="Website" value={website} onChange={(event) => setWebsite(event.target.value)} />
          </div>
          <TextAreaField
            id="company-description"
            label="Description"
            rows={4}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
          {error ? (
            <p role="alert" className="text-sm text-rose-200">
              {error}
            </p>
          ) : null}
          <Button type="submit" disabled={submitting}>
            {submitting ? "Creating" : "Create company"}
          </Button>
        </form>
      </Card>
    </div>
  );
}

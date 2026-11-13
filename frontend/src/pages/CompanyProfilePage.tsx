import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";

import { buttonClasses } from "../components/ui/Button";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState } from "../components/ui/ErrorState";
import { PageHeader } from "../components/ui/PageHeader";
import { Spinner } from "../components/ui/Spinner";
import { TextAreaField, TextField } from "../components/ui/TextField";
import { Building2 } from "lucide-react";
import { useCompany } from "../context/CompanyProvider";
import { apiErrorMessage } from "../lib/apiError";
import { updateCompany } from "../services/companies";
import type { Company } from "../types/company";

function emptyToNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function lines(value: string): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const line of value.split("\n")) {
    const trimmed = line.trim();
    if (trimmed && !seen.has(trimmed)) {
      seen.add(trimmed);
      result.push(trimmed);
    }
  }
  return result;
}

function formFromCompany(company: Company) {
  return {
    name: company.name,
    industry: company.industry ?? "",
    website: company.website ?? "",
    description: company.description ?? "",
    contactEmail: company.contact_email ?? "",
    contactPhone: company.contact_phone ?? "",
    addressLine1: company.address_line1 ?? "",
    addressLine2: company.address_line2 ?? "",
    city: company.city ?? "",
    region: company.region ?? "",
    postalCode: company.postal_code ?? "",
    country: company.country ?? "",
    services: company.services.join("\n"),
    expertise: company.expertise.join("\n"),
    brandTagline: company.brand_tagline ?? "",
    brandVoice: company.brand_voice ?? "",
    brandColor: company.brand_primary_color ?? "",
  };
}

export function CompanyProfilePage() {
  const { current, loading, error, refresh, replaceCurrent } = useCompany();
  const [form, setForm] = useState<ReturnType<typeof formFromCompany> | null>(null);
  const [loadedId, setLoadedId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const canEdit = current?.role === "OWNER" || current?.role === "ADMIN";

  useEffect(() => {
    if (!current || current.id === loadedId) {
      return;
    }
    setForm(formFromCompany(current));
    setLoadedId(current.id);
    setMessage(null);
    setFormError(null);
  }, [current, loadedId]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!current || !form || !canEdit) {
      return;
    }
    setSubmitting(true);
    setFormError(null);
    setMessage(null);
    try {
      const updated = await updateCompany(current.id, {
        name: form.name,
        industry: emptyToNull(form.industry),
        website: emptyToNull(form.website),
        description: emptyToNull(form.description),
        contact_email: emptyToNull(form.contactEmail),
        contact_phone: emptyToNull(form.contactPhone),
        address_line1: emptyToNull(form.addressLine1),
        address_line2: emptyToNull(form.addressLine2),
        city: emptyToNull(form.city),
        region: emptyToNull(form.region),
        postal_code: emptyToNull(form.postalCode),
        country: emptyToNull(form.country),
        services: lines(form.services),
        expertise: lines(form.expertise),
        brand_tagline: emptyToNull(form.brandTagline),
        brand_voice: emptyToNull(form.brandVoice),
        brand_primary_color: emptyToNull(form.brandColor),
      });
      replaceCurrent(updated);
      setForm(formFromCompany(updated));
      setMessage("Company profile saved.");
    } catch (caught) {
      setFormError(apiErrorMessage(caught, "The company profile could not be saved."));
    } finally {
      setSubmitting(false);
    }
  }

  if (loading && !current) {
    return <Spinner label="Loading company profile" />;
  }
  if (error && !current) {
    return <ErrorState title="Company profile is unavailable" message={error} onRetry={() => void refresh()} />;
  }
  if (!current || !form) {
    return (
      <EmptyState
        icon={Building2}
        title="No company selected"
        description="Create a company to edit its profile, contact details, and brand information."
        action={
          <Link to="/company/new" className={buttonClasses()}>
            Create company
          </Link>
        }
      />
    );
  }

  function update(field: keyof NonNullable<typeof form>, value: string) {
    setForm((existing) => (existing ? { ...existing, [field]: value } : existing));
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={current.role}
        title={current.name}
        description="Company details stay inside this workspace. Members of other companies cannot read them."
        action={
          <Link to="/company/settings" className={buttonClasses("secondary")}>
            Members
          </Link>
        }
      />
      <Card>
        <form className="space-y-6" onSubmit={(event) => void handleSubmit(event)}>
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField id="profile-name" label="Company name" required disabled={!canEdit} value={form.name} onChange={(event) => update("name", event.target.value)} />
            <TextField id="profile-industry" label="Industry" disabled={!canEdit} value={form.industry} onChange={(event) => update("industry", event.target.value)} />
            <TextField id="profile-website" label="Website" disabled={!canEdit} value={form.website} onChange={(event) => update("website", event.target.value)} />
            <TextField id="profile-email" label="Contact email" type="email" disabled={!canEdit} value={form.contactEmail} onChange={(event) => update("contactEmail", event.target.value)} />
            <TextField id="profile-phone" label="Contact phone" disabled={!canEdit} value={form.contactPhone} onChange={(event) => update("contactPhone", event.target.value)} />
          </div>
          <TextAreaField id="profile-description" label="Description" rows={4} disabled={!canEdit} value={form.description} onChange={(event) => update("description", event.target.value)} />
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField id="profile-line1" label="Address line 1" disabled={!canEdit} value={form.addressLine1} onChange={(event) => update("addressLine1", event.target.value)} />
            <TextField id="profile-line2" label="Address line 2" disabled={!canEdit} value={form.addressLine2} onChange={(event) => update("addressLine2", event.target.value)} />
            <TextField id="profile-city" label="City" disabled={!canEdit} value={form.city} onChange={(event) => update("city", event.target.value)} />
            <TextField id="profile-region" label="Region" disabled={!canEdit} value={form.region} onChange={(event) => update("region", event.target.value)} />
            <TextField id="profile-postal" label="Postal code" disabled={!canEdit} value={form.postalCode} onChange={(event) => update("postalCode", event.target.value)} />
            <TextField id="profile-country" label="Country" disabled={!canEdit} value={form.country} onChange={(event) => update("country", event.target.value)} />
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <TextAreaField id="profile-services" label="Services, one per line" rows={5} disabled={!canEdit} value={form.services} onChange={(event) => update("services", event.target.value)} />
            <TextAreaField id="profile-expertise" label="Expertise, one per line" rows={5} disabled={!canEdit} value={form.expertise} onChange={(event) => update("expertise", event.target.value)} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField id="profile-tagline" label="Brand tagline" disabled={!canEdit} value={form.brandTagline} onChange={(event) => update("brandTagline", event.target.value)} />
            <TextField id="profile-color" label="Brand color" disabled={!canEdit} value={form.brandColor} onChange={(event) => update("brandColor", event.target.value)} />
          </div>
          <TextAreaField id="profile-voice" label="Brand voice" rows={3} disabled={!canEdit} value={form.brandVoice} onChange={(event) => update("brandVoice", event.target.value)} />
          {formError ? <p role="alert" className="text-sm text-rose-200">{formError}</p> : null}
          {message ? <p role="status" className="text-sm text-emerald-200">{message}</p> : null}
          {canEdit ? (
            <Button type="submit" disabled={submitting}>
              {submitting ? "Saving" : "Save profile"}
            </Button>
          ) : (
            <p className="text-sm text-slate-400">Members can view this profile. Owners and admins can edit it.</p>
          )}
        </form>
      </Card>
    </div>
  );
}

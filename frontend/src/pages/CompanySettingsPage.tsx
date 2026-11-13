import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Building2 } from "lucide-react";
import { Link } from "react-router-dom";

import { buttonClasses } from "../components/ui/Button";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState } from "../components/ui/ErrorState";
import { PageHeader } from "../components/ui/PageHeader";
import { Spinner } from "../components/ui/Spinner";
import { TextField } from "../components/ui/TextField";
import { useCompany } from "../context/CompanyProvider";
import { apiErrorMessage } from "../lib/apiError";
import { addMember, listMembers, updateMemberRole } from "../services/companies";
import type { Member, MembershipRole } from "../types/company";

const roleLabels: Record<MembershipRole, string> = {
  OWNER: "Owner",
  ADMIN: "Admin",
  MEMBER: "Member",
};

export function CompanySettingsPage() {
  const { current, loading: companyLoading, error: companyError, refresh } = useCompany();
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<MembershipRole>("MEMBER");
  const [notice, setNotice] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const companyId = current?.id;
  const actorRole = current?.role;

  useEffect(() => {
    if (!companyId) {
      return;
    }
    let active = true;
    setLoading(true);
    setError(null);
    listMembers(companyId)
      .then((rows) => {
        if (active) {
          setMembers(rows);
        }
      })
      .catch((caught: unknown) => {
        if (active) {
          setError(apiErrorMessage(caught, "Members could not be loaded."));
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
  }, [companyId]);

  if (companyLoading && !current) {
    return <Spinner label="Loading company settings" />;
  }
  if (companyError && !current) {
    return <ErrorState title="Company settings are unavailable" message={companyError} onRetry={() => void refresh()} />;
  }
  if (!current || !companyId || !actorRole) {
    return (
      <EmptyState
        icon={Building2}
        title="No company selected"
        description="Create a company before managing members."
        action={
          <Link to="/company/new" className={buttonClasses()}>
            Create company
          </Link>
        }
      />
    );
  }

  const canAdd = actorRole === "OWNER" || actorRole === "ADMIN";
  const assignableRoles: MembershipRole[] = actorRole === "OWNER" ? ["MEMBER", "ADMIN", "OWNER"] : ["MEMBER"];

  async function handleAdd(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!companyId) {
      return;
    }
    setSubmitting(true);
    setNotice(null);
    setError(null);
    try {
      await addMember(companyId, email, role);
      setMembers(await listMembers(companyId));
      setEmail("");
      setRole("MEMBER");
      setNotice("Member added. No email was sent.");
    } catch (caught) {
      setError(apiErrorMessage(caught, "The member could not be added."));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRole(userId: string, nextRole: MembershipRole) {
    if (!companyId) {
      return;
    }
    setError(null);
    setNotice(null);
    try {
      const updated = await updateMemberRole(companyId, userId, nextRole);
      setMembers((rows) => rows.map((row) => (row.user_id === userId ? updated : row)));
      await refresh();
    } catch (caught) {
      setError(apiErrorMessage(caught, "The role could not be changed."));
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Access"
        title="Company settings"
        description="Add people who already have an account. Invitation email is not sent in this release."
        action={
          <Link to="/company" className={buttonClasses("secondary")}>
            Profile
          </Link>
        }
      />
      {loading ? <Spinner label="Loading members" /> : null}
      {error ? <ErrorState title="Membership update failed" message={error} /> : null}
      {notice ? <p role="status" className="text-sm text-emerald-200">{notice}</p> : null}
      <Card>
        <h2 className="text-sm font-semibold text-white">Members</h2>
        <ul className="mt-4 divide-y divide-white/10">
          {members.map((member) => (
            <li key={member.user_id} className="flex flex-col gap-3 py-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm font-medium text-white">{member.full_name}</p>
                <p className="text-xs text-slate-400">{member.email}</p>
              </div>
              {actorRole === "OWNER" ? (
                <label className="text-xs text-slate-400">
                  Role
                  <select
                    className="field mt-1"
                    value={member.role}
                    onChange={(event) => void handleRole(member.user_id, event.target.value as MembershipRole)}
                  >
                    {(["OWNER", "ADMIN", "MEMBER"] as MembershipRole[]).map((option) => (
                      <option key={option} value={option}>
                        {roleLabels[option]}
                      </option>
                    ))}
                  </select>
                </label>
              ) : (
                <span className="text-sm text-slate-300">{roleLabels[member.role]}</span>
              )}
            </li>
          ))}
        </ul>
      </Card>
      {canAdd ? (
        <Card>
          <h2 className="text-sm font-semibold text-white">Add a member</h2>
          <p className="mt-2 text-sm text-slate-400">The person must register before they can be added.</p>
          <form className="mt-4 grid gap-4 sm:grid-cols-[minmax(0,1fr)_12rem_auto] sm:items-end" onSubmit={(event) => void handleAdd(event)}>
            <TextField
              id="member-email"
              label="Email"
              type="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
            <div>
              <label className="field-label" htmlFor="member-role">
                Role
              </label>
              <select id="member-role" className="field" value={role} onChange={(event) => setRole(event.target.value as MembershipRole)}>
                {assignableRoles.map((option) => (
                  <option key={option} value={option}>
                    {roleLabels[option]}
                  </option>
                ))}
              </select>
            </div>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Adding" : "Add member"}
            </Button>
          </form>
        </Card>
      ) : null}
    </div>
  );
}

import { Building2 } from "lucide-react";
import { Link } from "react-router-dom";

import { useCompany } from "../../context/CompanyProvider";
import { buttonClasses } from "../ui/Button";
import { EmptyState } from "../ui/EmptyState";
import { ErrorState } from "../ui/ErrorState";
import { Spinner } from "../ui/Spinner";

export function CompanyBanner() {
  const { current, loading, error, refresh } = useCompany();

  if (loading && !current) {
    return <Spinner label="Loading your companies" />;
  }
  if (error && !current) {
    return <ErrorState title="Companies are unavailable" message={error} onRetry={() => void refresh()} />;
  }
  if (!current) {
    return (
      <EmptyState
        icon={Building2}
        title="No company yet"
        description="Create a company profile before inviting teammates. Proposal drafting is still a later release."
        action={
          <Link to="/company/new" className={buttonClasses()}>
            Create company
          </Link>
        }
      />
    );
  }

  return (
    <p className="text-sm text-slate-400">
      Working in{" "}
      <Link to="/company" className="font-medium text-cyan-200 hover:text-cyan-100">
        {current.name}
      </Link>
      .
    </p>
  );
}

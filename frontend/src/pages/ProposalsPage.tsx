import { FileText } from "lucide-react";
import { Link } from "react-router-dom";

import { buttonClasses } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { PageHeader } from "../components/ui/PageHeader";

export function ProposalsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Library"
        title="Proposals"
        description="Saved proposals will appear in this list. This release does not store or invent proposal records."
      />
      <EmptyState
        icon={FileText}
        title="No proposals yet"
        description="There is no proposals API in this release, so the list stays empty. Opening the create screen does not generate a draft."
        action={
          <Link to="/proposals/new" className={buttonClasses("secondary")}>
            Open create screen
          </Link>
        }
      />
    </div>
  );
}

import { Link } from "react-router-dom";

import { buttonClasses } from "../components/ui/Button";
import { PageHeader } from "../components/ui/PageHeader";

export function NotFoundPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="404"
        title="Page not found"
        description="That address is not part of the workspace."
      />
      <Link to="/" className={buttonClasses("secondary")}>
        Back to dashboard
      </Link>
    </div>
  );
}

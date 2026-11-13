import { Menu } from "lucide-react";
import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../../context/AuthProvider";
import { useHealthStatus } from "../../context/HealthProvider";
import { Button } from "../ui/Button";
import { pageTitle } from "./navigation";

interface TopBarProps {
  menuOpen: boolean;
  onMenu: () => void;
}

export function TopBar({ menuOpen, onMenu }: TopBarProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const title = pageTitle(location.pathname);
  const { logout } = useAuth();
  const { report, error, loading } = useHealthStatus();

  async function handleLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  useEffect(() => {
    document.title = `${title} · ProposalGenie`;
  }, [title]);

  let statusLabel = "Checking API";
  let statusClass = "text-slate-400";
  if (report) {
    statusLabel = report.status === "ok" ? "All services up" : "Services degraded";
    statusClass = report.status === "ok" ? "text-emerald-200" : "text-amber-200";
  } else if (!loading && error) {
    statusLabel = "API offline";
    statusClass = "text-rose-200";
  }

  return (
    <header className="sticky top-0 z-20 flex items-center justify-between gap-4 border-b border-white/10 bg-[#08111f]/85 px-4 py-3 backdrop-blur sm:px-6">
      <div className="flex min-w-0 items-center gap-3">
        <button
          type="button"
          className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-white/10 text-slate-200 hover:bg-white/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 lg:hidden"
          aria-label="Open navigation"
          aria-expanded={menuOpen}
          aria-controls="app-sidebar"
          onClick={onMenu}
        >
          <Menu className="h-5 w-5" aria-hidden="true" />
        </button>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-white">{title}</p>
          <p className="truncate text-xs text-slate-500">ProposalGenie</p>
        </div>
      </div>
      <div className="flex items-center gap-3 text-xs">
        <span className="hidden rounded-full border border-white/10 px-2.5 py-1 uppercase tracking-wide text-slate-400 sm:inline">
          {report?.environment ?? "—"}
        </span>
        <span data-testid="api-status" className={`font-medium ${statusClass}`}>
          {statusLabel}
        </span>
        <Button variant="ghost" onClick={() => void handleLogout()}>
          Log out
        </Button>
      </div>
    </header>
  );
}

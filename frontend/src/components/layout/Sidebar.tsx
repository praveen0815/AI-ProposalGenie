import { NavLink } from "react-router-dom";

import { useAuth } from "../../context/AuthProvider";
import { useCompany } from "../../context/CompanyProvider";
import { navItems } from "./navigation";

interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

function navClass(isActive: boolean): string {
  return [
    "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300",
    isActive ? "bg-cyan-300/10 text-cyan-50 ring-1 ring-cyan-300/30" : "text-slate-300 hover:bg-white/5 hover:text-white",
  ].join(" ");
}

export function Sidebar({ open, onClose }: SidebarProps) {
  const { user } = useAuth();
  const { companies, current, select } = useCompany();

  return (
    <>
      {open ? (
        <button
          type="button"
          className="fixed inset-0 z-30 bg-slate-950/70 lg:hidden"
          aria-label="Close navigation"
          onClick={onClose}
        />
      ) : null}
      <aside
        id="app-sidebar"
        className={`fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-white/10 bg-[#0c1728] transition-transform lg:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center gap-3 px-5 py-6">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-300/15 text-cyan-200">
            <svg viewBox="0 0 32 32" className="h-6 w-6" aria-hidden="true">
              <path
                d="M9 8.5h8.5L22.5 13v10.5a2 2 0 0 1-2 2h-11.5a2 2 0 0 1-2-2v-11.5a2 2 0 0 1 2-2z"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.7"
              />
              <path d="M17.5 8.5V13H22.5" fill="none" stroke="currentColor" strokeWidth="1.7" />
            </svg>
          </span>
          <span>
            <span className="block text-sm font-semibold text-white">ProposalGenie</span>
            <span className="block text-xs text-slate-400">Proposal workspace</span>
          </span>
        </div>
        <nav className="flex-1 space-y-1 overflow-y-auto px-3" aria-label="Primary">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end !== false}
                className={({ isActive }) => navClass(isActive)}
                onClick={onClose}
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                {item.label}
              </NavLink>
            );
          })}
        </nav>
        <div className="space-y-3 border-t border-white/10 px-4 py-4">
          {companies.length > 1 ? (
            <label className="block text-xs text-slate-400">
              Company
              <select
                className="field mt-1"
                value={current?.id ?? ""}
                onChange={(event) => select(event.target.value)}
              >
                {companies.map((company) => (
                  <option key={company.id} value={company.id}>
                    {company.name}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <p className="truncate px-1 text-xs text-slate-500">{user?.email ?? "Signed in"}</p>
        </div>
      </aside>
    </>
  );
}

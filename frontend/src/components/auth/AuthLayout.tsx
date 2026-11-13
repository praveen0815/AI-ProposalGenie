import type { ReactNode } from "react";
import { Link } from "react-router-dom";

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <Link to="/login" className="mb-6 flex items-center gap-3">
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
        </Link>
        {children}
      </div>
    </main>
  );
}

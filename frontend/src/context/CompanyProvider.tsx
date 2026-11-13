import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { useAuth } from "./AuthProvider";
import { apiErrorMessage } from "../lib/apiError";
import { listCompanies } from "../services/companies";
import type { Company } from "../types/company";

const companyKey = "proposalgenie.company_id";

interface CompanyContextValue {
  companies: Company[];
  current: Company | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  select: (companyId: string) => void;
  replaceCurrent: (company: Company) => void;
}

const CompanyContext = createContext<CompanyContextValue | null>(null);

export function CompanyProvider({ children }: { children: ReactNode }) {
  const { user, loading: authLoading } = useAuth();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const next = await listCompanies();
      setCompanies(next);
      setCurrentId((existing) => {
        const stored = existing ?? localStorage.getItem(companyKey);
        if (stored && next.some((company) => company.id === stored)) {
          return stored;
        }
        return next[0]?.id ?? null;
      });
    } catch (caught) {
      setCompanies([]);
      setCurrentId(null);
      setError(apiErrorMessage(caught, "Companies could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (authLoading) {
      return;
    }
    if (!user) {
      setCompanies([]);
      setCurrentId(null);
      setError(null);
      setLoading(false);
      return;
    }
    void refresh();
  }, [authLoading, user, refresh]);

  useEffect(() => {
    if (currentId) {
      localStorage.setItem(companyKey, currentId);
    }
  }, [currentId]);

  const select = useCallback((companyId: string) => {
    setCurrentId(companyId);
  }, []);

  const replaceCurrent = useCallback((company: Company) => {
    setCompanies((items) => items.map((item) => (item.id === company.id ? company : item)));
  }, []);

  const current = companies.find((company) => company.id === currentId) ?? null;
  const value = useMemo(
    () => ({ companies, current, loading, error, refresh, select, replaceCurrent }),
    [companies, current, loading, error, refresh, select, replaceCurrent],
  );

  return <CompanyContext.Provider value={value}>{children}</CompanyContext.Provider>;
}

export function useCompany(): CompanyContextValue {
  const value = useContext(CompanyContext);
  if (!value) {
    throw new Error("useCompany must be used within CompanyProvider");
  }
  return value;
}

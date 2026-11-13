import axios from "axios";
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

import { getHealth } from "../services/health";
import type { HealthReport } from "../types/health";

export interface HealthContextValue {
  report: HealthReport | null;
  error: string | null;
  loading: boolean;
  reload: () => Promise<void>;
}

const HealthContext = createContext<HealthContextValue | null>(null);

function toErrorMessage(caught: unknown): string {
  if (axios.isAxiosError(caught)) {
    const data: unknown = caught.response?.data;
    if (typeof data === "object" && data !== null && "message" in data) {
      const message = data.message;
      if (typeof message === "string" && message.length > 0) {
        return message;
      }
    }
    if (caught.code === "ERR_NETWORK" || caught.message === "Network Error") {
      return "The API is unreachable. Start the backend, then try again.";
    }
    if (caught.code === "ECONNABORTED") {
      return "The health check timed out. Confirm the API is running, then try again.";
    }
  }
  return "The health check could not be completed.";
}

export function HealthProvider({ children }: { children: ReactNode }) {
  const [report, setReport] = useState<HealthReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const requestId = useRef(0);

  const reload = useCallback(async () => {
    const id = requestId.current + 1;
    requestId.current = id;
    setLoading(true);
    setError(null);
    try {
      const next = await getHealth();
      if (requestId.current === id) {
        setReport(next);
      }
    } catch (caught) {
      if (requestId.current === id) {
        setReport(null);
        setError(toErrorMessage(caught));
      }
    } finally {
      if (requestId.current === id) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  return (
    <HealthContext.Provider value={{ report, error, loading, reload }}>
      {children}
    </HealthContext.Provider>
  );
}

export function useHealthStatus(): HealthContextValue {
  const value = useContext(HealthContext);
  if (!value) {
    throw new Error("useHealthStatus must be used within HealthProvider");
  }
  return value;
}

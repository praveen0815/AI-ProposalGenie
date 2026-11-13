const configured = import.meta.env.VITE_API_BASE_URL?.trim();

export const apiBaseUrl =
  configured && configured.length > 0 ? configured.replace(/\/$/, "") : "http://localhost:8000";

export const healthPath = "/api/v1/health";

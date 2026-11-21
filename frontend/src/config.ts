const configured = import.meta.env.VITE_API_BASE_URL;

export const apiBaseUrl =
  configured === undefined ? "http://localhost:8000" : configured.trim().replace(/\/$/, "");

export const healthPath = "/api/v1/health";

import axios from "axios";

export function apiErrorMessage(caught: unknown, fallback: string): string {
  if (axios.isAxiosError(caught)) {
    const data: unknown = caught.response?.data;
    if (typeof data === "object" && data !== null && "message" in data && typeof data.message === "string") {
      return data.message;
    }
    if (caught.code === "ERR_NETWORK" || caught.message === "Network Error") {
      return "The API is unreachable. Start the backend, then try again.";
    }
  }
  return fallback;
}

import axios from "axios";

import { apiBaseUrl } from "../config";
import { clearToken, readToken, unauthorizedEvent } from "./token";

export const apiClient = axios.create({
  baseURL: apiBaseUrl,
  timeout: 8000,
  headers: {
    Accept: "application/json",
  },
});

apiClient.interceptors.request.use((config) => {
  const token = readToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      const url = error.config?.url ?? "";
      const isLogin = url.includes("/auth/login") || url.includes("/auth/register");
      if (!isLogin) {
        clearToken();
        window.dispatchEvent(new Event(unauthorizedEvent));
      }
    }
    return Promise.reject(error);
  },
);

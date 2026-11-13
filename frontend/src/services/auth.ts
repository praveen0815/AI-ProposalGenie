import type { AuthUser, TokenResponse } from "../types/auth";
import { apiClient } from "./api";

export async function registerAccount(input: {
  email: string;
  full_name: string;
  password: string;
}): Promise<TokenResponse> {
  const response = await apiClient.post<TokenResponse>("/api/v1/auth/register", input);
  return response.data;
}

export async function loginAccount(input: { email: string; password: string }): Promise<TokenResponse> {
  const response = await apiClient.post<TokenResponse>("/api/v1/auth/login", input);
  return response.data;
}

export async function logoutAccount(): Promise<void> {
  await apiClient.post("/api/v1/auth/logout");
}

export async function getCurrentUser(): Promise<AuthUser> {
  const response = await apiClient.get<AuthUser>("/api/v1/auth/me");
  return response.data;
}

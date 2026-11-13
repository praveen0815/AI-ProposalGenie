const TOKEN_KEY = "proposalgenie.access_token";

export const unauthorizedEvent = "proposalgenie:unauthorized";

export function readToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function writeToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

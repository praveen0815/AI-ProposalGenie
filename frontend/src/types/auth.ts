export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: AuthUser;
}

import { useState } from "react";
import type { FormEvent } from "react";
import { Link, Navigate } from "react-router-dom";

import { AuthLayout } from "../components/auth/AuthLayout";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { TextField } from "../components/ui/TextField";
import { useAuth } from "../context/AuthProvider";
import { apiErrorMessage } from "../lib/apiError";

export function LoginPage() {
  const { user, loading, login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!loading && user) {
    return <Navigate to="/" replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
    } catch (caught) {
      setError(apiErrorMessage(caught, "Sign in failed."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout>
      <Card>
        <h1 className="text-xl font-semibold text-white">Sign in</h1>
        <p className="mt-2 text-sm text-slate-400">Use the email and password for your ProposalGenie account.</p>
        <form className="mt-6 space-y-4" onSubmit={(event) => void handleSubmit(event)}>
          <TextField
            id="login-email"
            label="Email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          <TextField
            id="login-password"
            label="Password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          {error ? (
            <p role="alert" className="text-sm text-rose-200">
              {error}
            </p>
          ) : null}
          <Button type="submit" className="w-full" disabled={submitting || loading}>
            {submitting ? "Signing in" : "Sign in"}
          </Button>
        </form>
        <p className="mt-4 text-sm text-slate-400">
          New here?{" "}
          <Link to="/register" className="font-medium text-cyan-200 hover:text-cyan-100">
            Create an account
          </Link>
        </p>
      </Card>
    </AuthLayout>
  );
}

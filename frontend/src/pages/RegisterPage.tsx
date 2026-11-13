import { useState } from "react";
import type { FormEvent } from "react";
import { Link, Navigate } from "react-router-dom";

import { AuthLayout } from "../components/auth/AuthLayout";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { TextField } from "../components/ui/TextField";
import { useAuth } from "../context/AuthProvider";
import { apiErrorMessage } from "../lib/apiError";

export function RegisterPage() {
  const { user, loading, register } = useAuth();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [created, setCreated] = useState(false);

  if (created) {
    return <Navigate to="/company/new" replace />;
  }
  if (!loading && user) {
    return <Navigate to="/" replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      await register(fullName, email, password);
      setCreated(true);
    } catch (caught) {
      setError(apiErrorMessage(caught, "Account creation failed."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout>
      <Card>
        <h1 className="text-xl font-semibold text-white">Create account</h1>
        <p className="mt-2 text-sm text-slate-400">Passwords are stored as hashes. This form does not create a company yet.</p>
        <form className="mt-6 space-y-4" onSubmit={(event) => void handleSubmit(event)}>
          <TextField
            id="register-name"
            label="Full name"
            autoComplete="name"
            required
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
          />
          <TextField
            id="register-email"
            label="Email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          <TextField
            id="register-password"
            label="Password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <TextField
            id="register-confirm"
            label="Confirm password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
          />
          {error ? (
            <p role="alert" className="text-sm text-rose-200">
              {error}
            </p>
          ) : null}
          <Button type="submit" className="w-full" disabled={submitting || loading}>
            {submitting ? "Creating account" : "Create account"}
          </Button>
        </form>
        <p className="mt-4 text-sm text-slate-400">
          Already registered?{" "}
          <Link to="/login" className="font-medium text-cyan-200 hover:text-cyan-100">
            Sign in
          </Link>
        </p>
      </Card>
    </AuthLayout>
  );
}

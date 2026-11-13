import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "../../context/AuthProvider";
import { Spinner } from "../ui/Spinner";

export function RequireAuth() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <Spinner label="Checking your session" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}

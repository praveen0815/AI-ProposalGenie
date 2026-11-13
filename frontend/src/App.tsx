import { Route, Routes } from "react-router-dom";

import { RequireAuth } from "./components/auth/RequireAuth";
import { AppShell } from "./components/layout/AppShell";
import { AuthProvider } from "./context/AuthProvider";
import { CompanyProvider } from "./context/CompanyProvider";
import { CompanyCreatePage } from "./pages/CompanyCreatePage";
import { CompanyKnowledgePage } from "./pages/CompanyKnowledgePage";
import { CompanyProfilePage } from "./pages/CompanyProfilePage";
import { CompanySettingsPage } from "./pages/CompanySettingsPage";
import { CreateProposalPage } from "./pages/CreateProposalPage";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { ProposalsPage } from "./pages/ProposalsPage";
import { RegisterPage } from "./pages/RegisterPage";
import { SettingsPage } from "./pages/SettingsPage";

export default function App() {
  return (
    <AuthProvider>
      <CompanyProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route element={<RequireAuth />}>
            <Route element={<AppShell />}>
              <Route index element={<DashboardPage />} />
              <Route path="proposals" element={<ProposalsPage />} />
              <Route path="proposals/new" element={<CreateProposalPage />} />
              <Route path="knowledge" element={<CompanyKnowledgePage />} />
              <Route path="company" element={<CompanyProfilePage />} />
              <Route path="company/new" element={<CompanyCreatePage />} />
              <Route path="company/settings" element={<CompanySettingsPage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Route>
        </Routes>
      </CompanyProvider>
    </AuthProvider>
  );
}

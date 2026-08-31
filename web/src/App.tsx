import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { getToken } from "./api";
import Layout from "./components/Layout";
import LoginPage from "./pages/LoginPage";
import AuthCallback from "./pages/AuthCallback";
import Dashboard from "./pages/Dashboard";
import MemoriesPage from "./pages/MemoriesPage";
import GraphPage from "./pages/GraphPage";
import SpacePage from "./pages/SpacePage";
import IngestPage from "./pages/IngestPage";
import ContradictionsPage from "./pages/ContradictionsPage";
import QueryPage from "./pages/QueryPage";
import MaintainPage from "./pages/MaintainPage";
import UsersPage from "./pages/UsersPage";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const loc = useLocation();
  if (!getToken()) return <Navigate to="/login" replace state={{ from: loc }} />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth/callback" element={<AuthCallback />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="memories" element={<MemoriesPage />} />
        <Route path="graph" element={<GraphPage />} />
        <Route path="space" element={<SpacePage />} />
        <Route path="ingest" element={<IngestPage />} />
        <Route path="contradictions" element={<ContradictionsPage />} />
        <Route path="query" element={<QueryPage />} />
        <Route path="maintain" element={<MaintainPage />} />
        <Route path="users" element={<UsersPage />} />
      </Route>
    </Routes>
  );
}

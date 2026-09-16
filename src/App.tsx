import { Suspense, lazy } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import Layout from "@/components/layout/Layout";
import { AuthProvider } from "@/context/AuthContext";
import { importWithReload } from "@/lazyImport";

const Landing = lazy(() => importWithReload(() => import("@/pages/Landing")));
const Login = lazy(() => importWithReload(() => import("@/pages/Login")));
const Dashboard = lazy(() => importWithReload(() => import("@/pages/Dashboard")));
const Analyze = lazy(() => importWithReload(() => import("@/pages/Analyze")));
const Incidents = lazy(() => importWithReload(() => import("@/pages/Incidents")));
// Filed as "Insights" (see src/pages/Insights.tsx) rather than "Analytics"
// -- ad-blocker/privacy filter lists commonly block any request path
// containing "analytics", which broke this exact route for real users.
const Analytics = lazy(() => importWithReload(() => import("@/pages/Insights")));
const Settings = lazy(() => importWithReload(() => import("@/pages/Settings")));

function PageFallback() {
  return (
    <div className="flex h-[60vh] items-center justify-center text-sm text-ink-faint">
      Loading…
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Suspense fallback={<PageFallback />}>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<Login />} />
            <Route element={<Layout />}>
              <Route
                path="/dashboard"
                element={
                  <ProtectedRoute>
                    <Dashboard />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/analyze"
                element={
                  <ProtectedRoute>
                    <Analyze />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/incidents"
                element={
                  <ProtectedRoute>
                    <Incidents />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/analytics"
                element={
                  <ProtectedRoute>
                    <Analytics />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/settings"
                element={
                  <ProtectedRoute>
                    <Settings />
                  </ProtectedRoute>
                }
              />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </AuthProvider>
    </BrowserRouter>
  );
}

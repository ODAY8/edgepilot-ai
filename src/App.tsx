import { Suspense, lazy } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Layout from "@/components/layout/Layout";
import { importWithReload } from "@/lazyImport";

const Landing = lazy(() => importWithReload(() => import("@/pages/Landing")));
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
      <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route element={<Layout />}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/analyze" element={<Analyze />} />
            <Route path="/incidents" element={<Incidents />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}

import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";
import { useLocation, Outlet } from "react-router-dom";
import ErrorBoundary from "@/components/common/ErrorBoundary";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";

const PAGE_META: Record<string, { title: string; description: string }> = {
  "/dashboard": {
    title: "Dashboard",
    description: "Real-time edge intelligence overview",
  },
  "/analyze": {
    title: "Analyze Environment",
    description: "Upload visual data and let EdgePilot identify meaningful events",
  },
  "/incidents": {
    title: "Incidents",
    description: "Full history of detected events across your sites",
  },
  "/analytics": {
    title: "Analytics",
    description: "Trends and performance across your edge network",
  },
  "/settings": {
    title: "Settings",
    description: "System information and configuration status",
  },
};

export default function Layout() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const meta = PAGE_META[location.pathname] ?? { title: "EdgePilot", description: "" };

  return (
    <div className="flex min-h-svh bg-base">
      <Sidebar mobileOpen={mobileOpen} onCloseMobile={() => setMobileOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar
          title={meta.title}
          description={meta.description}
          onOpenMobileNav={() => setMobileOpen(true)}
        />
        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.2, ease: "easeOut" }}
            >
              {/* Keyed by pathname so navigating away from a crashed page and
                  back remounts it fresh instead of staying stuck on the
                  error fallback. A crash here is scoped to the page content
                  only -- the sidebar and top bar above stay usable. */}
              <ErrorBoundary key={location.pathname}>
                <Outlet />
              </ErrorBoundary>
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}

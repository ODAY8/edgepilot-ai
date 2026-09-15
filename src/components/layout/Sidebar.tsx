import { motion } from "framer-motion";
import {
  Activity,
  BarChart3,
  LayoutDashboard,
  ScanSearch,
  Settings as SettingsIcon,
  ShieldAlert,
  X,
} from "lucide-react";
import type { ComponentType } from "react";
import { NavLink } from "react-router-dom";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/analyze", label: "Analyze", icon: ScanSearch },
  { to: "/incidents", label: "Incidents", icon: ShieldAlert },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
];

const SYSTEM_ITEMS = [{ to: "/settings", label: "Settings", icon: SettingsIcon }];

interface SidebarProps {
  mobileOpen: boolean;
  onCloseMobile: () => void;
}

interface SidebarNavItem {
  to: string;
  label: string;
  icon: ComponentType<{ size?: number; className?: string }>;
}

function SidebarNavLink({ item, onClick }: { item: SidebarNavItem; onClick: () => void }) {
  return (
    <NavLink
      to={item.to}
      onClick={onClick}
      className={({ isActive }) =>
        `group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors duration-150 ${
          isActive ? "text-ink" : "text-ink-dim hover:bg-surface-2 hover:text-ink"
        }`
      }
    >
      {({ isActive }) => (
        <>
          {isActive && (
            <motion.span
              layoutId="sidebar-active"
              className="absolute inset-0 rounded-lg border border-accent/30 bg-accent-soft"
              transition={{ type: "spring", stiffness: 400, damping: 32 }}
            />
          )}
          {isActive && (
            <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-accent shadow-[0_0_8px_rgba(91,124,250,0.9)]" />
          )}
          <item.icon size={17} className={`relative z-10 shrink-0 ${isActive ? "text-accent" : ""}`} />
          <span className="relative z-10">{item.label}</span>
        </>
      )}
    </NavLink>
  );
}

export default function Sidebar({ mobileOpen, onCloseMobile }: SidebarProps) {
  return (
    <>
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
          onClick={onCloseMobile}
          aria-hidden="true"
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-border bg-surface transition-transform duration-300 lg:static lg:z-auto lg:translate-x-0 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between gap-2 px-5 py-6">
          <div className="flex items-center gap-2.5">
            <div className="relative flex h-9 w-9 items-center justify-center rounded-lg bg-linear-to-br from-accent to-accent-2 shadow-[0_0_20px_-4px_rgba(91,124,250,0.7)]">
              <Activity size={18} className="text-white" strokeWidth={2.5} />
            </div>
            <div>
              <p className="text-sm font-bold leading-tight text-ink">EdgePilot</p>
              <p className="text-[10px] font-medium uppercase tracking-widest text-ink-faint">
                AI Infrastructure
              </p>
            </div>
          </div>
          <button
            onClick={onCloseMobile}
            aria-label="Close navigation"
            className="rounded-lg p-1.5 text-ink-dim hover:bg-surface-3 hover:text-ink lg:hidden"
          >
            <X size={18} />
          </button>
        </div>

        <nav className="flex-1 space-y-1 px-3 py-2" aria-label="Primary">
          {NAV_ITEMS.map((item) => (
            <SidebarNavLink key={item.to} item={item} onClick={onCloseMobile} />
          ))}

          <p className="px-3 pb-1 pt-5 text-[10px] font-semibold uppercase tracking-widest text-ink-faint">
            System
          </p>
          {SYSTEM_ITEMS.map((item) => (
            <SidebarNavLink key={item.to} item={item} onClick={onCloseMobile} />
          ))}
        </nav>

        <div className="border-t border-border px-4 py-4">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-ink-faint">
            System Status
          </p>
          <div className="flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-pulse-slow rounded-full bg-safe opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-safe" />
            </span>
            <p className="text-xs font-medium text-ink-dim">All systems operational</p>
          </div>
        </div>
      </aside>
    </>
  );
}

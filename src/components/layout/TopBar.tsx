import { Bell, Menu, User } from "lucide-react";
import { Link } from "react-router-dom";
import StatusIndicator from "@/components/common/StatusIndicator";

interface TopBarProps {
  title: string;
  description: string;
  onOpenMobileNav: () => void;
}

export default function TopBar({ title, description, onOpenMobileNav }: TopBarProps) {
  return (
    <header className="sticky top-0 z-30 flex items-center justify-between gap-4 border-b border-border bg-base/80 px-4 py-4 backdrop-blur-md sm:px-6 lg:px-8">
      <div className="flex items-center gap-3 min-w-0">
        <button
          onClick={onOpenMobileNav}
          aria-label="Open navigation"
          className="rounded-lg p-2 text-ink-dim hover:bg-surface-2 hover:text-ink lg:hidden"
        >
          <Menu size={20} />
        </button>
        <div className="min-w-0">
          <h1 className="truncate text-lg font-bold text-ink sm:text-xl">{title}</h1>
          <p className="truncate text-xs text-ink-faint sm:text-sm">{description}</p>
        </div>
      </div>

      <div className="flex items-center gap-2 sm:gap-4">
        <StatusIndicator label="System Operational" tone="safe" className="hidden md:inline-flex" />
        <Link
          to="/incidents"
          aria-label="View incidents"
          title="View incidents"
          className="relative rounded-lg p-2 text-ink-dim transition-colors hover:bg-surface-2 hover:text-ink"
        >
          <Bell size={18} />
        </Link>
        {/* Decorative only -- there's no user account system in EdgePilot,
            so this intentionally isn't a clickable menu with nothing behind
            it. */}
        <div
          aria-hidden="true"
          className="flex h-9 w-9 items-center justify-center rounded-full border border-border bg-surface-2 text-ink-dim"
        >
          <User size={16} />
        </div>
      </div>
    </header>
  );
}

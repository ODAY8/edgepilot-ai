import { motion } from "framer-motion";
import { Camera, Cpu, Eye, Radio, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import Button from "@/components/common/Button";
import { getSystemStatus, type SystemStatus } from "@/services/api";

// Live camera support can only ever be feature-detected on the client --
// the backend has no way to know what hardware/browser is viewing it.
// This checks whether the browser exposes the API at all; it says
// nothing about whether a camera device is actually attached or whether
// permission would be granted, so the label is worded accordingly.
function cameraApiSupported(): boolean {
  return typeof navigator !== "undefined" && typeof navigator.mediaDevices?.getUserMedia === "function";
}

type LoadState = "loading" | "loaded" | "error";

export default function Settings() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");

  const load = () => {
    setLoadState("loading");
    getSystemStatus()
      .then((s) => {
        setStatus(s);
        setLoadState("loaded");
      })
      .catch(() => {
        setStatus(null);
        setLoadState("error");
      });
  };

  useEffect(load, []);

  const cameraSupported = cameraApiSupported();

  const rows = [
    {
      label: "EdgePilot Version",
      value: loadState === "loaded" && status ? `v${status.version}` : loadState === "loading" ? "Loading…" : "Unavailable",
      icon: Cpu,
      tone: loadState === "loaded" ? "text-accent bg-accent-soft" : "text-ink-faint bg-surface-3",
    },
    {
      label: "Gemini Vision",
      value: loadState === "loaded" && status ? (status.visionEnabled ? "Enabled" : "Disabled") : loadState === "loading" ? "Loading…" : "Unknown",
      icon: Eye,
      tone:
        loadState === "loaded" && status
          ? status.visionEnabled
            ? "text-safe bg-safe/10"
            : "text-warn bg-warn/10"
          : "text-ink-faint bg-surface-3",
    },
    {
      label: "Groq Reasoning",
      value: loadState === "loaded" && status ? (status.reasoningEnabled ? "Enabled" : "Disabled") : loadState === "loading" ? "Loading…" : "Unknown",
      icon: Radio,
      tone:
        loadState === "loaded" && status
          ? status.reasoningEnabled
            ? "text-safe bg-safe/10"
            : "text-warn bg-warn/10"
          : "text-ink-faint bg-surface-3",
    },
    {
      label: "Live Camera",
      value: cameraSupported ? "Supported by this browser" : "Not supported by this browser",
      icon: Camera,
      tone: cameraSupported ? "text-safe bg-safe/10" : "text-warn bg-warn/10",
    },
  ];

  return (
    <div className="max-w-3xl space-y-6">
      <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
        <h2 className="text-xl font-bold text-ink sm:text-2xl">Settings</h2>
        <p className="mt-1 text-sm text-ink-dim">System information and configuration status.</p>
      </motion.div>

      <div className="rounded-2xl border border-border bg-surface p-5">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-semibold text-ink">API Status</p>
            <p className="mt-0.5 text-xs text-ink-faint">Connection to the EdgePilot backend</p>
          </div>
          <div className="flex items-center gap-3">
            <span
              className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide ${
                loadState === "loaded"
                  ? "bg-safe/10 text-safe"
                  : loadState === "loading"
                    ? "bg-surface-3 text-ink-faint"
                    : "bg-critical/10 text-critical"
              }`}
            >
              {loadState === "loaded" ? "Connected" : loadState === "loading" ? "Checking…" : "Unreachable"}
            </span>
            {loadState === "error" && (
              <Button variant="secondary" onClick={load} icon={<RefreshCw size={14} />}>
                Retry
              </Button>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {rows.map((row, i) => (
          <motion.div
            key={row.label}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: i * 0.05 }}
            className="rounded-2xl border border-border bg-surface p-4"
          >
            <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${row.tone}`}>
              <row.icon size={15} />
            </div>
            <p className="mt-3 text-sm font-bold text-ink">{row.value}</p>
            <p className="mt-0.5 text-[11px] font-medium uppercase tracking-wide text-ink-faint">{row.label}</p>
          </motion.div>
        ))}
      </div>

      <p className="text-xs text-ink-faint">
        No API keys or credentials are ever displayed here. Vision and reasoning status reflect whether the
        backend has the corresponding provider configured, not any usage or quota information.
      </p>
    </div>
  );
}

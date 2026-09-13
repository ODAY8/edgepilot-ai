import { motion } from "framer-motion";
import { Activity, AlertTriangle, HeartPulse, Video } from "lucide-react";
import { useEffect, useState } from "react";
import AIAnalysisCard from "@/components/dashboard/AIAnalysisCard";
import CameraPanel from "@/components/dashboard/CameraPanel";
import EventTimeline from "@/components/dashboard/EventTimeline";
import IncidentCard from "@/components/dashboard/IncidentCard";
import MonitoringState from "@/components/dashboard/MonitoringState";
import StatCard from "@/components/dashboard/StatCard";
import VisionDegradedState from "@/components/dashboard/VisionDegradedState";
import IncidentDetail from "@/components/incidents/IncidentDetail";
import StatusIndicator from "@/components/common/StatusIndicator";
import Modal from "@/components/common/Modal";
import ErrorState from "@/components/common/ErrorState";
import { acknowledgeIncident, escalateIncident, getDashboardStats, getIncidents, type LiveFrameResult } from "@/services/api";
import type { DashboardStats, Incident } from "@/data/types";

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Incident | null>(null);
  const [liveFrame, setLiveFrame] = useState<LiveFrameResult | null>(null);
  const [liveError, setLiveError] = useState<string | null>(null);

  const load = () => {
    let mounted = true;
    setLoading(true);
    setError(null);
    Promise.all([getDashboardStats(), getIncidents()])
      .then(([s, i]) => {
        if (!mounted) return;
        setStats(s);
        setIncidents(i);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : "Failed to load dashboard data.");
        setLoading(false);
      });
    return () => {
      mounted = false;
    };
  };

  useEffect(load, []);

  const primaryIncident = incidents.find((i) => i.status === "ACTIVE") ?? incidents[0];
  // While the live camera's most recent frame is normal_activity, the
  // camera panel already told us so via onFrameResult -- show that instead
  // of leaving whatever incident was last active looking like it's still
  // the current situation. Historical incidents are untouched either way.
  const showLiveMonitoring = liveFrame?.status === "NORMAL";
  // A failed live-analysis request takes priority over both the above and
  // the default incident display: a failure means the current state is
  // genuinely unknown, so neither "All Clear" nor a possibly-stale
  // incident should be presented as if they reflect the latest frame.
  const showLiveError = liveError !== null;

  const handleAcknowledge = async (id: string) => {
    try {
      const updated = await acknowledgeIncident(id);
      if (updated) setIncidents((prev) => prev.map((i) => (i.id === id ? updated : i)));
    } catch {
      // The action button re-enables itself; the operator can just retry.
    }
  };

  const handleEscalate = async (id: string) => {
    try {
      const updated = await escalateIncident(id);
      if (updated) setIncidents((prev) => prev.map((i) => (i.id === id ? updated : i)));
    } catch {
      // The action button re-enables itself; the operator can just retry.
    }
  };

  const handleLiveIncidentCreated = () => {
    // A live-camera frame just created a real incident -- refresh stats and
    // the incident list so the dashboard reflects it without a page reload.
    Promise.all([getDashboardStats(), getIncidents()])
      .then(([s, i]) => {
        setStats(s);
        setIncidents(i);
      })
      .catch(() => {
        // Non-critical background refresh; the next manual load/retry will catch up.
      });
  };

  if (error) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <ErrorState message={error} onRetry={load} />
      </div>
    );
  }

  if (loading || !stats) {
    return (
      <div className="flex h-[60vh] items-center justify-center text-ink-faint">
        <Activity className="animate-pulse" size={22} />
        <span className="ml-2 text-sm">Loading edge intelligence…</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <motion.div
        initial={{ opacity: 0, y: -6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end"
      >
        <div>
          <h2 className="text-xl font-bold text-ink sm:text-2xl">Good evening, Operator.</h2>
          <p className="mt-1 text-sm text-ink-dim">
            Here's what's happening across your environment.
          </p>
        </div>
        <StatusIndicator label="Live monitoring active" tone="safe" />
      </motion.div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          index={0}
          label="Total Events"
          value={stats.totalEvents.value}
          change={stats.totalEvents.change}
          icon={Activity}
          tone="accent"
        />
        <StatCard
          index={1}
          label="High Risk"
          value={stats.highRisk.value}
          change={stats.highRisk.change}
          icon={AlertTriangle}
          tone="critical"
        />
        <StatCard
          index={2}
          label="Active Inputs"
          value={stats.activeInputs.value}
          change={stats.activeInputs.change}
          icon={Video}
          tone="accent"
        />
        <StatCard
          index={3}
          label="System Health"
          value={stats.systemHealth.value}
          decimals={1}
          suffix="%"
          change={stats.systemHealth.change}
          icon={HeartPulse}
          tone="safe"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-5">
        <div className="space-y-2 xl:col-span-3">
          <div className="flex items-center justify-between px-1">
            <p className="text-xs font-semibold uppercase tracking-widest text-ink-faint">
              Camera / Edge Input
            </p>
          </div>
          <CameraPanel
            onIncidentCreated={handleLiveIncidentCreated}
            onFrameResult={setLiveFrame}
            onVisionError={setLiveError}
          />
        </div>
        <div className="space-y-2 xl:col-span-2">
          <div className="flex items-center justify-between px-1">
            <p className="text-xs font-semibold uppercase tracking-widest text-ink-faint">
              Current Incident
            </p>
          </div>
          {showLiveError ? (
            <VisionDegradedState message={liveError} />
          ) : showLiveMonitoring ? (
            <MonitoringState />
          ) : (
            primaryIncident && (
              <IncidentCard
                incident={primaryIncident}
                onAcknowledge={handleAcknowledge}
                onEscalate={handleEscalate}
              />
            )
          )}
        </div>
      </div>

      {!showLiveError && !showLiveMonitoring && primaryIncident && <AIAnalysisCard incident={primaryIncident} />}

      <EventTimeline incidents={incidents.slice(0, 6)} onSelect={setSelected} />

      <Modal isOpen={!!selected} onClose={() => setSelected(null)} title={selected?.event}>
        {selected && <IncidentDetail incident={selected} />}
      </Modal>
    </div>
  );
}

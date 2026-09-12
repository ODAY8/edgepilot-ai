import { motion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import IncidentDetail from "@/components/incidents/IncidentDetail";
import IncidentTable from "@/components/incidents/IncidentTable";
import Modal from "@/components/common/Modal";
import ErrorState from "@/components/common/ErrorState";
import type { Incident, RiskLevel } from "@/data/types";
import { acknowledgeIncident, escalateIncident, getIncidents } from "@/services/api";

type FilterKey = "ALL" | RiskLevel | "RESOLVED";

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: "ALL", label: "All" },
  { key: "HIGH", label: "High" },
  { key: "MEDIUM", label: "Medium" },
  { key: "LOW", label: "Low" },
  { key: "RESOLVED", label: "Resolved" },
];

export default function Incidents() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterKey>("ALL");
  const [selected, setSelected] = useState<Incident | null>(null);

  const load = () => {
    setLoading(true);
    setError(null);
    getIncidents()
      .then((data) => {
        setIncidents(data);
        setLoading(false);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load incidents.");
        setLoading(false);
      });
  };

  useEffect(load, []);

  const counts = useMemo(
    () => ({
      total: incidents.length,
      high: incidents.filter((i) => i.risk === "HIGH").length,
      medium: incidents.filter((i) => i.risk === "MEDIUM").length,
      low: incidents.filter((i) => i.risk === "LOW").length,
      resolved: incidents.filter((i) => i.status === "RESOLVED").length,
      active: incidents.filter((i) => i.status === "ACTIVE").length,
    }),
    [incidents],
  );

  const filtered = useMemo(() => {
    if (filter === "ALL") return incidents;
    if (filter === "RESOLVED") return incidents.filter((i) => i.status === "RESOLVED");
    return incidents.filter((i) => i.risk === filter);
  }, [incidents, filter]);

  const handleAcknowledge = async (id: string) => {
    try {
      const updated = await acknowledgeIncident(id);
      if (updated) {
        setIncidents((prev) => prev.map((i) => (i.id === id ? updated : i)));
        setSelected(updated);
      }
    } catch {
      // The action button re-enables itself; the operator can just retry.
    }
  };

  const handleEscalate = async (id: string) => {
    try {
      const updated = await escalateIncident(id);
      if (updated) {
        setIncidents((prev) => prev.map((i) => (i.id === id ? updated : i)));
        setSelected(updated);
      }
    } catch {
      // The action button re-enables itself; the operator can just retry.
    }
  };

  const summary = [
    { label: "Total", value: counts.total },
    { label: "High Risk", value: counts.high },
    { label: "Medium Risk", value: counts.medium },
    { label: "Low Risk", value: counts.low },
    { label: "Resolved", value: counts.resolved },
    { label: "Active", value: counts.active },
  ];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {summary.map((item, i) => (
          <motion.div
            key={item.label}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: i * 0.04 }}
            className="rounded-xl border border-border bg-surface p-4"
          >
            <p className="text-xl font-bold text-ink">{item.value}</p>
            <p className="mt-0.5 text-[11px] font-medium uppercase tracking-wide text-ink-faint">
              {item.label}
            </p>
          </motion.div>
        ))}
      </div>

      <div className="flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`rounded-full border px-3.5 py-1.5 text-xs font-semibold transition-colors duration-150 ${
              filter === f.key
                ? "border-accent/40 bg-accent-soft text-accent"
                : "border-border text-ink-dim hover:border-accent/30 hover:text-ink"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {error ? (
        <ErrorState message={error} onRetry={load} />
      ) : loading ? (
        <div className="rounded-2xl border border-border bg-surface p-12 text-center text-sm text-ink-faint">
          Loading incidents…
        </div>
      ) : (
        <IncidentTable incidents={filtered} onSelect={setSelected} />
      )}

      <Modal isOpen={!!selected} onClose={() => setSelected(null)} title={selected?.event}>
        {selected && (
          <IncidentDetail
            incident={selected}
            onAcknowledge={handleAcknowledge}
            onEscalate={handleEscalate}
          />
        )}
      </Modal>
    </div>
  );
}

import { motion } from "framer-motion";
import { ChevronRight } from "lucide-react";
import RiskBadge from "@/components/common/RiskBadge";
import type { Incident } from "@/data/types";
import { STATUS_LABEL } from "@/utils/format";

interface IncidentTableProps {
  incidents: Incident[];
  onSelect: (incident: Incident) => void;
}

const STATUS_DOT: Record<Incident["status"], string> = {
  ACTIVE: "bg-critical",
  ACKNOWLEDGED: "bg-warn",
  ESCALATED: "bg-accent",
  RESOLVED: "bg-safe",
};

export default function IncidentTable({ incidents, onSelect }: IncidentTableProps) {
  if (incidents.length === 0) {
    return (
      <div className="rounded-2xl border border-border bg-surface p-12 text-center">
        <p className="text-sm text-ink-faint">No incidents match the selected filter.</p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-surface">
      {/* Desktop table */}
      <div className="hidden overflow-x-auto lg:block">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-border text-[11px] font-semibold uppercase tracking-widest text-ink-faint">
              <th className="px-5 py-3">Time</th>
              <th className="px-5 py-3">Event</th>
              <th className="px-5 py-3">Location</th>
              <th className="px-5 py-3">Risk</th>
              <th className="px-5 py-3">Confidence</th>
              <th className="px-5 py-3">Status</th>
              <th className="px-5 py-3" />
            </tr>
          </thead>
          <tbody>
            {incidents.map((incident, i) => (
              <motion.tr
                key={incident.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.25, delay: i * 0.03 }}
                onClick={() => onSelect(incident)}
                className="cursor-pointer border-b border-border-soft transition-colors hover:bg-surface-2 last:border-0"
              >
                <td className="px-5 py-3.5 font-mono text-xs text-ink-faint">{incident.timestamp}</td>
                <td className="px-5 py-3.5 font-medium text-ink">{incident.event}</td>
                <td className="px-5 py-3.5 text-ink-dim">{incident.location}</td>
                <td className="px-5 py-3.5">
                  <RiskBadge risk={incident.risk} />
                </td>
                <td className="px-5 py-3.5 text-ink-dim">{incident.confidence}%</td>
                <td className="px-5 py-3.5">
                  <span className="inline-flex items-center gap-1.5 text-xs text-ink-dim">
                    <span className={`h-1.5 w-1.5 rounded-full ${STATUS_DOT[incident.status]}`} />
                    {STATUS_LABEL[incident.status]}
                  </span>
                </td>
                <td className="px-5 py-3.5 text-right">
                  <ChevronRight size={15} className="ml-auto text-ink-faint" />
                </td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <div className="divide-y divide-border-soft lg:hidden">
        {incidents.map((incident, i) => (
          <motion.button
            key={incident.id}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.25, delay: i * 0.03 }}
            onClick={() => onSelect(incident)}
            className="flex w-full items-center justify-between gap-3 px-4 py-4 text-left transition-colors hover:bg-surface-2"
          >
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs text-ink-faint">{incident.timestamp}</span>
                <RiskBadge risk={incident.risk} />
              </div>
              <p className="mt-1 truncate text-sm font-semibold text-ink">{incident.event}</p>
              <p className="mt-0.5 truncate text-xs text-ink-faint">{incident.location}</p>
            </div>
            <ChevronRight size={16} className="shrink-0 text-ink-faint" />
          </motion.button>
        ))}
      </div>
    </div>
  );
}

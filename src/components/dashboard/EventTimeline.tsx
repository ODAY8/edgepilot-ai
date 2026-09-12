import { motion } from "framer-motion";
import type { Incident } from "@/data/types";
import RiskBadge from "@/components/common/RiskBadge";

interface EventTimelineProps {
  incidents: Incident[];
  onSelect?: (incident: Incident) => void;
}

export default function EventTimeline({ incidents, onSelect }: EventTimelineProps) {
  return (
    <div className="rounded-2xl border border-border bg-surface p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-ink">Event Timeline</h3>
        <span className="text-xs text-ink-faint">Last {incidents.length} events</span>
      </div>

      <ul className="space-y-1">
        {incidents.map((incident, i) => (
          <motion.li
            key={incident.id}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.3, delay: i * 0.05 }}
          >
            <button
              onClick={() => onSelect?.(incident)}
              className="group flex w-full items-start gap-3 rounded-xl px-2 py-3 text-left transition-colors duration-150 hover:bg-surface-2"
            >
              <div className="flex flex-col items-center pt-1">
                <span className="h-2 w-2 shrink-0 rounded-full bg-accent group-hover:shadow-[0_0_8px_rgba(91,124,250,0.8)]" />
                {i < incidents.length - 1 && <span className="mt-1 h-full w-px flex-1 bg-border" />}
              </div>
              <div className="min-w-0 flex-1 pb-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-xs text-ink-faint">{incident.timestamp}</span>
                  <RiskBadge risk={incident.risk} />
                </div>
                <p className="mt-1 truncate text-sm font-semibold text-ink">{incident.event}</p>
                <p className="mt-0.5 line-clamp-1 text-xs text-ink-faint group-hover:text-ink-dim">
                  {incident.explanation}
                </p>
              </div>
            </button>
          </motion.li>
        ))}
      </ul>
    </div>
  );
}

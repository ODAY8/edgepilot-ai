import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, CheckCircle2, Clock } from "lucide-react";
import { useState } from "react";
import Button from "@/components/common/Button";
import RiskBadge from "@/components/common/RiskBadge";
import type { Incident } from "@/data/types";

interface IncidentCardProps {
  incident: Incident;
  onAcknowledge: (id: string) => void | Promise<void>;
  onEscalate: (id: string) => void | Promise<void>;
}

export default function IncidentCard({ incident, onAcknowledge, onEscalate }: IncidentCardProps) {
  const [busy, setBusy] = useState<"ack" | "esc" | null>(null);
  const resolved = incident.status === "ACKNOWLEDGED" || incident.status === "ESCALATED";

  const handle = async (action: "ack" | "esc") => {
    setBusy(action);
    await (action === "ack" ? onAcknowledge(incident.id) : onEscalate(incident.id));
    setBusy(null);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className="relative flex h-full flex-col overflow-hidden rounded-2xl border border-critical/25 bg-surface p-5"
    >
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(248,85,90,0.08),transparent_60%)]" />

      <div className="relative flex items-center justify-between">
        <div className="flex items-center gap-2 text-critical">
          <AlertTriangle size={16} />
          <span className="text-xs font-bold uppercase tracking-widest">Event Detected</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-ink-faint">
          <Clock size={12} />
          <span className="font-mono">{incident.timestamp}</span>
        </div>
      </div>

      <h3 className="relative mt-3 text-lg font-bold text-ink">{incident.event}</h3>
      <p className="relative mt-1 text-xs text-ink-faint">{incident.location}</p>

      <div className="relative mt-3 flex items-center gap-2">
        <RiskBadge risk={incident.risk} />
        <span className="text-xs font-medium text-ink-dim">{incident.confidence}% confidence</span>
      </div>

      <div className="relative mt-4 space-y-3 border-t border-border pt-4">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-ink-faint">
            AI Analysis
          </p>
          <p className="mt-1 text-sm leading-relaxed text-ink-dim">{incident.explanation}</p>
        </div>
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-ink-faint">
            Recommended Action
          </p>
          <p className="mt-1 text-sm leading-relaxed text-ink-dim">{incident.recommendation}</p>
        </div>
      </div>

      <div className="relative mt-5 flex gap-3">
        <AnimatePresence mode="wait">
          {resolved ? (
            <motion.div
              key="resolved"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="flex w-full items-center justify-center gap-2 rounded-lg border border-safe/30 bg-safe/10 py-2.5 text-sm font-semibold text-safe"
            >
              <CheckCircle2 size={16} />
              {incident.status === "ACKNOWLEDGED" ? "Acknowledged" : "Escalated"}
            </motion.div>
          ) : (
            <motion.div key="actions" className="flex w-full gap-3">
              <Button
                variant="secondary"
                className="flex-1"
                onClick={() => handle("ack")}
                disabled={busy !== null}
              >
                {busy === "ack" ? "Acknowledging…" : "Acknowledge"}
              </Button>
              <Button
                variant="danger"
                className="flex-1"
                onClick={() => handle("esc")}
                disabled={busy !== null}
              >
                {busy === "esc" ? "Escalating…" : "Escalate"}
              </Button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}

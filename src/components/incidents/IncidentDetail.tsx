import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, MapPin, Radio } from "lucide-react";
import { useState } from "react";
import Button from "@/components/common/Button";
import RiskBadge from "@/components/common/RiskBadge";
import type { Incident } from "@/data/types";
import { STATUS_LABEL } from "@/utils/format";

interface IncidentDetailProps {
  incident: Incident;
  onAcknowledge?: (id: string) => void | Promise<void>;
  onEscalate?: (id: string) => void | Promise<void>;
}

export default function IncidentDetail({ incident, onAcknowledge, onEscalate }: IncidentDetailProps) {
  const [busy, setBusy] = useState<"ack" | "esc" | null>(null);
  const resolved = incident.status === "ACKNOWLEDGED" || incident.status === "ESCALATED" || incident.status === "RESOLVED";

  const handle = async (action: "ack" | "esc") => {
    setBusy(action);
    await (action === "ack" ? onAcknowledge?.(incident.id) : onEscalate?.(incident.id));
    setBusy(null);
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <RiskBadge risk={incident.risk} />
        <span className="text-xs font-medium text-ink-dim">{incident.confidence}% confidence</span>
        <span className="text-xs text-ink-faint">·</span>
        <span className="text-xs text-ink-faint">{STATUS_LABEL[incident.status]}</span>
      </div>

      <div className="grid grid-cols-2 gap-4 rounded-xl border border-border-soft bg-surface-2 p-4 sm:grid-cols-4">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-ink-faint">ID</p>
          <p className="mt-1 font-mono text-sm text-ink">{incident.id}</p>
        </div>
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-ink-faint">Time</p>
          <p className="mt-1 font-mono text-sm text-ink">{incident.timestamp}</p>
        </div>
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-ink-faint">Camera</p>
          <p className="mt-1 flex items-center gap-1 text-sm text-ink">
            <Radio size={12} className="text-accent" /> {incident.cameraId}
          </p>
        </div>
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-ink-faint">Location</p>
          <p className="mt-1 flex items-center gap-1 text-sm text-ink">
            <MapPin size={12} className="text-accent" /> {incident.location}
          </p>
        </div>
      </div>

      <div>
        <p className="text-[10px] font-semibold uppercase tracking-widest text-ink-faint">AI Analysis</p>
        <p className="mt-1.5 text-sm leading-relaxed text-ink-dim">{incident.explanation}</p>
      </div>
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-widest text-ink-faint">
          Recommended Action
        </p>
        <p className="mt-1.5 text-sm leading-relaxed text-ink-dim">{incident.recommendation}</p>
      </div>

      {(onAcknowledge || onEscalate) && (
        <div className="flex gap-3 border-t border-border pt-4">
          <AnimatePresence mode="wait">
            {resolved ? (
              <motion.div
                key="resolved"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="flex w-full items-center justify-center gap-2 rounded-lg border border-safe/30 bg-safe/10 py-2.5 text-sm font-semibold text-safe"
              >
                <CheckCircle2 size={16} />
                {STATUS_LABEL[incident.status]}
              </motion.div>
            ) : (
              <motion.div key="actions" className="flex w-full gap-3">
                <Button variant="secondary" className="flex-1" onClick={() => handle("ack")} disabled={busy !== null}>
                  {busy === "ack" ? "Acknowledging…" : "Acknowledge"}
                </Button>
                <Button variant="danger" className="flex-1" onClick={() => handle("esc")} disabled={busy !== null}>
                  {busy === "esc" ? "Escalating…" : "Escalate"}
                </Button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}

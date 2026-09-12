import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Sparkles } from "lucide-react";
import { useState } from "react";
import Button from "@/components/common/Button";
import RiskBadge from "@/components/common/RiskBadge";
import type { AnalysisResult } from "@/services/api";

interface AnalysisResultCardProps {
  result: AnalysisResult;
  onAcknowledge: () => void | Promise<void>;
  onEscalate: () => void | Promise<void>;
  onAnalyzeAnother: () => void;
}

export default function AnalysisResultCard({
  result,
  onAcknowledge,
  onEscalate,
  onAnalyzeAnother,
}: AnalysisResultCardProps) {
  const [status, setStatus] = useState<"pending" | "acknowledged" | "escalated">("pending");
  const [busy, setBusy] = useState(false);

  const handle = async (action: "ack" | "esc") => {
    setBusy(true);
    try {
      await (action === "ack" ? onAcknowledge() : onEscalate());
      setStatus(action === "ack" ? "acknowledged" : "escalated");
    } catch {
      // Stay pending; the buttons re-enable so the operator can retry.
    } finally {
      setBusy(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className="rounded-2xl border border-critical/25 bg-surface p-6"
    >
      <div className="flex items-center gap-2 text-critical">
        <Sparkles size={16} />
        <span className="text-xs font-bold uppercase tracking-widest">Event Detected</span>
      </div>

      <h2 className="mt-3 text-xl font-bold text-ink">{result.event}</h2>

      <div className="mt-3 flex flex-wrap items-center gap-3">
        <RiskBadge risk={result.risk} />
        <span className="text-sm font-medium text-ink-dim">Confidence: {result.confidence}%</span>
        <span className="font-mono text-xs text-ink-faint">{result.timestamp}</span>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="rounded-xl border border-border-soft bg-surface-2 p-4">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-ink-faint">
            AI Explanation
          </p>
          <p className="mt-1.5 text-sm leading-relaxed text-ink-dim">{result.explanation}</p>
        </div>
        <div className="rounded-xl border border-border-soft bg-surface-2 p-4">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-ink-faint">
            Recommended Action
          </p>
          <p className="mt-1.5 text-sm leading-relaxed text-ink-dim">{result.recommendation}</p>
        </div>
      </div>

      <div className="mt-6 flex flex-wrap gap-3">
        <AnimatePresence mode="wait">
          {status !== "pending" ? (
            <motion.div
              key="done"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="flex items-center gap-2 rounded-lg border border-safe/30 bg-safe/10 px-4 py-2.5 text-sm font-semibold text-safe"
            >
              <CheckCircle2 size={16} />
              {status === "acknowledged" ? "Acknowledged" : "Escalated"}
            </motion.div>
          ) : (
            <motion.div key="actions" className="flex flex-wrap gap-3">
              <Button variant="secondary" onClick={() => handle("ack")} disabled={busy}>
                Acknowledge
              </Button>
              <Button variant="danger" onClick={() => handle("esc")} disabled={busy}>
                Escalate
              </Button>
            </motion.div>
          )}
        </AnimatePresence>
        <Button variant="ghost" onClick={onAnalyzeAnother}>
          Analyze Another
        </Button>
      </div>
    </motion.div>
  );
}

import { motion } from "framer-motion";
import { ShieldCheck } from "lucide-react";

// Shown in place of the "Current Incident" card while the live browser
// camera's most recent analyzed frame is normal_activity -- reflects what
// the camera is seeing right now instead of leaving a stale historical
// incident displayed as if it were still ongoing.
export default function MonitoringState() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className="flex h-full flex-col items-center justify-center gap-3 rounded-2xl border border-safe/25 bg-surface p-8 text-center"
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-safe/10 text-safe">
        <ShieldCheck size={22} />
      </div>
      <div>
        <p className="text-sm font-bold uppercase tracking-widest text-safe">All Clear</p>
        <p className="mt-1 text-sm text-ink">No anomalies detected</p>
      </div>
      <p className="max-w-xs text-xs text-ink-faint">
        The live camera's latest frame shows normal activity. This panel updates automatically
        the moment something meaningful is detected.
      </p>
    </motion.div>
  );
}

import { motion } from "framer-motion";
import { EyeOff } from "lucide-react";

interface VisionDegradedStateProps {
  message?: string | null;
}

// Shown in place of the "Current Incident" card when the live camera's most
// recent frame could not be analyzed (the vision request failed). A failed
// frame must never be presented as "All Clear", nor should a stale
// historical incident keep displaying as if it still reflects the current
// situation -- this state makes the uncertainty visible instead.
export default function VisionDegradedState({ message }: VisionDegradedStateProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className="flex h-full flex-col items-center justify-center gap-3 rounded-2xl border border-warn/25 bg-surface p-8 text-center"
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-warn/10 text-warn">
        <EyeOff size={22} />
      </div>
      <div>
        <p className="text-sm font-bold uppercase tracking-widest text-warn">Vision Unavailable</p>
        <p className="mt-1 text-sm text-ink">Unable to analyze the latest frame</p>
      </div>
      <p className="max-w-xs text-xs text-ink-faint">
        {message ?? "The vision analysis service could not be reached."} Monitoring resumes
        automatically as soon as the next frame succeeds.
      </p>
    </motion.div>
  );
}

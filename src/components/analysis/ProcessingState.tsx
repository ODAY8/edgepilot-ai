import { motion } from "framer-motion";
import { Check, Loader2 } from "lucide-react";

export type ProcessingStage = "analyzing" | "finalizing";

interface ProcessingStateProps {
  stage: ProcessingStage;
}

type StepStatus = "done" | "active" | "pending";

// The backend runs vision, risk, and reasoning inside a single request/
// response, so the client has no way to know when each one individually
// finishes -- only that the /api/analyze call itself is still pending
// ("analyzing"), or that it has genuinely returned and the follow-up
// incident lookup is in flight ("finalizing"). These three rows are shown
// together and only ever move from active -> done as a group, in lockstep
// with real "finalizing" state -- never on a fixed timer.
const STEPS: { key: string; label: string; status: (stage: ProcessingStage) => StepStatus }[] = [
  { key: "upload", label: "Upload received", status: () => "done" },
  { key: "vision", label: "Analyzing image/video with Gemini", status: (s) => (s === "finalizing" ? "done" : "active") },
  { key: "risk", label: "Evaluating risk", status: (s) => (s === "finalizing" ? "done" : "active") },
  { key: "reasoning", label: "Generating AI reasoning", status: (s) => (s === "finalizing" ? "done" : "active") },
  { key: "complete", label: "Complete", status: (s) => (s === "finalizing" ? "active" : "pending") },
];

export default function ProcessingState({ stage }: ProcessingStateProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl border border-border bg-surface p-8"
    >
      <div className="flex flex-col items-center">
        <div className="relative flex h-20 w-20 items-center justify-center">
          <motion.span
            className="absolute inset-0 rounded-full border-2 border-accent/30"
            animate={{ scale: [1, 1.25, 1], opacity: [0.6, 0, 0.6] }}
            transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
          />
          <motion.span
            className="absolute inset-2 rounded-full border-2 border-accent-2/40"
            animate={{ scale: [1, 1.15, 1], opacity: [0.5, 0, 0.5] }}
            transition={{ duration: 2, repeat: Infinity, ease: "easeInOut", delay: 0.3 }}
          />
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-linear-to-br from-accent to-accent-2 shadow-[0_0_24px_-4px_rgba(91,124,250,0.7)]">
            <Loader2 size={20} className="animate-spin text-white" />
          </div>
        </div>

        <h3 className="mt-5 text-sm font-bold uppercase tracking-widest text-ink">
          Analyzing Environment
        </h3>

        <ul className="mt-6 w-full max-w-sm space-y-3">
          {STEPS.map((step) => {
            const status = step.status(stage);
            return (
              <li key={step.key} className="flex items-center gap-3">
                <span
                  className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[10px] ${
                    status === "done"
                      ? "border-safe bg-safe/15 text-safe"
                      : status === "active"
                        ? "border-accent bg-accent-soft text-accent"
                        : "border-border text-ink-faint"
                  }`}
                >
                  {status === "done" && <Check size={12} />}
                  {status === "active" && (
                    <motion.span
                      className="h-1.5 w-1.5 rounded-full bg-accent"
                      animate={{ opacity: [1, 0.3, 1] }}
                      transition={{ duration: 1, repeat: Infinity }}
                    />
                  )}
                </span>
                <span
                  className={`text-sm ${
                    status === "pending" ? "text-ink-faint" : "font-medium text-ink"
                  }`}
                >
                  {step.label}
                </span>
              </li>
            );
          })}
        </ul>
      </div>
    </motion.div>
  );
}

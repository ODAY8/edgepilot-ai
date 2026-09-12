import { motion } from "framer-motion";
import { Check, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

const STEPS = [
  "Input received",
  "Visual data processed",
  "Detecting events",
  "Evaluating risk",
  "Generating recommendation",
];

interface ProcessingStateProps {
  onComplete: () => void;
}

export default function ProcessingState({ onComplete }: ProcessingStateProps) {
  const [activeStep, setActiveStep] = useState(0);

  useEffect(() => {
    if (activeStep >= STEPS.length) {
      const done = setTimeout(onComplete, 500);
      return () => clearTimeout(done);
    }
    const id = setTimeout(() => setActiveStep((s) => s + 1), 480);
    return () => clearTimeout(id);
  }, [activeStep, onComplete]);

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
          {STEPS.map((step, i) => {
            const status = i < activeStep ? "done" : i === activeStep ? "active" : "pending";
            return (
              <li key={step} className="flex items-center gap-3">
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
                  {step}
                </span>
              </li>
            );
          })}
        </ul>
      </div>
    </motion.div>
  );
}

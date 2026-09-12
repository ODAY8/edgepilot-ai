import { motion } from "framer-motion";
import { ArrowRight, Crosshair, MapPin, ShieldAlert, Zap } from "lucide-react";
import type { Incident } from "@/data/types";

interface AIAnalysisCardProps {
  incident: Incident;
}

export default function AIAnalysisCard({ incident }: AIAnalysisCardProps) {
  const steps = [
    { label: "Detection", value: incident.detection, icon: Crosshair, tone: "text-accent" },
    { label: "Context", value: incident.context, icon: MapPin, tone: "text-accent-2" },
    { label: "Risk", value: incident.risk, icon: ShieldAlert, tone: "text-critical" },
    { label: "Recommendation", value: incident.recommendation.split(".")[0], icon: Zap, tone: "text-warn" },
  ];

  return (
    <div className="rounded-2xl border border-border bg-surface p-5">
      <h3 className="text-sm font-semibold text-ink">AI Reasoning Chain</h3>
      <p className="mt-0.5 text-xs text-ink-faint">How EdgePilot arrived at this decision</p>

      <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-4 sm:gap-0">
        {steps.map((step, i) => (
          <div key={step.label} className="flex items-center sm:contents">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: i * 0.12, ease: "easeOut" }}
              className="min-w-0 flex-1 rounded-xl border border-border-soft bg-surface-2 p-3.5 sm:mx-1"
            >
              <div className={`mb-2 flex h-7 w-7 items-center justify-center rounded-md bg-surface-3 ${step.tone}`}>
                <step.icon size={14} />
              </div>
              <p className="text-[10px] font-semibold uppercase tracking-widest text-ink-faint">
                {step.label}
              </p>
              <p className="mt-1 truncate text-sm font-medium text-ink" title={step.value}>
                {step.value}
              </p>
            </motion.div>
            {i < steps.length - 1 && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.3, delay: i * 0.12 + 0.15 }}
                className="hidden shrink-0 items-center justify-center text-ink-faint sm:flex sm:w-6"
              >
                <ArrowRight size={14} className="text-accent/50" />
              </motion.div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

import { motion } from "framer-motion";
import { Activity, ArrowRight, Eye, Gauge, ShieldCheck, Zap } from "lucide-react";
import { Link } from "react-router-dom";
import RiskBadge from "@/components/common/RiskBadge";
import StatusIndicator from "@/components/common/StatusIndicator";

const PIPELINE = [
  { label: "Observe", icon: Eye, description: "Ingest camera and edge video streams in real time." },
  { label: "Understand", icon: Activity, description: "AI vision detects people, objects, and anomalies." },
  { label: "Assess", icon: Gauge, description: "Reasoning engine scores risk with full context." },
  { label: "Act", icon: ShieldCheck, description: "Operators get a clear, recommended next step." },
];

export default function Landing() {
  return (
    <div className="min-h-svh bg-base">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(ellipse_at_top,rgba(91,124,250,0.12),transparent_45%)]" />

      <header className="relative mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-linear-to-br from-accent to-accent-2 shadow-[0_0_20px_-4px_rgba(91,124,250,0.7)]">
            <Activity size={18} className="text-white" strokeWidth={2.5} />
          </div>
          <span className="text-sm font-bold text-ink">EdgePilot</span>
        </div>
        <Link
          to="/dashboard"
          className="rounded-lg border border-border px-4 py-2 text-sm font-semibold text-ink-dim transition-colors hover:border-accent/40 hover:text-ink"
        >
          Launch Dashboard
        </Link>
      </header>

      <section className="relative mx-auto max-w-4xl px-6 pb-16 pt-12 text-center sm:pt-20">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <StatusIndicator label="Live edge network" tone="safe" className="mx-auto justify-center" />
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="mt-6 text-4xl font-extrabold leading-[1.08] tracking-tight text-ink sm:text-6xl"
        >
          Edge intelligence,
          <br />
          <span className="bg-linear-to-r from-accent to-accent-2 bg-clip-text text-transparent">
            made actionable.
          </span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="mx-auto mt-5 max-w-xl text-base text-ink-dim sm:text-lg"
        >
          EdgePilot transforms physical-world data into intelligent, actionable decisions —
          for factories, warehouses, and industrial facilities.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row"
        >
          <Link
            to="/dashboard"
            className="inline-flex items-center gap-2 rounded-lg bg-linear-to-r from-accent to-accent-2 px-5 py-3 text-sm font-semibold text-white shadow-[0_8px_24px_-8px_rgba(91,124,250,0.6)] transition-transform hover:scale-[1.02]"
          >
            Launch Dashboard
            <ArrowRight size={16} />
          </Link>
          <a
            href="#how-it-works"
            className="inline-flex items-center gap-2 rounded-lg border border-border px-5 py-3 text-sm font-semibold text-ink-dim transition-colors hover:border-accent/40 hover:text-ink"
          >
            Explore How It Works
          </a>
        </motion.div>
      </section>

      {/* Dashboard preview */}
      <section className="relative mx-auto max-w-5xl px-6 pb-20">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.35, ease: "easeOut" }}
          className="rounded-2xl border border-border bg-surface p-3 shadow-2xl sm:p-5"
        >
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-border-soft bg-surface-2 p-4 sm:col-span-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-semibold uppercase tracking-widest text-ink-faint">
                  Camera 01 · Edge Node 01
                </span>
                <span className="flex items-center gap-1.5 text-[10px] font-bold uppercase text-critical">
                  <span className="h-1.5 w-1.5 rounded-full bg-critical" /> Live
                </span>
              </div>
              <div className="relative mt-3 aspect-video overflow-hidden rounded-lg bg-[#05060a]">
                <div className="absolute inset-0 bg-grid opacity-40" />
                <div className="absolute left-[38%] top-[30%] h-[40%] w-[22%] rounded-sm border-2 border-critical/80" />
              </div>
            </div>
            <div className="rounded-xl border border-critical/20 bg-surface-2 p-4">
              <p className="text-[10px] font-bold uppercase tracking-widest text-critical">Event Detected</p>
              <p className="mt-2 text-sm font-bold text-ink">Restricted Area Entry</p>
              <div className="mt-2">
                <RiskBadge risk="HIGH" />
              </div>
              <p className="mt-3 text-xs leading-relaxed text-ink-faint">
                A worker entered the restricted zone near industrial equipment.
              </p>
            </div>
          </div>
        </motion.div>
      </section>

      {/* Pipeline */}
      <section id="how-it-works" className="relative mx-auto max-w-5xl px-6 pb-24">
        <h2 className="text-center text-sm font-semibold uppercase tracking-widest text-ink-faint">
          How It Works
        </h2>
        <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-4">
          {PIPELINE.map((step, i) => (
            <motion.div
              key={step.label}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: i * 0.08 }}
              className="rounded-2xl border border-border bg-surface p-5 text-center"
            >
              <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-xl bg-accent-soft text-accent">
                <step.icon size={18} />
              </div>
              <p className="mt-3 text-sm font-bold text-ink">{step.label}</p>
              <p className="mt-1.5 text-xs leading-relaxed text-ink-faint">{step.description}</p>
            </motion.div>
          ))}
        </div>
      </section>

      <footer className="relative border-t border-border px-6 py-8 text-center">
        <p className="flex items-center justify-center gap-1.5 text-xs text-ink-faint">
          <Zap size={12} className="text-accent" /> EdgePilot AI — Turn edge intelligence into actionable decisions.
        </p>
      </footer>
    </div>
  );
}

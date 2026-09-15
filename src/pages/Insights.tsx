import { motion } from "framer-motion";
import { Activity, Clock, HeartPulse, Server } from "lucide-react";
import { useEffect, useState } from "react";
import ChartCard from "@/components/common/ChartCard";
import EventCategoriesChart from "@/components/analytics/EventCategoriesChart";
import EventsOverTimeChart from "@/components/analytics/EventsOverTimeChart";
import RiskDistributionChart from "@/components/analytics/RiskDistributionChart";
import ErrorState from "@/components/common/ErrorState";
import { getAnalyticsData, type AnalyticsData } from "@/services/api";

export default function Analytics() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setError(null);
    getAnalyticsData()
      .then(setData)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Failed to load analytics."));
  };

  useEffect(load, []);

  if (error) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <ErrorState message={error} onRetry={load} />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex h-[50vh] items-center justify-center text-sm text-ink-faint">
        Loading analytics…
      </div>
    );
  }

  const summary = [
    { label: "Uptime", value: data.systemHealth.uptime || "N/A", icon: HeartPulse, tone: "text-safe bg-safe/10" },
    {
      label: "Avg Response Time",
      value: data.systemHealth.avgResponseTime || "N/A",
      icon: Clock,
      tone: "text-accent bg-accent-soft",
    },
    {
      label: "Edge Nodes Online",
      value:
        data.systemHealth.edgeNodesOnline != null && data.systemHealth.edgeNodesTotal != null
          ? `${data.systemHealth.edgeNodesOnline}/${data.systemHealth.edgeNodesTotal}`
          : "N/A",
      icon: Server,
      tone: "text-accent bg-accent-soft",
    },
    {
      label: "Events (24h)",
      value: data.eventsOverTime.reduce((s, p) => s + (p.events ?? 0), 0),
      icon: Activity,
      tone: "text-accent-2 bg-accent-soft",
    },
  ];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {summary.map((item, i) => (
          <motion.div
            key={item.label}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: i * 0.05 }}
            className="rounded-2xl border border-border bg-surface p-4"
          >
            <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${item.tone}`}>
              <item.icon size={15} />
            </div>
            <p className="mt-3 text-lg font-bold text-ink">{item.value}</p>
            <p className="mt-0.5 text-[11px] font-medium uppercase tracking-wide text-ink-faint">
              {item.label}
            </p>
          </motion.div>
        ))}
      </div>

      <ChartCard title="Events Over Time" subtitle="Detections across the last shift">
        <EventsOverTimeChart data={data.eventsOverTime} />
      </ChartCard>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ChartCard title="Risk Distribution" subtitle="Share of events by risk level">
          <RiskDistributionChart data={data.riskDistribution} />
        </ChartCard>
        <ChartCard title="Event Categories" subtitle="Most common detected event types">
          <EventCategoriesChart data={data.eventCategories} />
        </ChartCard>
      </div>
    </div>
  );
}

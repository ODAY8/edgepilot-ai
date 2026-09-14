import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TimelinePoint } from "@/data/types";

interface EventsOverTimeChartProps {
  data: TimelinePoint[];
}

export default function EventsOverTimeChart({ data }: EventsOverTimeChartProps) {
  if (data.length === 0) {
    return (
      <div className="flex h-[240px] items-center justify-center text-sm text-ink-faint">
        No event data available yet.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={240}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
        <defs>
          <linearGradient id="eventsGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#5b7cfa" stopOpacity={0.35} />
            <stop offset="100%" stopColor="#5b7cfa" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="#1f2431" vertical={false} />
        <XAxis
          dataKey="time"
          tick={{ fill: "#5b6274", fontSize: 11 }}
          axisLine={{ stroke: "#1f2431" }}
          tickLine={false}
        />
        <YAxis tick={{ fill: "#5b6274", fontSize: 11 }} axisLine={false} tickLine={false} width={24} />
        <Tooltip
          contentStyle={{
            background: "#10131c",
            border: "1px solid #1f2431",
            borderRadius: 10,
            fontSize: 12,
            color: "#e8eaf2",
          }}
          labelStyle={{ color: "#9aa1b4" }}
          cursor={{ stroke: "#5b7cfa", strokeWidth: 1, strokeDasharray: "4 4" }}
        />
        <Area
          type="monotone"
          dataKey="events"
          stroke="#5b7cfa"
          strokeWidth={2}
          fill="url(#eventsGradient)"
          animationDuration={900}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

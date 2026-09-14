import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { RiskDistributionPoint } from "@/data/types";

interface RiskDistributionChartProps {
  data: RiskDistributionPoint[];
}

const COLORS: Record<string, string> = {
  LOW: "#34d399",
  MEDIUM: "#fbbf24",
  HIGH: "#f8555a",
};

export default function RiskDistributionChart({ data }: RiskDistributionChartProps) {
  const total = data.reduce((sum, entry) => sum + entry.value, 0);
  if (total === 0) {
    return (
      <div className="flex h-[240px] items-center justify-center text-sm text-ink-faint">
        No event data available yet.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={240}>
      <PieChart>
        <Pie
          data={data}
          dataKey="value"
          nameKey="name"
          innerRadius={55}
          outerRadius={85}
          paddingAngle={3}
          animationDuration={900}
        >
          {data.map((entry) => (
            <Cell key={entry.name} fill={COLORS[entry.name] ?? "#5b6274"} stroke="none" />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            background: "#10131c",
            border: "1px solid #1f2431",
            borderRadius: 10,
            fontSize: 12,
            color: "#e8eaf2",
          }}
        />
        <Legend
          verticalAlign="bottom"
          iconType="circle"
          iconSize={8}
          wrapperStyle={{ fontSize: 12, color: "#9aa1b4" }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}

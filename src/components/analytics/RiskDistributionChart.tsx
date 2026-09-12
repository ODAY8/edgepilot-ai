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
            <Cell key={entry.name} fill={COLORS[entry.name]} stroke="none" />
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

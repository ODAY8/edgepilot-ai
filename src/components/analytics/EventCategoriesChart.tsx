import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { EventCategoryPoint } from "@/data/types";

interface EventCategoriesChartProps {
  data: EventCategoryPoint[];
}

export default function EventCategoriesChart({ data }: EventCategoriesChartProps) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} layout="vertical" margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
        <CartesianGrid stroke="#1f2431" horizontal={false} />
        <XAxis type="number" tick={{ fill: "#5b6274", fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis
          type="category"
          dataKey="name"
          tick={{ fill: "#9aa1b4", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          width={120}
        />
        <Tooltip
          contentStyle={{
            background: "#10131c",
            border: "1px solid #1f2431",
            borderRadius: 10,
            fontSize: 12,
            color: "#e8eaf2",
          }}
          cursor={{ fill: "rgba(91,124,250,0.08)" }}
        />
        <Bar dataKey="value" fill="#8b6bf5" radius={[0, 6, 6, 0]} animationDuration={900} barSize={16} />
      </BarChart>
    </ResponsiveContainer>
  );
}

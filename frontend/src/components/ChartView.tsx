import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ChartSpec } from "../types";

// Renders the backend-computed series as-is; no values are derived in the browser.
export default function ChartView({ chart }: { chart: ChartSpec }) {
  const common = { data: chart.data, margin: { top: 8, right: 16, bottom: 8, left: 8 } };
  return (
    <div className="mt-4">
      <div className="label mb-2">{chart.title}</div>
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          {chart.type === "bar" ? (
            <BarChart {...common}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E9E4D8" />
              <XAxis dataKey="name" tick={{ fontSize: 12, fill: "#777166" }} label={{ value: chart.x_label, position: "insideBottom", offset: -2, fill: "#777166", fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12, fill: "#777166" }} label={{ value: chart.y_label, angle: -90, position: "insideLeft", fill: "#777166", fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="value" fill="#F5BC42" radius={[6, 6, 0, 0]} />
            </BarChart>
          ) : (
            <LineChart {...common}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E9E4D8" />
              <XAxis dataKey="name" tick={{ fontSize: 12, fill: "#777166" }} />
              <YAxis tick={{ fontSize: 12, fill: "#777166" }} />
              <Tooltip />
              <Line type="monotone" dataKey="value" stroke="#111111" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  );
}

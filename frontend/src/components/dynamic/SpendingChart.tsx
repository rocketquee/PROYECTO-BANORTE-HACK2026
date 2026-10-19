"use client";

import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { SpendingChartSpec } from "@/types/contract";
import { CHART_COLORS, money } from "@/lib/format";

export default function SpendingChart({
  spec, onAsk,
}: { spec: SpendingChartSpec; onAsk: (message: string) => void }) {
  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold">{spec.title}</h3>
        <span className="rounded-full bg-neutral-100 px-2.5 py-1 text-xs text-neutral-600">
          {spec.period}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <PieChart>
          <Pie
            data={spec.series}
            dataKey="amount"
            nameKey="category"
            innerRadius={65}
            outerRadius={105}
            paddingAngle={2}
            onClick={(entry: unknown) => {
              const category = (entry as { category?: string })?.category;
              if (category) onAsk(`¿Cómo puedo reducir mis gastos en ${category}?`);
            }}
            className="cursor-pointer focus:outline-none"
          >
            {spec.series.map((_, i) => (
              <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
            ))}
          </Pie>
          <Tooltip formatter={(v, name) => [money(Number(v)), String(name)]} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
        </PieChart>
      </ResponsiveContainer>
      <p className="mt-1 text-center text-xs text-neutral-400">
        Haz clic en una categoría para pedirle al agente un plan de reducción.
      </p>
    </div>
  );
}

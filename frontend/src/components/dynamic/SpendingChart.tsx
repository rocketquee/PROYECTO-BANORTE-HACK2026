"use client";

import { useState } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { SpendingChartSpec } from "@/types/contract";
import { CHART_COLORS, money } from "@/lib/format";

/**
 * Gastos por categoría. WCAG 2.2 AA: every slice shows name + value + pct
 * (not color-only), a table view carries the same data, and the graphic has
 * a text summary for screen readers.
 */
export default function SpendingChart({
  spec, onAsk,
}: { spec: SpendingChartSpec; onAsk: (message: string) => void }) {
  const [view, setView] = useState<"chart" | "table">("chart");
  const total = spec.series.reduce((acc, s) => acc + s.amount, 0);
  const summary = spec.series
    .map((s) => `${s.category}: ${money(s.amount)} (${s.pct}%)`)
    .join("; ");

  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-base font-semibold">{spec.title}</h3>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-neutral-200 px-3 py-1 text-base text-neutral-800">
            {spec.period}
          </span>
          <button
            onClick={() => setView(view === "chart" ? "table" : "chart")}
            className="min-h-[48px] rounded-lg border border-neutral-300 px-3 py-2 text-base text-neutral-700 hover:border-brand"
          >
            {view === "chart" ? "Ver como tabla" : "Ver como gráfica"}
          </button>
        </div>
      </div>

      {view === "chart" ? (
        <>
          <ResponsiveContainer width="100%" height={320}>
            <PieChart role="img"
                      aria-label={`Gráfica de gastos: ${summary}. Total ${money(total)}.`}>
              <Pie
                data={spec.series}
                dataKey="amount"
                nameKey="category"
                innerRadius={70}
                outerRadius={110}
                paddingAngle={2}
                label={(props: { name?: string; percent?: number }) =>
                  `${props.name ?? ""} ${Math.round((props.percent ?? 0) * 100)}%`
                }
                labelLine
                onClick={(entry: unknown) => {
                  const category = (entry as { category?: string })?.category;
                  if (category) onAsk(`¿Cómo puedo reducir mis gastos en ${category}?`);
                }}
                className="cursor-pointer focus:outline-none"
              >
                {spec.series.map((_, i) => (
                  <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]}
                        stroke="#FFFFFF" strokeWidth={2} />
                ))}
              </Pie>
              <Tooltip formatter={(v, name) => [money(Number(v)), String(name)]} />
            </PieChart>
          </ResponsiveContainer>
          <ul className="mt-3 grid grid-cols-1 gap-1.5 sm:grid-cols-2">
            {spec.series.map((s, i) => (
              <li key={s.category} className="flex items-center gap-2 text-base">
                <span
                  className="inline-block h-4 w-4 shrink-0 rounded"
                  style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }}
                  aria-hidden="true"
                />
                <span className="min-w-0 flex-1 truncate text-neutral-800">{s.category}</span>
                <span className="tabular-nums text-neutral-900">{money(s.amount)}</span>
                <span className="tabular-nums text-neutral-600">({s.pct}%)</span>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <table className="w-full text-left text-base">
          <caption className="sr-only">{spec.title}</caption>
          <thead>
            <tr className="border-b border-neutral-300">
              <th scope="col" className="py-2">Categoría</th>
              <th scope="col" className="py-2 text-right">Gasto</th>
              <th scope="col" className="py-2 text-right">Porcentaje</th>
              <th scope="col" className="py-2 text-right">Movimientos</th>
            </tr>
          </thead>
          <tbody>
            {spec.series.map((s) => (
              <tr key={s.category} className="border-b border-neutral-200">
                <th scope="row" className="py-2 font-normal">{s.category}</th>
                <td className="py-2 text-right tabular-nums">{money(s.amount)}</td>
                <td className="py-2 text-right tabular-nums">{s.pct}%</td>
                <td className="py-2 text-right tabular-nums">{s.count ?? "—"}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row" className="py-2 font-semibold">Total</th>
              <td className="py-2 text-right font-semibold tabular-nums">{money(total)}</td>
              <td colSpan={2} />
            </tr>
          </tfoot>
        </table>
      )}
      <p className="mt-3 text-base text-neutral-600">
        Consejo: selecciona una categoría en la gráfica para pedir un plan de reducción.
      </p>
    </div>
  );
}

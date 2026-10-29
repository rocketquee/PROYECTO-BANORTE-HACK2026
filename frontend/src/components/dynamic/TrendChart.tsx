"use client";

import { useEffect, useId, useRef, useState } from "react";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Line,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { TrendChartSpec } from "@/types/contract";
import { CHART_COLORS, money } from "@/lib/format";
import useReducedMotion from "@/hooks/useReducedMotion";

/**
 * Temporal chart (line / bars / area) with visible values, a table view of
 * the same data, an accessible text summary and a chart-type switcher.
 */
export default function TrendChart({ spec }: { spec: TrendChartSpec }) {
  const [view, setView] = useState<"chart" | "table">("chart");
  const [chartType, setChartType] = useState(spec.chart_type);
  const [linePath, setLinePath] = useState("");
  const [overlaySize, setOverlaySize] = useState({ width: 0, height: 0 });
  const [lineEnd, setLineEnd] = useState({ x: 0, y: 0 });
  const chartContainer = useRef<HTMLDivElement>(null);
  const gradientId = `trend-fill-${useId().replace(/:/g, "")}`;
  const reducedMotion = useReducedMotion();

  const data = spec.series.map((p) => ({ name: p.label, amount: p.amount }));
  const summary = spec.series
    .map((p) => `${p.label}: ${money(p.amount)}`)
    .join("; ");

  const Chart = chartType === "bar" ? BarChart : AreaChart;

  useEffect(() => {
    if (view !== "chart" || chartType !== "line") {
      setLinePath("");
      return;
    }

    let frame = 0;
    const readChart = () => {
      if (!chartContainer.current) return;
      const bounds = chartContainer.current.getBoundingClientRect();
      setOverlaySize({ width: bounds.width, height: bounds.height });
      setLinePath(
        chartContainer.current.querySelector(".recharts-line-curve")?.getAttribute("d") ?? ""
      );
    };
    const resizeObserver = new ResizeObserver(() => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(readChart);
    });

    if (chartContainer.current) resizeObserver.observe(chartContainer.current);
    frame = requestAnimationFrame(readChart);
    return () => {
      cancelAnimationFrame(frame);
      resizeObserver.disconnect();
    };
  }, [chartType, spec, view]);

  useEffect(() => {
    if (!linePath) return;
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", linePath);
    const length = path.getTotalLength();
    const end = path.getPointAtLength(length);
    setLineEnd({ x: end.x, y: end.y });
  }, [linePath]);

  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-base font-semibold">{spec.title}</h3>
        <div className="flex gap-1" role="group" aria-label="Tipo de gráfica y vista">
          {(["line", "bar", "area"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setChartType(t)}
              aria-pressed={chartType === t}
              className={`min-h-[48px] rounded-lg border px-3 py-2 text-base ${
                chartType === t
                  ? "border-brand bg-brand-soft font-medium text-brand-dark"
                  : "border-neutral-300 text-neutral-700 hover:border-brand"
              }`}
            >
              {t === "line" ? "Línea" : t === "bar" ? "Barras" : "Área"}
            </button>
          ))}
          <button
            onClick={() => setView(view === "chart" ? "table" : "chart")}
            className="min-h-[48px] rounded-lg border border-neutral-300 px-3 py-2 text-base text-neutral-700 hover:border-brand"
          >
            {view === "chart" ? "Ver como tabla" : "Ver como gráfica"}
          </button>
        </div>
      </div>

      {view === "chart" ? (
        <div ref={chartContainer} className="relative">
        <ResponsiveContainer width="100%" height={320}>
          <Chart key={chartType} data={data} role="img" aria-label={`Gráfica de ${spec.title}. ${summary}`}>
            <CartesianGrid strokeDasharray="3 3" stroke="#D4D4D4" />
            <XAxis dataKey="name" tick={{ fontSize: 18, fill: "var(--muted)" }} />
            <YAxis
              tick={{ fontSize: 18, fill: "var(--muted)" }}
              tickFormatter={(v: number) => money(v, 0)}
            />
            <Tooltip formatter={(v) => money(Number(v))} />
            {chartType === "line" && (
              <>
                <defs>
                  <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#EB0029" stopOpacity={0.25} />
                    <stop offset="100%" stopColor="#EB0029" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <Area
                  type="monotone"
                  dataKey="amount"
                  stroke="none"
                  fill={`url(#${gradientId})`}
                  isAnimationActive={!reducedMotion}
                  animationDuration={900}
                  name="Gasto"
                />
              </>
            )}
            {chartType === "line" && (
              <Line
                type="monotone"
                dataKey="amount"
                stroke="#EB0029"
                strokeWidth={3}
                dot={{ r: 5 }}
                name="Gasto"
                isAnimationActive={!reducedMotion}
                animationDuration={900}
              />
            )}
            {chartType === "bar" && (
              <Bar
                dataKey="amount"
                fill={CHART_COLORS[1]}
                name="Gasto"
                radius={[6, 6, 0, 0]}
                isAnimationActive={!reducedMotion}
                animationDuration={900}
              />
            )}
            {chartType === "area" && (
              <Area type="monotone" dataKey="amount" stroke={CHART_COLORS[1]}
                    fill={CHART_COLORS[1]} fillOpacity={0.25} strokeWidth={3} name="Gasto"
                    isAnimationActive={!reducedMotion} animationDuration={900} />
            )}
          </Chart>
        </ResponsiveContainer>
        {chartType === "line" && linePath && overlaySize.width > 0 && (
          <svg
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 h-full w-full overflow-visible"
            viewBox={`0 0 ${overlaySize.width} ${overlaySize.height}`}
            preserveAspectRatio="none"
          >
            <path d={linePath} fill="none" stroke="none" />
            <circle
              cx={reducedMotion ? lineEnd.x : 0}
              cy={reducedMotion ? lineEnd.y : 0}
              r="6"
              fill="#EB0029"
              stroke="white"
              strokeWidth="2"
            >
              {!reducedMotion && (
                <animateMotion dur="900ms" fill="freeze" path={linePath} />
              )}
            </circle>
          </svg>
        )}
        </div>
      ) : (
        <table className="w-full text-left text-base">
          <caption className="sr-only">{spec.title}</caption>
          <thead>
            <tr className="border-b border-neutral-300">
              <th scope="col" className="py-2">Periodo</th>
              <th scope="col" className="py-2 text-right">Gasto</th>
            </tr>
          </thead>
          <tbody>
            {spec.series.map((p) => (
              <tr key={p.label} className="border-b border-neutral-200">
                <th scope="row" className="py-2 font-normal">{p.label}</th>
                <td className="py-2 text-right tabular-nums">{money(p.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {spec.conclusion && (
        <p className="mt-3 rounded-xl bg-neutral-100 p-3 text-base text-neutral-800">
          {spec.conclusion}
        </p>
      )}
      <p className="mt-2 text-base text-neutral-700">{spec.period}</p>
    </div>
  );
}

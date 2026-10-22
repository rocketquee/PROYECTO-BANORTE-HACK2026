"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { DashboardData, GoalProgress } from "@/types/contract";
import { apiFetch } from "@/lib/api";
import { CHART_COLORS, fmtDate, money } from "@/lib/format";

function Kpi({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-2xl bg-white p-5 shadow-sm">
      <p className="text-base font-medium uppercase tracking-wide text-neutral-700">{label}</p>
      <p className={`mt-2 text-2xl font-semibold ${tone ?? ""}`}>{value}</p>
    </div>
  );
}

function GoalRow({ goal }: { goal: GoalProgress }) {
  return (
    <div>
      <div className="flex items-center justify-between text-base">
        <span className="font-medium">{goal.name}</span>
        <span className="text-neutral-700">
          {money(goal.saved_amount)} / {money(goal.target_amount)} · {goal.progress_pct}%
        </span>
      </div>
      <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-neutral-200">
        <div
          className={`h-full rounded-full ${goal.progress_pct >= 100 ? "bg-emerald-600" : "bg-brand"}`}
          style={{ width: `${Math.min(goal.progress_pct, 100)}%` }}
        />
      </div>
    </div>
  );
}

const monthOptions = () => {
  const out: { value: string; label: string }[] = [];
  const now = new Date();
  for (let i = 0; i < 6; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    out.push({
      value: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`,
      label: d.toLocaleDateString("es-MX", { month: "long", year: "numeric" }),
    });
  }
  return out;
};

export default function DashboardView({ refreshKey }: { refreshKey: number }) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [month, setMonth] = useState<string>(monthOptions()[0].value);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const months = useMemo(monthOptions, []);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    apiFetch<DashboardData>(`/api/dashboard?month=${month}`)
      .then((d) => { if (alive) { setData(d); setLoading(false); } })
      .catch((e: Error) => { if (alive) { setError(e.message); setLoading(false); } });
    return () => { alive = false; };
  }, [month, refreshKey]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-neutral-700">
        Cargando dashboard…
      </div>
    );
  }
  if (error || !data) {
    return (
      <div className="m-6 rounded-xl bg-brand-soft p-4 text-base text-brand-dark">
        {error ?? "No se pudieron cargar los datos."}
      </div>
    );
  }

  const s = data.summary;
  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <select
          value={month}
          onChange={(e) => setMonth(e.target.value)}
          className="rounded-lg border border-neutral-300 bg-white px-3 py-2 text-base"
          aria-label="Filtrar resumen por mes"
        >
          {months.map((m) => (
            <option key={m.value} value={m.value}>{m.label}</option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi label="Saldo total" value={money(data.total_balance)} />
        <Kpi label={`Ingresos · ${s.month_label}`} value={money(s.income)} tone="text-emerald-700" />
        <Kpi label={`Gastos · ${s.month_label}`} value={money(s.expense)} tone="text-brand" />
        <Kpi
          label="Balance del mes"
          value={money(s.net)}
          tone={s.net >= 0 ? "text-emerald-700" : "text-brand"}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <div className="rounded-2xl bg-white p-5 shadow-sm">
          <h2 className="mb-4 text-base font-semibold">Gastos por categoría · {s.month_label}</h2>
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie
                data={data.categories}
                dataKey="amount"
                nameKey="category"
                innerRadius={60}
                outerRadius={100}
                paddingAngle={2}
              >
                {data.categories.map((_, i) => (
                  <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                formatter={(v) => money(Number(v))}
                contentStyle={{ backgroundColor: "var(--surface)", borderColor: "var(--line)", color: "var(--text)" }}
                labelStyle={{ color: "var(--text)" }}
                itemStyle={{ color: "var(--text)" }}
              />
              <Legend wrapperStyle={{ fontSize: 18, color: "var(--text)" }} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="rounded-2xl bg-white p-5 shadow-sm">
          <h2 className="mb-4 text-base font-semibold">Ingresos vs gastos (últimos 6 meses)</h2>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={data.monthly_series}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="label" fontSize={18} tick={{ fill: "var(--muted)" }} />
              <YAxis fontSize={18} tick={{ fill: "var(--muted)" }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
              <Tooltip
                formatter={(v) => money(Number(v))}
                contentStyle={{ backgroundColor: "var(--surface)", borderColor: "var(--line)", color: "var(--text)" }}
                labelStyle={{ color: "var(--text)" }}
                itemStyle={{ color: "var(--text)" }}
              />
              <Legend wrapperStyle={{ fontSize: 18, color: "var(--text)" }} />
              <Bar dataKey="income" name="Ingresos" fill="#2E86AB" radius={[4, 4, 0, 0]} />
              <Bar dataKey="expense" name="Gastos" fill="#C8102E" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <div className="rounded-2xl bg-white p-5 shadow-sm">
          <h2 className="mb-4 text-base font-semibold">Metas de ahorro</h2>
          <div className="space-y-4">
            {data.goals.map((g) => <GoalRow key={g.id} goal={g} />)}
            {data.goals.length === 0 && (
              <p className="text-base text-neutral-700">Aún no tienes metas. Créalas desde el asistente.</p>
            )}
          </div>
        </div>

        <div className="rounded-2xl bg-white p-5 shadow-sm">
          <h2 className="mb-4 text-base font-semibold">Movimientos recientes</h2>
          <table className="w-full text-base">
            <thead>
              <tr className="text-left text-base uppercase tracking-wide text-neutral-700">
                <th className="pb-2">Fecha</th>
                <th className="pb-2">Concepto</th>
                <th className="pb-2 text-right">Importe</th>
              </tr>
            </thead>
            <tbody>
              {data.recent_transactions.map((t) => (
                <tr key={t.id} className="border-t border-neutral-100">
                  <td className="py-2 text-neutral-700">{fmtDate(t.date)}</td>
                  <td className="py-2">
                    {t.description}
                    <span className="ml-2 rounded bg-neutral-100 px-1.5 py-0.5 text-base text-neutral-600">
                      {t.category}
                    </span>
                  </td>
                  <td className={`py-2 text-right font-medium ${
                    t.type === "income" ? "text-emerald-700" : "text-neutral-800"
                  }`}>
                    {t.type === "income" ? "+" : "−"}{money(t.amount)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="rounded-2xl bg-white p-5 shadow-sm">
        <h2 className="mb-2 text-base font-semibold">Resumen de actividad financiera</h2>
        <p className="text-base leading-relaxed text-neutral-600">
          En {s.month_label} registraste {s.transaction_count} movimientos: ingresos por{" "}
          <strong>{money(s.income)}</strong> y gastos por <strong>{money(s.expense)}</strong>, con un
          balance de <strong>{money(s.net)}</strong>. Tu presupuesto disponible del mes es{" "}
          <strong>{money(data.budget_overview.available)}</strong>. Estos son hechos calculados sobre
          datos sintéticos de demostración, no asesoría financiera.
        </p>
      </div>
    </div>
  );
}

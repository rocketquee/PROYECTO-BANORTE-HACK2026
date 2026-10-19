"use client";

import { useState } from "react";
import type { BudgetCategory } from "@/types/contract";
import { post } from "@/lib/api";
import { money } from "@/lib/format";

export default function BudgetPlanner({
  title, month, income, total_spent, categories,
}: {
  title: string;
  month: string;
  income: number;
  total_spent: number;
  categories: BudgetCategory[];
}) {
  const [rows, setRows] = useState(categories);
  const [saving, setSaving] = useState<string | null>(null);

  const spentTotal = rows.reduce((acc, r) => acc + r.spent, 0);
  const available = income - spentTotal;

  async function saveLimit(category: string, limit: number) {
    setSaving(category);
    try {
      await post("/api/budget/update", { category, monthly_limit: limit });
    } finally {
      setSaving(null);
    }
  }

  function updateLimit(category: string, value: number) {
    setRows((prev) => prev.map((r) => (r.category === category ? { ...r, limit: value } : r)));
  }

  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">{title}</h3>
        <span className="text-xs text-neutral-500">Mes {month}</span>
      </div>

      <div className="mb-4 grid grid-cols-3 gap-3 text-sm">
        <div className="rounded-xl bg-neutral-50 p-3">
          <p className="text-xs text-neutral-500">Ingreso del mes</p>
          <p className="font-semibold">{money(income)}</p>
        </div>
        <div className="rounded-xl bg-neutral-50 p-3">
          <p className="text-xs text-neutral-500">Gastado</p>
          <p className="font-semibold text-brand">{money(spentTotal)}</p>
        </div>
        <div className="rounded-xl bg-neutral-50 p-3">
          <p className="text-xs text-neutral-500">Disponible</p>
          <p className={`font-semibold ${available >= 0 ? "text-emerald-700" : "text-brand"}`}>
            {money(available)}
          </p>
        </div>
      </div>

      <div className="space-y-3">
        {rows.map((r) => {
          const pct = r.limit ? Math.round((r.spent / r.limit) * 100) : null;
          return (
            <div key={r.category} className="flex flex-wrap items-center gap-3">
              <span className="w-44 text-sm font-medium">{r.category}</span>
              <div className="h-2 min-w-[100px] flex-1 overflow-hidden rounded-full bg-neutral-200">
                <div
                  className={`h-full rounded-full ${
                    pct !== null && pct > 100 ? "bg-brand" : pct !== null && pct > 85 ? "bg-amber-500" : "bg-emerald-600"
                  }`}
                  style={{ width: pct !== null ? `${Math.min(pct, 100)}%` : "0%" }}
                />
              </div>
              <span className="w-40 text-xs text-neutral-500">
                {money(r.spent)} de <input
                  value={r.limit}
                  onChange={(e) => updateLimit(r.category, Number(e.target.value.replace(/[^\d.]/g, "")) || 0)}
                  onBlur={() => saveLimit(r.category, r.limit)}
                  inputMode="decimal"
                  className="w-20 rounded border border-neutral-300 px-1.5 py-0.5 text-right text-xs"
                  aria-label={`Límite mensual de ${r.category}`}
                />
                {saving === r.category && <span className="ml-1">guardando…</span>}
              </span>
              {pct !== null && pct > 100 && (
                <span className="rounded-full bg-brand-soft px-2 py-0.5 text-[11px] font-medium text-brand-dark">
                  Excedido
                </span>
              )}
            </div>
          );
        })}
      </div>
      <p className="mt-3 text-xs text-neutral-400">
        Edita un límite y sal del campo para guardarlo. Gastos calculados sobre movimientos del mes.
      </p>
    </div>
  );
}

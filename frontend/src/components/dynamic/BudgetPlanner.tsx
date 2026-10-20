"use client";

import { useState } from "react";
import type { BudgetCategory } from "@/types/contract";
import { post } from "@/lib/api";
import { money, moneyInput } from "@/lib/format";

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
        <h3 className="text-base font-semibold">{title}</h3>
        <span className="text-base text-neutral-700">Mes {month}</span>
      </div>

      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <div className="rounded-xl bg-neutral-50 p-3">
          <p className="text-base text-neutral-700">Ingreso del mes</p>
          <p className="text-base font-semibold">{money(income)}</p>
        </div>
        <div className="rounded-xl bg-neutral-50 p-3">
          <p className="text-base text-neutral-700">Gastado</p>
          <p className="text-base font-semibold text-brand">{money(spentTotal)}</p>
        </div>
        <div className="rounded-xl bg-neutral-50 p-3">
          <p className="text-base text-neutral-700">Disponible</p>
          <p className={`text-base font-semibold ${available >= 0 ? "text-emerald-800" : "text-brand"}`}>
            {money(available)}
          </p>
          {/* R9: a negative available balance is spelled out. */}
          {available < 0 && (
            <p className="text-base font-medium text-brand-dark">
              Ya gastaste {money(Math.abs(available))} de más este mes.
            </p>
          )}
        </div>
      </div>

      <div className="space-y-3">
        {rows.map((r) => {
          const pct = r.limit ? Math.round((r.spent / r.limit) * 100) : null;
          return (
            <div key={r.category} className="flex flex-wrap items-center gap-3">
              <span className="w-44 text-base font-medium">{r.category}</span>
              <div className="h-2 min-w-[100px] flex-1 overflow-hidden rounded-full bg-neutral-200">
                <div
                  className={`h-full rounded-full ${
                    pct !== null && pct > 100 ? "bg-brand" : pct !== null && pct > 85 ? "bg-amber-600" : "bg-emerald-700"
                  }`}
                  style={{ width: pct !== null ? `${Math.min(pct, 100)}%` : "0%" }}
                />
              </div>
              <span className="flex items-center gap-1 text-base text-neutral-800">
                {money(r.spent)} de
                {/* UI-4: the limit shows "$" plus a thousands separator
                    ("$1,500") and stays editable. */}
                <span className="flex items-center rounded border border-neutral-400 bg-white pl-1.5 focus-within:border-brand">
                  <span aria-hidden="true" className="text-base text-neutral-800">$</span>
                  <input
                    value={moneyInput(r.limit)}
                    onChange={(e) => updateLimit(r.category, Number(e.target.value.replace(/[^\d]/g, "")) || 0)}
                    onBlur={() => saveLimit(r.category, r.limit)}
                    inputMode="numeric"
                    className="w-20 min-h-[32px] bg-transparent px-1.5 py-1 text-right text-base text-neutral-900 outline-none"
                    aria-label={`Límite mensual de ${r.category} en pesos`}
                  />
                </span>
                {saving === r.category && <span className="ml-1">guardando…</span>}
              </span>
              {pct !== null && pct > 100 && (
                <span className="rounded-full bg-brand-soft px-2 py-0.5 text-base font-medium text-brand-dark">
                  Excedido
                </span>
              )}
            </div>
          );
        })}
      </div>
      <p className="mt-3 text-base text-neutral-700">
        Edita un límite y sal del campo para guardarlo. Gastos calculados sobre movimientos del mes.
      </p>
    </div>
  );
}

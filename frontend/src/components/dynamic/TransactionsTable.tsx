"use client";

import { useMemo, useState } from "react";
import type { TransactionsTableSpec } from "@/types/contract";
import { fmtDate, money } from "@/lib/format";

export default function TransactionsTable({ spec }: { spec: TransactionsTableSpec }) {
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [type, setType] = useState("");

  const filtered = useMemo(
    () =>
      spec.transactions.filter(
        (t) =>
          (!q || t.description.toLowerCase().includes(q.toLowerCase())) &&
          (!category || t.category === category) &&
          (!type || t.type === type)
      ),
    [spec.transactions, q, category, type]
  );

  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-base font-semibold">{spec.title}</h3>
        <div className="flex flex-wrap gap-2">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar concepto…"
            className="rounded-lg border border-neutral-300 px-3 py-1.5 text-base"
            aria-label="Buscar movimientos"
          />
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="rounded-lg border border-neutral-300 bg-white px-2 py-1.5 text-base"
            aria-label="Filtrar por categoría"
          >
            <option value="">Todas las categorías</option>
            {spec.categories.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <select
            value={type}
            onChange={(e) => setType(e.target.value)}
            className="rounded-lg border border-neutral-300 bg-white px-2 py-1.5 text-base"
            aria-label="Filtrar por tipo"
          >
            <option value="">Ingresos, gastos y transferencias</option>
            <option value="expense">Solo gastos</option>
            <option value="income">Solo ingresos</option>
            <option value="transfer">Solo transferencias</option>
          </select>
        </div>
      </div>
      <p className="mb-2 text-base text-neutral-700">
        {spec.period_label} · {filtered.length} de {spec.total_count} movimientos
      </p>
      <div className="max-h-96 overflow-y-auto">
        <table className="w-full text-base">
          <thead className="sticky top-0 bg-white">
            <tr className="text-left text-base uppercase tracking-wide text-neutral-700">
              <th className="pb-2">Fecha</th>
              <th className="pb-2">Concepto</th>
              <th className="pb-2">Categoría</th>
              <th className="pb-2 text-right">Importe</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((t) => (
              <tr key={t.id} className="border-t border-neutral-100">
                <td className="py-2 text-neutral-700">{fmtDate(t.date)}</td>
                <td className="py-2">{t.description}</td>
                <td className="py-2">
                  <span className="rounded bg-neutral-100 px-1.5 py-0.5 text-base text-neutral-600">
                    {t.category ?? "Transferencia"}
                  </span>
                </td>
                <td className={`py-2 text-right font-medium ${
                  t.type === "income" ? "text-emerald-700" : "text-neutral-800"
                }`}>
                  {t.type === "income" ? "+" : t.type === "expense" ? "−" : ""}{money(t.amount)}
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr><td colSpan={4} className="py-4 text-center text-neutral-700">Sin resultados.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";
import type { GoalProgress } from "@/types/contract";
import { patch } from "@/lib/api";
import { fmtDate, money } from "@/lib/format";

export default function SavingsProgress({
  title, goals, onChanged,
}: { title: string; goals: GoalProgress[]; onChanged?: () => void }) {
  const [local, setLocal] = useState(goals);
  const [busy, setBusy] = useState<number | null>(null);

  async function addAmount(goal: GoalProgress, amount: number) {
    if (!window.confirm(`¿Confirmas abonar ${money(amount)} a la meta "${goal.name}"?`)) return;
    setBusy(goal.id);
    try {
      const updated = await patch<GoalProgress>(`/api/goals/${goal.id}`, { add_amount: amount });
      setLocal((prev) => prev.map((g) => (g.id === goal.id ? { ...g, ...updated } : g)));
      onChanged?.();
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
      <h3 className="mb-4 text-sm font-semibold">{title}</h3>
      <div className="space-y-5">
        {local.map((g) => (
          <div key={g.id}>
            <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <span className="font-medium">
                {g.name}
                {g.status === "completada" && (
                  <span className="ml-2 rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-medium text-emerald-700">
                    Completada
                  </span>
                )}
              </span>
              <span className="text-neutral-500">
                {money(g.saved_amount)} / {money(g.target_amount)} · {g.progress_pct}%
                {g.deadline && ` · límite ${fmtDate(g.deadline)}`}
              </span>
            </div>
            <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-neutral-200">
              <div
                className={`h-full rounded-full ${g.progress_pct >= 100 ? "bg-emerald-600" : "bg-brand"}`}
                style={{ width: `${Math.min(g.progress_pct, 100)}%` }}
              />
            </div>
            <button
              onClick={() => addAmount(g, 500)}
              disabled={busy === g.id}
              className="mt-2 rounded-lg border border-brand px-3 py-1.5 text-xs font-medium text-brand hover:bg-brand-soft disabled:opacity-50"
            >
              {busy === g.id ? "Abonando…" : "Abonar $500"}
            </button>
          </div>
        ))}
        {local.length === 0 && (
          <p className="text-sm text-neutral-500">No hay metas todavía.</p>
        )}
      </div>
    </div>
  );
}

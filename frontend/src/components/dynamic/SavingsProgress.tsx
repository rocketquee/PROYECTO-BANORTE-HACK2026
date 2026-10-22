"use client";

import { useState } from "react";
import type { GoalProgress } from "@/types/contract";
import { patch } from "@/lib/api";
import { fmtDate, money } from "@/lib/format";
import AnimatedProgressFill from "../AnimatedProgressFill";
import ProgressRing from "../ProgressRing";

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
      <h3 className="mb-4 text-base font-semibold">{title}</h3>
      <div className="space-y-5">
        {local.map((g) => (
          <div key={g.id} className="screen-stagger">
            <div className="flex flex-wrap items-center justify-between gap-2 text-base">
              <span className="flex items-center gap-3 font-medium">
                <ProgressRing value={g.progress_pct} />
                <span>
                  {g.name}
                  {g.status === "completada" && (
                    <span className="ml-2 rounded-full bg-emerald-100 px-2 py-0.5 text-base font-medium text-emerald-700">
                      Completada
                    </span>
                  )}
                </span>
              </span>
              <span className="text-neutral-700">
                {money(g.saved_amount)} / {money(g.target_amount)} · {g.progress_pct}%
                {g.deadline && ` · límite ${fmtDate(g.deadline)}`}
              </span>
            </div>
            <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-neutral-200">
              <AnimatedProgressFill
                value={g.progress_pct}
                className={g.progress_pct >= 100 ? "bg-emerald-600" : "bg-brand"}
              />
            </div>
            <button
              onClick={() => addAmount(g, 500)}
              disabled={busy === g.id}
              className="mt-2 rounded-lg border border-brand px-3 py-1.5 text-base font-medium text-brand hover:bg-brand-soft disabled:opacity-50"
            >
              {busy === g.id ? "Abonando…" : "Abonar $500"}
            </button>
          </div>
        ))}
        {local.length === 0 && (
          <p className="text-base text-neutral-700">No hay metas todavía.</p>
        )}
      </div>
    </div>
  );
}

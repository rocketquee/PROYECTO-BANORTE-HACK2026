"use client";

import { useState } from "react";
import type { SavingsContributionSpec } from "@/types/contract";
import { money } from "@/lib/format";

export default function SavingsContribution({
  spec,
  loading,
  onSelectGoal,
  onChangeAmount,
  onConfirm,
}: {
  spec: SavingsContributionSpec;
  loading: boolean;
  onSelectGoal: (goalId: number) => void;
  onChangeAmount: (amount: number) => void;
  onConfirm: (goalId: number, amount: number, token: string, key: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [amount, setAmount] = useState(spec.contribution_amount?.toString() ?? "");

  if (spec.status === "select_goal") {
    return (
      <section className="rounded-2xl border border-neutral-300 bg-white p-4" aria-labelledby="goal-select-title">
        <h3 id="goal-select-title" className="text-[18px] font-semibold">¿A cuál meta te refieres?</h3>
        <div className="mt-3 grid gap-2">
          {spec.candidates.map((goal) => (
            <button
              key={goal.goal_id}
              type="button"
              disabled={loading}
              onClick={() => onSelectGoal(goal.goal_id)}
              className="min-h-[48px] rounded-xl border-2 border-neutral-300 px-4 py-2 text-left text-[18px] hover:border-brand focus-visible:outline focus-visible:outline-4 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:opacity-60"
            >
              {goal.goal_name} · faltan {money(Math.max(0, goal.target_amount - goal.saved_amount))}
            </button>
          ))}
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-neutral-300 bg-white p-4" aria-labelledby="contribution-title">
      <h3 id="contribution-title" className="text-[18px] font-semibold">
        {spec.status === "completed" ? "Abono registrado" : "Revisa el abono"}
      </h3>
      <p className="mt-2 text-[18px]">{spec.goal_name}</p>
      <dl className="mt-3 space-y-2 text-[18px]">
        <div className="flex justify-between gap-3">
          <dt>Faltan</dt><dd className="font-semibold">{money(spec.remaining_before ?? 0)}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt>{spec.status === "completed" ? "Abonaste" : "Abonarás"}</dt>
          <dd className="font-semibold">{money(spec.contribution_amount ?? 0)}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt>Quedarán</dt><dd className="font-semibold">{money(spec.remaining_after ?? 0)}</dd>
        </div>
      </dl>
      {spec.status === "confirm_required" && (
        <>
          <p className="mt-3 text-base text-neutral-700">
            Disponible en tus cuentas: {money(spec.available_balance ?? 0)}. Solo se actualizarán datos de demostración.
          </p>
          {editing ? (
            <form
              className="mt-3 flex flex-wrap gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                const nextAmount = Number(amount);
                if (Number.isFinite(nextAmount) && nextAmount > 0) {
                  onChangeAmount(nextAmount);
                  setEditing(false);
                }
              }}
            >
              <label className="flex min-w-0 flex-1 flex-col gap-1 text-base">
                Nuevo monto
                <input
                  type="number"
                  min="0.01"
                  step="0.01"
                  value={amount}
                  onChange={(event) => setAmount(event.target.value)}
                  className="min-h-[48px] rounded-xl border border-neutral-400 px-3 text-[18px]"
                />
              </label>
              <button type="submit" disabled={loading} className="min-h-[48px] rounded-xl border-2 border-brand px-4 text-[18px] font-semibold text-brand">
                Actualizar
              </button>
            </form>
          ) : (
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                disabled={loading || !spec.confirmation_token || !spec.idempotency_key || !spec.goal_id}
                onClick={() => {
                  if (spec.confirmation_token && spec.idempotency_key && spec.goal_id && spec.contribution_amount) {
                    onConfirm(spec.goal_id, spec.contribution_amount, spec.confirmation_token, spec.idempotency_key);
                  }
                }}
                className="min-h-[48px] rounded-xl bg-brand px-4 text-[18px] font-semibold text-white focus-visible:outline focus-visible:outline-4 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:opacity-60"
              >
                Confirmar abono
              </button>
              <button
                type="button"
                disabled={loading}
                onClick={() => setEditing(true)}
                className="min-h-[48px] rounded-xl border-2 border-brand px-4 text-[18px] font-semibold text-brand focus-visible:outline focus-visible:outline-4 focus-visible:outline-offset-2 focus-visible:outline-brand"
              >
                Cambiar monto
              </button>
            </div>
          )}
        </>
      )}
    </section>
  );
}

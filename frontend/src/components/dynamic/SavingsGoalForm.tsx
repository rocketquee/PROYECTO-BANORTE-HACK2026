"use client";

import { useState } from "react";
import type { SavingsGoalFormSpec } from "@/types/contract";
import { post } from "@/lib/api";
import { money } from "@/lib/format";

interface Props {
  spec: SavingsGoalFormSpec;
  pending?: { id: string; description: string } | null;
  onCreated: (name: string, target: number) => void;
  onConfirmPending?: (actionId: string) => Promise<void>;
}

export default function SavingsGoalForm({ spec, pending, onCreated, onConfirmPending }: Props) {
  const [name, setName] = useState(spec.suggested_name ?? "");
  const [target, setTarget] = useState(spec.suggested_amount?.toString() ?? "");
  const [deadline, setDeadline] = useState(spec.suggested_deadline ?? "");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const amount = Number(target);
    if (!name.trim() || !amount || amount <= 0) {
      setError("Captura un nombre y un importe válido.");
      return;
    }
    setSaving(true);
    try {
      await post("/api/goals", {
        name: name.trim(),
        target_amount: amount,
        deadline: deadline || null,
      });
      onCreated(name.trim(), amount);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
      <h3 className="mb-4 text-base font-semibold">{spec.title}</h3>

      {pending && onConfirmPending && (
        <div className="mb-4 rounded-xl bg-brand-soft p-4">
          <p className="text-base font-medium text-brand-dark">Confirmación requerida</p>
          <p className="mt-1 text-base text-brand-dark/80">{pending.description}</p>
          <button
            onClick={() => onConfirmPending(pending.id)}
            className="mt-3 rounded-lg bg-brand px-4 py-2 text-base font-medium text-white hover:bg-brand-dark"
          >
            Confirmar creación
          </button>
        </div>
      )}

      <form onSubmit={submit} className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <label className="text-base">
          <span className="mb-1 block font-medium text-neutral-700">Nombre de la meta</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Ej. Fondo de viaje"
            className="w-full rounded-lg border border-neutral-300 px-3 py-2 text-base"
          />
        </label>
        <label className="text-base">
          <span className="mb-1 block font-medium text-neutral-700">Importe objetivo</span>
          <input
            value={target}
            onChange={(e) => setTarget(e.target.value.replace(/[^\d.]/g, ""))}
            inputMode="decimal"
            placeholder="5000"
            className="w-full rounded-lg border border-neutral-300 px-3 py-2 text-base"
          />
          {target && <span className="mt-1 block text-base text-neutral-700">{money(Number(target) || 0)}</span>}
        </label>
        <label className="text-base">
          <span className="mb-1 block font-medium text-neutral-700">Fecha límite</span>
          <input
            type="date"
            value={deadline}
            onChange={(e) => setDeadline(e.target.value)}
            className="w-full rounded-lg border border-neutral-300 px-3 py-2 text-base"
          />
        </label>
        {error && <p className="text-base text-brand sm:col-span-3">{error}</p>}
        <div className="sm:col-span-3">
          <button
            type="submit"
            disabled={saving}
            className="rounded-lg bg-brand px-4 py-2 text-base font-medium text-white hover:bg-brand-dark disabled:opacity-50"
          >
            {saving ? "Guardando…" : "Guardar meta"}
          </button>
        </div>
      </form>
    </div>
  );
}

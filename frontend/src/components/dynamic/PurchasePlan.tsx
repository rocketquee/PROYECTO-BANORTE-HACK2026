"use client";

import type { PurchasePlanSpec, PurchaseOption } from "@/types/contract";
import { fmtDate, money } from "@/lib/format";

export default function PurchasePlan({
  spec,
  loading,
  eventAvailable,
  onSelect,
  onRequestGoal,
  onConfirmGoal,
}: {
  spec: PurchasePlanSpec;
  loading: boolean;
  eventAvailable: boolean;
  onSelect: (optionId: PurchaseOption["option_id"], label: string) => void;
  onRequestGoal: () => void;
  onConfirmGoal: (confirmationToken: string, idempotencyKey: string) => void;
}) {
  const selected = spec.options.find(
    (option) => option.option_id === spec.selected_option_id
  );

  return (
    <section
      className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm"
      aria-labelledby="purchase-plan-title"
    >
      <h3 id="purchase-plan-title" className="mb-4 text-[20px] font-semibold">
        {spec.title}: {money(spec.purchase_amount)}
      </h3>

      <dl className="mb-4 grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl bg-neutral-50 p-3">
          <dt className="text-[18px] text-neutral-700">Saldo actual</dt>
          <dd className="text-[20px] font-semibold">{money(spec.current_balance)}</dd>
        </div>
        <div className="rounded-xl bg-neutral-50 p-3">
          <dt className="text-[18px] text-neutral-700">Saldo si compras de contado</dt>
          <dd className="text-[20px] font-semibold">{money(spec.balance_after_cash_purchase)}</dd>
        </div>
        <div className="rounded-xl bg-neutral-50 p-3">
          <dt className="text-[18px] text-neutral-700">Balance de este mes</dt>
          <dd className="text-[20px] font-semibold">{money(spec.monthly_balance)}</dd>
          {spec.monthly_balance < 0 && (
            <p className="text-[18px] font-medium text-red-800">
              Ya gastaste {money(Math.abs(spec.monthly_balance))} de más este mes.
            </p>
          )}
        </div>
        <div className="rounded-xl bg-neutral-50 p-3">
          <dt className="text-[18px] text-neutral-700">Pagos fijos al mes</dt>
          <dd className="text-[20px] font-semibold">{money(spec.fixed_payments_monthly)}</dd>
        </div>
      </dl>

      <fieldset className="space-y-2" disabled={loading || !eventAvailable}>
        <legend className="mb-2 text-[18px] font-medium">
          Elige una opción para ver cómo cambiaría tu balance mensual
        </legend>
        {spec.options.map((option) => {
          const isSelected = spec.selected_option_id === option.option_id;
          return (
            <button
              key={option.option_id}
              type="button"
              aria-pressed={isSelected}
              onClick={() => onSelect(option.option_id, option.label)}
              className={`flex min-h-[56px] w-full flex-wrap items-center justify-between gap-2 rounded-xl border-2 px-4 py-3 text-left text-[18px] focus-visible:outline focus-visible:outline-4 focus-visible:outline-offset-2 focus-visible:outline-brand ${
                isSelected
                  ? "border-brand bg-brand-soft text-brand-dark"
                  : "border-neutral-300 bg-white text-neutral-900 hover:border-brand"
              }`}
            >
              <span className="font-medium">{option.label}</span>
              <span>
                {option.monthly_payment > 0
                  ? `${money(option.monthly_payment)} al mes`
                  : money(option.total_cost)}
              </span>
            </button>
          );
        })}
      </fieldset>

      {loading && (
        <p className="mt-3 text-[18px] text-neutral-700" role="status" aria-live="polite">
          Actualizando el impacto de la opción…
        </p>
      )}
      {!eventAvailable && (
        <p className="mt-3 text-[18px] text-amber-900" role="status">
          Vuelve a consultar la compra para activar las opciones de este plan.
        </p>
      )}

      {selected && (
        <div className="mt-4 rounded-xl border border-brand/30 bg-brand-soft p-4" aria-live="polite">
          <h4 className="text-[18px] font-semibold">Con esta opción</h4>
          <p className="text-[18px]">
            El balance mensual estimado quedaría en{" "}
            <strong>{money(selected.monthly_balance_after)}</strong>.
          </p>
        </div>
      )}

      {spec.selected_option_id === "savings_12" && spec.goal_status === "not_requested" && (
        <button
          type="button"
          disabled={loading || !eventAvailable}
          onClick={onRequestGoal}
          className="mt-4 min-h-[48px] rounded-xl bg-brand px-5 py-3 text-[18px] font-semibold text-white hover:bg-brand-dark focus-visible:outline focus-visible:outline-4 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:cursor-not-allowed disabled:opacity-60"
        >
          Preparar meta de ahorro
        </button>
      )}

      {spec.goal_status === "confirm_required" && (
        <div className="mt-4 rounded-xl border-2 border-amber-500 bg-amber-50 p-4">
          <h4 className="text-[18px] font-semibold">Revisa antes de confirmar</h4>
          <p className="mt-2 text-[18px]">
            Se creará la meta <strong>{spec.goal_name}</strong> por{" "}
            <strong>{money(spec.purchase_amount)}</strong>, con fecha límite el{" "}
            <strong>{fmtDate(spec.goal_deadline ?? "")}</strong>.
          </p>
          <p className="mt-2 text-[18px]">
            Solo se guardará una meta de ahorro ficticia. No se apartará ni moverá dinero.
          </p>
          <button
            type="button"
            disabled={loading || !eventAvailable || !spec.goal_confirmation_token || !spec.goal_idempotency_key}
            onClick={() => {
              if (spec.goal_confirmation_token && spec.goal_idempotency_key) {
                onConfirmGoal(spec.goal_confirmation_token, spec.goal_idempotency_key);
              }
            }}
            className="mt-3 min-h-[48px] rounded-xl bg-brand px-5 py-3 text-[18px] font-semibold text-white hover:bg-brand-dark focus-visible:outline focus-visible:outline-4 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:cursor-not-allowed disabled:opacity-60"
          >
            Confirmar y crear meta
          </button>
        </div>
      )}

      {spec.goal_status === "created" && (
        <p className="mt-4 rounded-xl bg-emerald-50 p-4 text-[18px] font-medium text-emerald-900" role="status">
          La meta ya está creada y aparece en Metas de ahorro.
        </p>
      )}

      <p className="mt-4 text-[18px] text-neutral-700">{spec.disclaimer}</p>
      <p className="mt-2 text-[18px] font-medium text-neutral-800">
        Prototipo educativo con datos sintéticos. No es el banco oficial ni una oferta financiera.
      </p>
    </section>
  );
}

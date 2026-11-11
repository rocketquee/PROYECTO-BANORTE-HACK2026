"use client";

import { useState } from "react";
import type { UIPlan, UIPlanAction, UIPlanComponent } from "@/types/contract";
import { formatMoney, transferFormAction } from "@/lib/uiPlan.mjs";
import ProgressRing from "@/components/ProgressRing";

const MAX_BAR = 100;

function StatCard({ component }: { component: Extract<UIPlanComponent, { type: "StatCard" }> }) {
  const tone = component.tone === "positive"
    ? "text-emerald-700"
    : component.tone === "negative"
      ? "text-brand"
      : "text-neutral-900";
  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
      <p className="text-base text-neutral-600">{component.title}</p>
      <p className={`mt-1 text-2xl font-semibold ${tone}`}>{component.value}</p>
      {component.hint && <p className="mt-1 text-base text-neutral-600">{component.hint}</p>}
      {typeof component.trend_pct === "number" && (
        <p className="mt-1 text-base text-neutral-700">
          {component.trend_pct > 0 ? "+" : ""}
          {component.trend_pct}% contra el periodo anterior
        </p>
      )}
    </div>
  );
}

function BarChart({ component }: { component: Extract<UIPlanComponent, { type: "BarChart" }> }) {
  const max = Math.max(...component.series.map((item) => item.value), 1);
  const summary = component.series
    .map((item) => `${item.label}: ${formatMoney(item.value)}`)
    .join("; ");
  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
      <h3 className="text-base font-semibold">{component.title}</h3>
      <ul className="mt-3 space-y-2" aria-label={`${component.title}. ${summary}`}>
        {component.series.map((item) => {
          const width = Math.max(2, (item.value / max) * MAX_BAR);
          return (
            <li key={`${item.label}-${item.value}`}>
              <div className="flex items-baseline justify-between gap-3 text-base">
                <span className="truncate text-neutral-800">{item.label}</span>
                <span className="shrink-0 font-medium text-neutral-900">
                  {formatMoney(item.value)}
                </span>
              </div>
              <div className="mt-1 h-2.5 rounded-full bg-neutral-200" aria-hidden="true">
                <div className="h-2.5 rounded-full bg-brand" style={{ width: `${width}%` }} />
              </div>
            </li>
          );
        })}
      </ul>
      {component.note && <p className="mt-3 text-base text-neutral-600">{component.note}</p>}
      <p className="mt-1 text-base text-neutral-600">Unidad: {component.unit ?? "MXN"}</p>
    </div>
  );
}

function Table({ component }: { component: Extract<UIPlanComponent, { type: "Table" }> }) {
  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
      <h3 className="text-base font-semibold">{component.title}</h3>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full border-collapse text-base">
          <thead>
            <tr>
              {component.columns.map((column) => (
                <th key={column} scope="col" className="border-b border-neutral-300 px-2 py-2 text-left font-semibold">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {component.rows.map((row, rowIndex) => (
              <tr key={rowIndex} className="border-b border-neutral-100">
                {row.map((cell, cellIndex) => (
                  <td key={cellIndex} className="px-2 py-2 text-neutral-800">
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {component.note && <p className="mt-3 text-base text-neutral-600">{component.note}</p>}
    </div>
  );
}

function Progress({ component }: { component: Extract<UIPlanComponent, { type: "ProgressRing" }> }) {
  return (
    <div className="flex items-start gap-4 rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
      <ProgressRing value={component.value} />
      <div className="min-w-0">
        <h3 className="text-base font-semibold">{component.title}</h3>
        <p className="text-base text-neutral-800">{component.label}</p>
        <p className="mt-1 text-base text-neutral-700">
          {Math.round(component.value)}%{component.target_label ? ` de ${component.target_label}` : ""}
        </p>
        {component.note && <p className="mt-1 text-base text-neutral-600">{component.note}</p>}
      </div>
    </div>
  );
}

function TransferForm({
  component, onAction, disabled,
}: {
  component: Extract<UIPlanComponent, { type: "TransferForm" }>;
  onAction: (message: string, action?: UIPlanAction) => void;
  disabled: boolean;
}) {
  const [sent, setSent] = useState(false);
  const action = transferFormAction(component);
  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
      <h3 className="text-base font-semibold">{component.title}</h3>
      <dl className="mt-3 grid grid-cols-2 gap-2 text-base">
        <dt className="text-neutral-600">Desde</dt>
        <dd className="text-neutral-900">{component.from_account}</dd>
        <dt className="text-neutral-600">Hacia</dt>
        <dd className="text-neutral-900">{component.to_account}</dd>
        <dt className="text-neutral-600">Monto</dt>
        <dd className="font-semibold text-neutral-900">{formatMoney(component.amount)}</dd>
        <dt className="text-neutral-600">Concepto</dt>
        <dd className="text-neutral-900">{component.concept}</dd>
      </dl>
      <p className="mt-3 text-base text-neutral-600">{component.confirmation_text}</p>
      <button
        onClick={() => {
          setSent(true);
          onAction(action.message, action.event as UIPlanAction | undefined);
        }}
        disabled={disabled || sent}
        className="mt-3 min-h-[48px] rounded-xl bg-brand px-5 py-3 text-base font-medium text-white hover:bg-brand-dark disabled:opacity-60"
      >
        {sent ? "Confirmación enviada" : "Confirmar transferencia"}
      </button>
      <p className="mt-2 text-base text-neutral-600" role="status" aria-live="polite">
        {sent ? "Confirmando con el agente…" : ""}
      </p>
    </div>
  );
}

export default function UIRenderer({
  plan, onAction, disabled = false,
}: {
  plan: UIPlan;
  onAction: (message: string, action?: UIPlanAction) => void;
  disabled?: boolean;
}) {
  if (!plan.components.length) return null;
  return (
    <section aria-label={plan.title} className="space-y-3">
      <h2 className="text-lg font-semibold text-neutral-900">{plan.title}</h2>
      {plan.components.map((component, index) => {
        const key = `${component.type}-${index}`;
        switch (component.type) {
          case "StatCard":
            return <StatCard key={key} component={component} />;
          case "BarChart":
            return <BarChart key={key} component={component} />;
          case "Table":
            return <Table key={key} component={component} />;
          case "ProgressRing":
            return <Progress key={key} component={component} />;
          case "TransferForm":
            return <TransferForm key={key} component={component} onAction={onAction} disabled={disabled} />;
          default:
            return null;
        }
      })}
    </section>
  );
}

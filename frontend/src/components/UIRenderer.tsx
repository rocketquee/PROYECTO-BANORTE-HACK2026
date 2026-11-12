"use client";

import { useState } from "react";
import type { UIPlan, UIPlanAction, UIPlanComponent } from "@/types/contract";
import { formatMoney, sliderAction, transferFormAction } from "@/lib/uiPlan.mjs";
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

function PlanDePago({ component }: { component: Extract<UIPlanComponent, { type: "PlanDePago" }> }) {
  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
      <h3 className="text-base font-semibold">{component.title}</h3>
      <p className="mt-1 text-base text-neutral-700">
        Monto {formatMoney(component.amount)} · tasa anual {component.annual_rate}%
      </p>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full border-collapse text-base">
          <thead>
            <tr>
              <th scope="col" className="border-b border-neutral-300 px-2 py-2 text-left font-semibold">Plazo</th>
              <th scope="col" className="border-b border-neutral-300 px-2 py-2 text-right font-semibold">Pago mensual</th>
              <th scope="col" className="border-b border-neutral-300 px-2 py-2 text-right font-semibold">CAT</th>
              <th scope="col" className="border-b border-neutral-300 px-2 py-2 text-right font-semibold">Intereses</th>
            </tr>
          </thead>
          <tbody>
            {component.terms.map((term) => (
              <tr key={term.months} className="border-b border-neutral-100">
                <td className="px-2 py-2 text-neutral-800">{term.months} meses</td>
                <td className="px-2 py-2 text-right font-medium text-neutral-900">
                  {formatMoney(term.monthly_payment)}
                </td>
                <td className="px-2 py-2 text-right text-neutral-800">{term.cat_pct}%</td>
                <td className="px-2 py-2 text-right text-neutral-800">
                  {typeof term.total_interest === "number" ? formatMoney(term.total_interest) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {component.note && <p className="mt-3 text-base text-neutral-600">{component.note}</p>}
      <p className="mt-1 text-base text-neutral-600">
        CAT estimado sin comisiones; simulación educativa, no una oferta.
      </p>
    </div>
  );
}

function LineChart({ component }: { component: Extract<UIPlanComponent, { type: "LineChart" }> }) {
  const values = component.points.map((point) => point.value);
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const span = max - min || 1;
  const coords = component.points.map((point, index) => ({
    x: 4 + (index * 92) / Math.max(component.points.length - 1, 1),
    y: 36 - ((point.value - min) / span) * 28,
  }));
  const summary = component.points
    .map((point) => `${point.label}: ${formatMoney(point.value)}`)
    .join("; ");
  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
      <h3 className="text-base font-semibold">{component.title}</h3>
      <p className="mt-1 text-base text-neutral-600">{component.period}</p>
      <svg
        viewBox="0 0 100 40"
        role="img"
        aria-label={`${component.title}. ${summary}`}
        className="mt-3 h-36 w-full text-brand"
      >
        <line x1="4" y1="36" x2="96" y2="36" stroke="currentColor" strokeWidth="0.4" opacity="0.25" />
        <polyline
          points={coords.map((point) => `${point.x},${point.y}`).join(" ")}
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        {coords.map((point, index) => (
          <circle key={index} cx={point.x} cy={point.y} r="1.2" fill="currentColor" />
        ))}
      </svg>
      <ul className="mt-2 grid grid-cols-1 gap-1 text-base sm:grid-cols-2">
        {component.points.map((point) => (
          <li key={`${point.label}-${point.value}`} className="flex justify-between gap-3">
            <span className="truncate text-neutral-700">{point.label}</span>
            <span className="shrink-0 font-medium text-neutral-900">{formatMoney(point.value)}</span>
          </li>
        ))}
      </ul>
      {component.note && <p className="mt-3 text-base text-neutral-600">{component.note}</p>}
      <p className="mt-1 text-base text-neutral-600">
        {component.series_label ?? "Serie"} · unidad {component.unit ?? "MXN"}
      </p>
    </div>
  );
}

function SliderControl({
  component, onAction, disabled,
}: {
  component: Extract<UIPlanComponent, { type: "Slider" }>;
  onAction: (message: string, action?: UIPlanAction) => void;
  disabled: boolean;
}) {
  const [value, setValue] = useState(component.value);
  const display = component.unit === "MXN" ? formatMoney(value) : `${value}`;
  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
      <h3 className="text-base font-semibold">{component.title}</h3>
      <label className="mt-2 block text-base">
        <span className="mb-1 block text-neutral-700">
          {component.label}: <strong>{display}</strong>
          {component.unit && component.unit !== "MXN" ? ` ${component.unit}` : ""}
        </span>
        <input
          type="range"
          min={component.min_value}
          max={component.max_value}
          step={component.step}
          value={value}
          onChange={(event) => setValue(Number(event.target.value))}
          className="w-full accent-brand"
          aria-label={component.label}
        />
      </label>
      {component.note && <p className="mt-2 text-base text-neutral-600">{component.note}</p>}
      <button
        onClick={() => onAction(sliderAction(component, value))}
        disabled={disabled}
        className="mt-3 min-h-[48px] rounded-xl bg-brand px-5 py-3 text-base font-medium text-white hover:bg-brand-dark disabled:opacity-60"
      >
        Recalcular
      </button>
    </div>
  );
}

function BudgetAllocator({ component }: { component: Extract<UIPlanComponent, { type: "BudgetAllocator" }> }) {
  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
      <h3 className="text-base font-semibold">{component.title}</h3>
      <p className="mt-1 text-base text-neutral-700">
        Ingreso del mes: <strong>{formatMoney(component.income)}</strong>
      </p>
      <ul className="mt-3 space-y-3">
        {component.buckets.map((bucket) => (
          <li key={bucket.bucket}>
            <div className="flex items-baseline justify-between gap-3 text-base">
              <span className="capitalize text-neutral-800">
                {bucket.bucket} · {bucket.pct}%
              </span>
              <span className="shrink-0 font-medium text-neutral-900">
                {formatMoney(bucket.amount)}
              </span>
            </div>
            <div className="mt-1 h-2.5 rounded-full bg-neutral-200" aria-hidden="true">
              <div
                className="h-2.5 rounded-full bg-brand"
                style={{ width: `${bucket.pct}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
      {component.note && <p className="mt-3 text-base text-neutral-600">{component.note}</p>}
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
          case "PlanDePago":
            return <PlanDePago key={key} component={component} />;
          case "LineChart":
            return <LineChart key={key} component={component} />;
          case "Slider":
            return <SliderControl key={key} component={component} onAction={onAction} disabled={disabled} />;
          case "BudgetAllocator":
            return <BudgetAllocator key={key} component={component} />;
          default:
            return null;
        }
      })}
    </section>
  );
}

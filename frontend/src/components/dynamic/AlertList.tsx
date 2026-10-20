"use client";

import type { AlertListSpec } from "@/types/contract";

const STYLES = {
  info: "border-neutral-300 bg-neutral-50",
  warning: "border-amber-400 bg-amber-50",
  critical: "border-brand bg-brand-soft",
} as const;

const LABELS = {
  info: "Aviso",
  warning: "Atención",
  critical: "Importante",
} as const;

export default function AlertList({ spec }: { spec: AlertListSpec }) {
  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
      <h3 className="mb-3 text-base font-semibold">{spec.title}</h3>
      <ul className="space-y-3">
        {spec.items.map((item, i) => (
          <li key={i} className={`rounded-xl border-2 p-4 ${STYLES[item.severity]}`}>
            <p className="text-sm font-semibold text-neutral-900">
              <span className="sr-only">{LABELS[item.severity]}: </span>
              {item.title}
            </p>
            <p className="mt-1 text-sm text-neutral-700">{item.detail}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

"use client";

import type { AlertListSpec } from "@/types/contract";

const STYLES = {
  info: "border-neutral-400 bg-neutral-50",
  warning: "border-amber-500 bg-amber-50",
  critical: "border-brand bg-brand-soft",
} as const;

export default function AlertList({ spec }: { spec: AlertListSpec }) {
  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
      <h3 className="mb-3 text-base font-semibold">{spec.title}</h3>
      <ul className="space-y-3">
        {spec.items.map((item, i) => (
          <li key={i} className={`rounded-xl border-2 p-4 ${STYLES[item.severity]}`}>
            {/* R11: no "Aviso:"/severity prefix is glued onto the charge row;
                the title itself already says what the charge is. */}
            <p className="text-base font-semibold text-neutral-900">{item.title}</p>
            <p className="mt-1 text-base text-neutral-800">{item.detail}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

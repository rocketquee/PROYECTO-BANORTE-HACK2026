"use client";

import { Metric, UITone } from "@/types/contract";

const toneClass: Record<UITone, string> = {
  positive: "text-emerald-700",
  negative: "text-brand",
  neutral: "text-ink",
};

export default function FinancialSummary({
  title, metrics, note,
}: { title: string; metrics: Metric[]; note?: string | null }) {
  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
      <h3 className="mb-4 text-base font-semibold">{title}</h3>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4">
        {metrics.map((m, i) => (
          <div key={i} className="rounded-xl bg-neutral-50 p-4">
            <p className="text-base font-medium uppercase tracking-wide text-neutral-700">{m.label}</p>
            <p className={`mt-1 text-xl font-semibold ${toneClass[m.tone ?? "neutral"]}`}>{m.value}</p>
            {m.delta && <p className="mt-0.5 text-base text-neutral-700">{m.delta}</p>}
          </div>
        ))}
      </div>
      {note && <p className="mt-3 text-base text-neutral-700">{note}</p>}
    </div>
  );
}

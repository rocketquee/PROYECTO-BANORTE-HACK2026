"use client";

import type { RecommendationListSpec } from "@/types/contract";

export default function RecommendationList({ spec }: { spec: RecommendationListSpec }) {
  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
      <h3 className="mb-4 text-base font-semibold">{spec.title}</h3>
      <div className="space-y-3">
        {spec.items.map((item, i) => (
          <div key={i} className="flex gap-3 rounded-xl bg-neutral-50 p-4">
            <span
              className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-base ${
                item.kind === "fact" ? "bg-sky-100 text-sky-700" : "bg-amber-100 text-amber-700"
              }`}
              title={item.kind === "fact" ? "Hecho calculado" : "Sugerencia de IA"}
            >
              {item.kind === "fact" ? "✓" : "💡"}
            </span>
            <div>
              <p className="text-base font-medium">{item.title}</p>
              <p className="mt-0.5 text-base text-neutral-600">{item.detail}</p>
              <p className="mt-1 text-base text-neutral-700">
                {item.kind === "fact" ? "Hecho calculado · " : "Sugerencia de IA · "}
                {item.basis}
              </p>
            </div>
          </div>
        ))}
        {spec.items.length === 0 && (
          <p className="text-base text-neutral-700">Sin recomendaciones por ahora.</p>
        )}
      </div>
    </div>
  );
}

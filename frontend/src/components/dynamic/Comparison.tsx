"use client";

import type { ComparisonSpec } from "@/types/contract";

export default function Comparison({ spec }: { spec: ComparisonSpec }) {
  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
      <h3 className="mb-3 text-base font-semibold">{spec.title}</h3>
      <table className="w-full text-left text-base">
        <caption className="sr-only">{spec.title}</caption>
        <thead>
          <tr className="border-b border-neutral-300">
            <th scope="col" className="py-2">Concepto</th>
            <th scope="col" className="py-2 text-right">{spec.column_a}</th>
            <th scope="col" className="py-2 text-right">{spec.column_b}</th>
          </tr>
        </thead>
        <tbody>
          {spec.rows.map((r) => (
            <tr key={r.label} className="border-b border-neutral-200">
              <th scope="row" className="py-2 font-medium">{r.label}</th>
              <td className="py-2 text-right tabular-nums">{r.value_a}</td>
              <td className="py-2 text-right tabular-nums">{r.value_b}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

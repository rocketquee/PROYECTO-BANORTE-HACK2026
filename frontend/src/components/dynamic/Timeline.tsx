"use client";

import type { TimelineSpec } from "@/types/contract";
import { fmtDate } from "@/lib/format";

export default function Timeline({ spec }: { spec: TimelineSpec }) {
  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
      <h3 className="mb-4 text-base font-semibold">{spec.title}</h3>
      <ol className="relative ml-3 border-l-2 border-neutral-300">
        {spec.items.map((item, i) => (
          <li key={i} className="mb-5 ml-5">
            <span
              className="absolute -left-[9px] mt-1.5 h-4 w-4 rounded-full border-2 border-white bg-brand"
              aria-hidden="true"
            />
            <p className="text-sm font-semibold text-neutral-900">{item.title}</p>
            <p className="text-sm text-neutral-600">{fmtDate(item.date)}</p>
            <p className="mt-1 text-sm text-neutral-700">{item.detail}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}

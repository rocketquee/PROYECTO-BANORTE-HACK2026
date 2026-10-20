"use client";

import { useEffect, useState } from "react";

const SIZES = [
  { id: "sm", label: "A-", pct: 87.5, aria: "Reducir tamaño de letra" },
  { id: "md", label: "A", pct: 100, aria: "Tamaño de letra normal" },
  { id: "lg", label: "A+", pct: 112.5, aria: "Aumentar tamaño de letra" },
] as const;

const STORAGE_KEY = "baf.fontsize";

/**
 * WCAG 2.2 AA text-size control. Adjusts the root font size so the whole
 * interface scales. Default is the middle size (18px base).
 */
export default function FontSizeControl() {
  const [size, setSize] = useState<(typeof SIZES)[number]["id"]>("md");

  useEffect(() => {
    const saved = window.localStorage.getItem(STORAGE_KEY) as (typeof SIZES)[number]["id"] | null;
    const initial = saved && SIZES.some((s) => s.id === saved) ? saved : "md";
    setSize(initial);
    apply(initial);
  }, []);

  function apply(id: (typeof SIZES)[number]["id"]) {
    const pct = SIZES.find((s) => s.id === id)?.pct ?? 100;
    document.documentElement.style.fontSize = `${pct}%`;
    window.localStorage.setItem(STORAGE_KEY, id);
  }

  return (
    <div className="flex gap-1" role="group" aria-label="Tamaño de letra">
      {SIZES.map((s) => (
        <button
          key={s.id}
          aria-label={s.aria}
          aria-pressed={size === s.id}
          onClick={() => { setSize(s.id); apply(s.id); }}
          className={`min-h-[44px] min-w-[44px] rounded-lg border text-base font-semibold ${
            size === s.id
              ? "border-brand bg-brand-soft text-brand-dark"
              : "border-white/30 text-white hover:border-white"
          }`}
        >
          {s.label}
        </button>
      ))}
    </div>
  );
}

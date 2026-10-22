"use client";

import { useEffect, useState } from "react";

const SIZES = [
  { id: "sm", label: "A-", pct: 112.5, aria: "Reducir tamaño de letra a 18 px" },
  { id: "md", label: "A", pct: 125, aria: "Tamaño de letra normal, 20 px" },
  { id: "lg", label: "A+", pct: 137.5, aria: "Aumentar tamaño de letra a 22 px" },
] as const;

const STORAGE_KEY = "baf.fontsize";

/**
 * Adjusts the root font size while keeping the smallest preset at 18px.
 */
export default function FontSizeControl({ vertical = false }: { vertical?: boolean }) {
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
    <div className={`flex shrink-0 gap-1 ${vertical ? "flex-col lg:flex-row" : ""}`} role="group" aria-label="Tamaño de letra">
      {SIZES.map((s) => (
        <button
          key={s.id}
          aria-label={s.aria}
          aria-pressed={size === s.id}
          onClick={() => { setSize(s.id); apply(s.id); }}
          className={`min-h-[48px] min-w-[48px] shrink-0 rounded-full border text-base font-semibold ${
            size === s.id
              ? "border-brand bg-brand-soft text-brand-dark"
              : "border-[var(--line)] text-[var(--text)] hover:bg-[var(--surface-subtle)]"
          }`}
        >
          {s.label}
        </button>
      ))}
    </div>
  );
}

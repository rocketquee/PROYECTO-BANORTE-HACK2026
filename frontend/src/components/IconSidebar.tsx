"use client";

import { useState } from "react";
import FontSizeControl from "./FontSizeControl";
import { NAV_ITEMS, type ViewId } from "@/lib/navigation";

function Icon({ path }: { path: string }) {
  return (
    <svg className="h-6 w-6 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.8"
         viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d={path} />
    </svg>
  );
}

export default function IconSidebar({
  view, onChange, dark, onToggleTheme, onOpenHistory,
}: {
  view: ViewId;
  onChange: (view: ViewId) => void;
  dark: boolean;
  onToggleTheme: () => void;
  onOpenHistory: () => void;
}) {
  const [notice, setNotice] = useState("");

  return (
    <aside className="relative z-20 flex h-full min-h-0 w-[76px] shrink-0 flex-col items-center py-3 sm:w-[88px] sm:py-4 lg:w-[248px] lg:px-2">
      <div className="flex h-full min-h-0 w-[60px] flex-col items-center overflow-hidden rounded-full border border-[var(--line)] bg-[var(--surface)] py-3 shadow-sm sm:w-[68px] sm:py-4 lg:w-full lg:items-stretch lg:px-2">
        <button
          type="button"
          onClick={onToggleTheme}
          aria-label={dark ? "Activar modo claro" : "Activar modo oscuro"}
          title={dark ? "Modo claro" : "Modo oscuro"}
          className="flex min-h-[48px] min-w-[48px] shrink-0 items-center justify-center self-center rounded-full text-[var(--accent)] hover:bg-[var(--surface-subtle)]"
        >
          {dark ? <Icon path="M12 3v2m0 14v2M5 12H3m18 0h-2M6.3 6.3 4.9 4.9m14.2 14.2-1.4-1.4M7 17a5 5 0 1 1 10 0" /> : <Icon path="M20.9 13A9 9 0 0 1 11 3.1 9 9 0 1 0 20.9 13z" />}
        </button>

        <div className="my-2 h-px w-9 shrink-0 self-center bg-[var(--line)] lg:w-full" />
        <div className="shrink-0 self-center">
          <FontSizeControl vertical />
        </div>
        <nav
          className="mt-2 hidden min-h-0 w-full flex-1 flex-col gap-1 overflow-y-auto overflow-x-hidden px-1 scrollbar-hidden lg:flex"
          aria-label="Navegación principal"
        >
          {NAV_ITEMS.map((item, index) => (
            <div key={item.id} className="shrink-0">
              {index > 0 && NAV_ITEMS[index - 1].group !== item.group && (
                <div className="my-2 h-px w-full bg-[var(--line)]" aria-hidden="true" />
              )}
              <button
                type="button"
                onClick={() => onChange(item.id)}
                aria-label={item.label}
                aria-current={view === item.id ? "page" : undefined}
                title={item.label}
                className={`flex min-h-[48px] w-full items-center justify-center gap-3 rounded-full px-3 text-left transition-colors lg:justify-start ${
                  view === item.id
                    ? "bg-[#17171D] text-white"
                    : "text-[var(--text)] hover:bg-[var(--surface-subtle)]"
                }`}
              >
                <Icon path={item.icon} />
                <span className="hidden lg:block">{item.label}</span>
              </button>
            </div>
          ))}
        </nav>

        <div className="my-2 h-px w-9 shrink-0 self-center bg-[var(--line)] lg:w-full" />
        <button
          type="button"
          onClick={onOpenHistory}
          aria-label="Historial de conversaciones"
          title="Historial de conversaciones"
          className="flex min-h-[48px] min-w-[48px] shrink-0 items-center justify-center self-center rounded-full text-[var(--text)] hover:bg-[var(--surface-subtle)]"
        >
          <Icon path="M3 12a9 9 0 109-9 9.75 9.75 0 00-6.74 2.74L3 8m0-5v5h5m4-1v5l3 2" />
        </button>
        <button
          type="button"
          onClick={() => setNotice("No hay una sesión real que cerrar en este prototipo educativo.")}
          aria-label="Cerrar sesión (simulado)"
          title="Cerrar sesión (simulado)"
          className="flex min-h-[48px] min-w-[48px] shrink-0 items-center justify-center self-center rounded-full text-[var(--text)] hover:bg-[var(--surface-subtle)]"
        >
          <Icon path="M10 17l5-5-5-5m5 5H3m9-9h6a2 2 0 012 2v14a2 2 0 01-2 2h-6" />
        </button>
        {notice && (
          <div role="status" className="absolute bottom-4 left-[calc(100%+12px)] z-50 w-72 rounded-2xl border border-[var(--line)] bg-[var(--surface)] p-4 text-base text-[var(--text)] shadow-xl">
            <p>{notice}</p>
            <button type="button" onClick={() => setNotice("")} className="mt-2 min-h-[48px] rounded-full px-3 font-medium text-brand-dark hover:bg-[var(--surface-subtle)]">
              Entendido
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}

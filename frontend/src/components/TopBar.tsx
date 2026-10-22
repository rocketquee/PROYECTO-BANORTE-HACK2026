"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { NAV_ITEMS, type ViewId } from "@/lib/navigation";

type Panel = "search" | "notifications" | "help" | null;

function Icon({ path }: { path: string }) {
  return (
    <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8"
         viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d={path} />
    </svg>
  );
}

export default function TopBar({
  view,
  onChange,
}: {
  view: ViewId;
  onChange: (view: ViewId) => void;
}) {
  const [openPanel, setOpenPanel] = useState<Panel>(null);
  const [search, setSearch] = useState("");
  const searchTrigger = useRef<HTMLButtonElement>(null);
  const notificationTrigger = useRef<HTMLButtonElement>(null);
  const helpTrigger = useRef<HTMLButtonElement>(null);
  const panelCloseButton = useRef<HTMLButtonElement>(null);
  const searchInput = useRef<HTMLInputElement>(null);
  const results = useMemo(
    () => NAV_ITEMS.filter((item) => item.label.toLowerCase().includes(search.trim().toLowerCase())),
    [search]
  );

  useEffect(() => {
    if (!openPanel) return;

    const trigger = {
      search: searchTrigger,
      notifications: notificationTrigger,
      help: helpTrigger,
    }[openPanel];

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        setOpenPanel(null);
        trigger.current?.focus();
      }
    }

    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [openPanel]);

  useEffect(() => {
    if (openPanel === "search") searchInput.current?.focus();
    else if (openPanel) panelCloseButton.current?.focus();
  }, [openPanel]);

  function closePanel() {
    if (!openPanel) return;
    const trigger = {
      search: searchTrigger,
      notifications: notificationTrigger,
      help: helpTrigger,
    }[openPanel];
    setOpenPanel(null);
    trigger.current?.focus();
  }

  function selectView(next: ViewId) {
    onChange(next);
    setSearch("");
    setOpenPanel(null);
  }

  return (
    <header className="relative z-30 flex shrink-0 flex-col gap-3 px-3 py-3 sm:px-5 lg:px-7">
      <div className="flex w-full flex-wrap items-center justify-between gap-3">
        <div className="flex min-h-[64px] min-w-fit shrink-0 items-center gap-3 rounded-full border border-[var(--line)] bg-[var(--surface)] px-3 shadow-sm sm:px-5">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-[#F26A4B] text-base font-bold text-white">
            BF
          </div>
          <div className="min-w-0 leading-tight">
            <p className="font-semibold text-[var(--text)]">Banorte AI</p>
            <p className="text-base text-[var(--muted)]">Prototipo educativo</p>
          </div>
        </div>

        <div className="flex min-h-[64px] shrink-0 items-center gap-0.5 rounded-full border border-[var(--line)] bg-[var(--surface)] px-1 shadow-sm sm:gap-1 sm:px-2">
          <button
            ref={searchTrigger}
            type="button"
            onClick={() => {
              setSearch("");
              setOpenPanel((panel) => panel === "search" ? null : "search");
            }}
            aria-label="Buscar secciones"
            aria-expanded={openPanel === "search"}
            aria-controls="topbar-panel"
            className="flex min-h-[48px] min-w-[48px] items-center justify-center rounded-full text-[var(--accent)] hover:bg-[var(--surface-subtle)]"
          >
            <Icon path="M11 19a8 8 0 110-16 8 8 0 010 16zm10 2-4.35-4.35" />
          </button>
          <button
            ref={notificationTrigger}
            type="button"
            onClick={() => setOpenPanel((panel) => panel === "notifications" ? null : "notifications")}
            aria-label="Notificaciones"
            aria-expanded={openPanel === "notifications"}
            aria-controls="topbar-panel"
            className="flex min-h-[48px] min-w-[48px] items-center justify-center rounded-full text-[var(--accent)] hover:bg-[var(--surface-subtle)]"
          >
            <Icon path="M18 8a6 6 0 00-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9m-8 12a2 2 0 004 0" />
          </button>
          <button
            ref={helpTrigger}
            type="button"
            onClick={() => setOpenPanel((panel) => panel === "help" ? null : "help")}
            aria-label="Ayuda"
            aria-expanded={openPanel === "help"}
            aria-controls="topbar-panel"
            className="flex min-h-[48px] min-w-[48px] items-center justify-center rounded-full text-[var(--accent)] hover:bg-[var(--surface-subtle)]"
          >
            <Icon path="M9.1 9a3 3 0 015.8 1c0 2-3 3-3 3m.1 4h.01M22 12a10 10 0 11-20 0 10 10 0 0120 0z" />
          </button>
          <div className="flex min-h-[48px] items-center gap-2 rounded-full bg-[var(--surface-subtle)] py-1 pl-1 pr-2 sm:gap-3 sm:pr-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#FCE8E2] font-semibold text-[#742515]">
              AG
            </div>
            <div className="hidden leading-tight xl:block">
              <p className="font-semibold text-[var(--text)]">Ana García</p>
              <p className="text-base text-[var(--muted)]">ana.garcia@example.test</p>
            </div>
          </div>
        </div>
      </div>

      <div className="w-full lg:hidden">
        <label className="sr-only" htmlFor="mobile-section-menu">Sección</label>
        <select
          id="mobile-section-menu"
          value={view}
          onChange={(event) => selectView(event.target.value as ViewId)}
          className="min-h-[48px] w-full rounded-full border border-[var(--line)] bg-[var(--surface)] px-5 font-medium text-[var(--text)] shadow-sm"
        >
          {NAV_ITEMS.map((item) => (
            <option key={item.id} value={item.id}>{item.label}</option>
          ))}
        </select>
      </div>

      {openPanel && (
        <section
          id="topbar-panel"
          role="dialog"
          aria-modal="false"
          aria-labelledby="topbar-panel-title"
          className="absolute right-3 top-[calc(100%-4px)] z-50 w-[min(380px,calc(100vw-100px))] rounded-2xl border border-[var(--line)] bg-[var(--surface)] p-4 shadow-xl sm:right-5"
        >
          <div className="flex items-center justify-between gap-3">
            <h2 id="topbar-panel-title" className="font-semibold text-[var(--text)]">
              {openPanel === "search" ? "Buscar secciones" : openPanel === "notifications" ? "Notificaciones" : "Ayuda"}
            </h2>
            <button
              ref={panelCloseButton}
              type="button"
              onClick={closePanel}
              aria-label="Cerrar panel"
              className="min-h-[48px] min-w-[48px] rounded-full text-[var(--text)] hover:bg-[var(--surface-subtle)]"
            >
              ×
            </button>
          </div>
          {openPanel === "search" ? (
            <>
              <label className="sr-only" htmlFor="section-search">Buscar una sección</label>
              <input
                ref={searchInput}
                id="section-search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Buscar una sección…"
                className="mt-2 min-h-[48px] w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-4 text-base text-[var(--text)]"
              />
              <div className="mt-2 max-h-64 overflow-y-auto">
                {results.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => selectView(item.id)}
                    className="flex min-h-[48px] w-full items-center rounded-xl px-3 text-left text-[var(--text)] hover:bg-[var(--surface-subtle)]"
                  >
                    {item.label}
                  </button>
                ))}
                {results.length === 0 && <p className="p-3 text-base text-[var(--muted)]">Sin resultados</p>}
              </div>
            </>
          ) : openPanel === "notifications" ? (
            <p className="mt-2 text-base text-[var(--muted)]">
              No tienes avisos nuevos. La información de esta aplicación es ficticia.
            </p>
          ) : (
            <div className="mt-2 space-y-2 text-base text-[var(--muted)]">
              <p>Este prototipo educativo muestra información ficticia.</p>
              <p>Usa la barra lateral para cambiar de sección y el historial para volver a una conversación.</p>
            </div>
          )}
        </section>
      )}
    </header>
  );
}

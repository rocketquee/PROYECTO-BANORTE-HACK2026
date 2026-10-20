"use client";

import { useEffect, useReducer, useState } from "react";
import Sidebar, { type ViewId } from "@/components/Sidebar";
import DashboardView from "@/components/DashboardView";
import AgentView from "@/components/AgentView";
import SectionView from "@/components/SectionView";

const VIEW_KEY = "baf.view";

const SECTIONS: ViewId[] = [
  "cuentas", "movimientos", "tarjetas", "pagos", "contactos", "creditos",
  "ahorro", "inversiones", "seguros", "presupuesto", "notificaciones",
  "perfil", "ayuda",
];

export default function Home() {
  const [view, setView] = useState<ViewId>("asistente");
  const [menuOpen, setMenuOpen] = useState(false);
  const [pendingQuestion, setPendingQuestion] = useState<{ text: string; nonce: number } | null>(null);
  const [refreshKey, bumpRefresh] = useReducer((x: number) => x + 1, 0);

  useEffect(() => {
    const saved = window.localStorage.getItem(VIEW_KEY) as ViewId | null;
    if (saved) setView(saved);
  }, []);

  function changeView(next: ViewId) {
    setView(next);
    window.localStorage.setItem(VIEW_KEY, next);
  }

  function askAssistant(question: string) {
    setPendingQuestion({ text: question, nonce: Date.now() });
    changeView("asistente");
  }

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Desktop sidebar */}
      <div className="hidden md:flex">
        <Sidebar view={view} onChange={changeView} />
      </div>

      {/* Mobile drawer */}
      {menuOpen && (
        <div className="fixed inset-0 z-40 flex md:hidden" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-black/50" onClick={() => setMenuOpen(false)}
               aria-hidden="true" />
          <div className="relative z-50">
            <Sidebar view={view} onChange={changeView} onClose={() => setMenuOpen(false)} />
          </div>
        </div>
      )}

      <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <div className="flex items-center gap-3 border-b border-neutral-200 bg-white px-4 py-2 md:hidden">
          <button
            onClick={() => setMenuOpen(true)}
            aria-label="Abrir menú"
            className="min-h-[48px] min-w-[48px] rounded-lg border border-neutral-300 text-xl"
          >
            ☰
          </button>
          <p className="font-semibold">Banorte AI Finanzas</p>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {view === "dashboard" ? (
            <DashboardView refreshKey={refreshKey} />
          ) : view === "asistente" ? (
            <AgentView
              onGoalsChanged={bumpRefresh}
              onNavigate={(v) => changeView(v as ViewId)}
              pendingQuestion={pendingQuestion}
            />
          ) : SECTIONS.includes(view) ? (
            <SectionView section={view} onAskAssistant={askAssistant} refreshKey={refreshKey} />
          ) : (
            <AgentView
              onGoalsChanged={bumpRefresh}
              onNavigate={(v) => changeView(v as ViewId)}
              pendingQuestion={pendingQuestion}
            />
          )}
        </div>
      </main>
    </div>
  );
}

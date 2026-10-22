"use client";

import { useEffect, useReducer, useState } from "react";
import AppShell from "@/components/AppShell";
import DashboardView from "@/components/DashboardView";
import AgentView from "@/components/AgentView";
import CardsView from "@/components/CardsView";
import SectionView from "@/components/SectionView";
import { VIEW_META, type ViewId } from "@/lib/navigation";
import { chatActions } from "@/lib/chatStore";

const VIEW_KEY = "baf.view";

const SECTIONS: ViewId[] = [
  "cuentas", "movimientos", "tarjetas", "pagos", "contactos", "creditos",
  "ahorro", "inversiones", "seguros", "presupuesto", "notificaciones",
  "perfil", "ayuda",
];

function isViewId(value: string | null): value is ViewId {
  return value !== null && [
    "dashboard", "asistente", "cuentas", "movimientos", "tarjetas", "pagos",
    "contactos", "creditos", "ahorro", "inversiones", "seguros",
    "presupuesto", "notificaciones", "perfil", "ayuda",
  ].includes(value);
}

export default function Home() {
  const [view, setView] = useState<ViewId>("asistente");
  const [pendingQuestion, setPendingQuestion] = useState<{ text: string; nonce: number } | null>(null);
  const [refreshKey, bumpRefresh] = useReducer((x: number) => x + 1, 0);

  useEffect(() => {
    const saved = window.localStorage.getItem(VIEW_KEY);
    if (isViewId(saved)) setView(saved);
  }, []);

  function changeView(next: ViewId) {
    setView(next);
    window.localStorage.setItem(VIEW_KEY, next);
  }

  function askAssistant(question: string) {
    setPendingQuestion({ text: question, nonce: Date.now() });
    changeView("asistente");
  }

  const primaryAction = view === "dashboard"
    ? { label: "Actualizar resumen", run: bumpRefresh }
    : view === "asistente"
      ? { label: "+ Nueva conversación", run: chatActions.newConversation }
      : {
          label: "Consultar al asistente",
          run: () => askAssistant(VIEW_META[view].question),
        };

  return (
    <AppShell view={view} onChange={changeView}>
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        {view !== "tarjetas" && (
          <div className="flex shrink-0 flex-wrap items-center justify-between gap-4 px-5 pb-4 pt-3 sm:px-7 lg:px-9">
            <div className="min-w-0">
              <h1 className="text-2xl font-semibold tracking-tight text-[var(--text)] sm:text-3xl">
                {VIEW_META[view].title}
              </h1>
              <p className="mt-1 text-base text-[var(--muted)]">{VIEW_META[view].description}</p>
            </div>
            <button
              type="button"
              onClick={primaryAction.run}
              className="min-h-[48px] shrink-0 rounded-full bg-[#17171D] px-6 font-semibold text-white transition-colors hover:bg-[#33333D]"
            >
              {primaryAction.label}
            </button>
          </div>
        )}

        <div className="min-h-0 flex-1 overflow-hidden px-5 pb-5 sm:px-7 lg:px-9">
          <section
            aria-label={`Contenido: ${VIEW_META[view].title}`}
            className="h-full min-h-0 overflow-hidden rounded-3xl border border-[var(--line)] bg-[var(--surface)] shadow-sm"
          >
            <div className="h-full min-h-0 overflow-y-auto">
              {view === "dashboard" ? (
                <DashboardView refreshKey={refreshKey} />
              ) : view === "tarjetas" ? (
                <CardsView />
              ) : view === "asistente" ? (
                <AgentView
                  onGoalsChanged={bumpRefresh}
                  onNavigate={(v) => changeView(v as ViewId)}
                  pendingQuestion={pendingQuestion}
                />
              ) : SECTIONS.includes(view) ? (
                <SectionView section={view} refreshKey={refreshKey} />
              ) : (
                <AgentView
                  onGoalsChanged={bumpRefresh}
                  onNavigate={(v) => changeView(v as ViewId)}
                  pendingQuestion={pendingQuestion}
                />
              )}
            </div>
          </section>
        </div>
      </div>
    </AppShell>
  );
}

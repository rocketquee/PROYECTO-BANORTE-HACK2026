"use client";

import { useReducer, useState } from "react";
import AppShell from "@/components/AppShell";
import DashboardView from "@/components/DashboardView";
import AgentView from "@/components/AgentView";
import CardsView from "@/components/CardsView";
import SectionView from "@/components/SectionView";
import ViewTransition from "@/components/ViewTransition";
import { VIEW_META, type ViewId } from "@/lib/navigation";
import { chatActions } from "@/lib/chatStore";

const SECTIONS: ViewId[] = [
  "cuentas", "movimientos", "tarjetas", "pagos", "contactos", "creditos",
  "ahorro", "inversiones", "seguros", "presupuesto", "notificaciones",
  "perfil", "ayuda",
];

export default function Home() {
  const [view, setView] = useState<ViewId>("inicio");
  const [pendingQuestion, setPendingQuestion] = useState<{ text: string; nonce: number } | null>(null);
  const [refreshKey, bumpRefresh] = useReducer((x: number) => x + 1, 0);

  function changeView(next: ViewId) {
    setView(next);
  }

  function askAssistant(question: string) {
    setPendingQuestion({ text: question, nonce: Date.now() });
    changeView("asistente");
  }

  function navigateFromAssistant(target: string) {
    changeView(target as ViewId);
  }

  const primaryAction = view === "inicio"
    ? { label: "Hablar con el asistente", run: () => changeView("asistente") }
    : view === "dashboard"
    ? { label: "Actualizar resumen", run: bumpRefresh }
    : view === "asistente"
      ? { label: "+ Nueva conversación", run: chatActions.newConversation }
      : {
          label: "Consultar al asistente",
          run: () => askAssistant(VIEW_META[view].question),
        };

  return (
    <AppShell view={view} onChange={changeView}>
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
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
            {view === "inicio" ? (
              <CardsView
                variant="home"
                onOpenSummary={() => changeView("dashboard")}
              />
            ) : view === "asistente" ? (
              <AgentView
                onGoalsChanged={bumpRefresh}
                onNavigate={navigateFromAssistant}
                pendingQuestion={pendingQuestion}
              />
            ) : (
              <ViewTransition view={view}>
                {view === "dashboard" ? (
                  <DashboardView refreshKey={refreshKey} />
                ) : view === "tarjetas" ? (
                  <CardsView onOpenSummary={() => changeView("dashboard")} />
                ) : SECTIONS.includes(view) ? (
                  <SectionView section={view} refreshKey={refreshKey} />
                ) : (
                  <DashboardView refreshKey={refreshKey} />
                )}
              </ViewTransition>
            )}
          </section>
        </div>
      </div>
    </AppShell>
  );
}

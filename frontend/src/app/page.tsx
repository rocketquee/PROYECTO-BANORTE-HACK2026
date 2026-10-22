"use client";

import { useEffect, useReducer, useState } from "react";
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
  const [assistantOpen, setAssistantOpen] = useState(true);
  const [mobileAssistantOpen, setMobileAssistantOpen] = useState(false);
  const [pendingQuestion, setPendingQuestion] = useState<{ text: string; nonce: number } | null>(null);
  const [refreshKey, bumpRefresh] = useReducer((x: number) => x + 1, 0);

  useEffect(() => {
    const media = window.matchMedia("(min-width: 1024px)");
    const syncAssistantToViewport = () => {
      setAssistantOpen(media.matches);
      setMobileAssistantOpen(!media.matches);
    };
    syncAssistantToViewport();
    media.addEventListener("change", syncAssistantToViewport);
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.altKey && event.key.toLowerCase() === "a") {
        event.preventDefault();
        if (media.matches) setAssistantOpen((open) => !open);
        else setMobileAssistantOpen((open) => !open);
      }
      if (event.key === "Escape") setMobileAssistantOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      media.removeEventListener("change", syncAssistantToViewport);
    };
  }, []);

  function changeView(next: ViewId) {
    if (next === "asistente") {
      if (window.matchMedia("(min-width: 1024px)").matches) setAssistantOpen(true);
      else setMobileAssistantOpen(true);
      return;
    }
    setView(next);
  }

  function askAssistant(question: string) {
    setPendingQuestion({ text: question, nonce: Date.now() });
    changeView("asistente");
  }

  function navigateFromAssistant(target: string) {
    changeView(target as ViewId);
    setMobileAssistantOpen(false);
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
      <div className="flex min-h-0 min-w-0 flex-1 overflow-hidden">
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        {view !== "tarjetas" && (
          <div className="flex shrink-0 flex-wrap items-center justify-between gap-4 px-5 pb-4 pt-3 sm:px-7 lg:px-9">
            <div className="min-w-0">
              <h1 className="text-2xl font-semibold tracking-tight text-[var(--text)] sm:text-3xl">
                {VIEW_META[view].title}
              </h1>
              <p className="mt-1 text-base text-[var(--muted)]">{VIEW_META[view].description}</p>
            </div>
            {view !== "inicio" && (
              <button
                type="button"
                onClick={primaryAction.run}
                className="min-h-[48px] shrink-0 rounded-full bg-[#17171D] px-6 font-semibold text-white transition-colors hover:bg-[#33333D]"
              >
                {primaryAction.label}
              </button>
            )}
          </div>
        )}

        <div className="min-h-0 flex-1 overflow-hidden px-5 pb-5 sm:px-7 lg:px-9">
          <section
            aria-label={`Contenido: ${VIEW_META[view].title}`}
            className="h-full min-h-0 overflow-hidden rounded-3xl border border-[var(--line)] bg-[var(--surface)] shadow-sm"
          >
            <ViewTransition view={view}>
              {view === "dashboard" ? (
                <DashboardView refreshKey={refreshKey} />
              ) : view === "tarjetas" || view === "inicio" ? (
                <CardsView
                  variant={view === "inicio" ? "home" : "cards"}
                  onOpenSummary={() => changeView("dashboard")}
                />
              ) : SECTIONS.includes(view) ? (
                <SectionView section={view} refreshKey={refreshKey} />
              ) : (
                <DashboardView refreshKey={refreshKey} />
              )}
            </ViewTransition>
          </section>
        </div>
      </div>
      {assistantOpen && (
        <aside
          aria-label="Asistente financiero"
          className="hidden min-h-0 w-[min(420px,38vw)] shrink-0 flex-col border-l border-[var(--line)] bg-[var(--surface)] lg:flex"
        >
          <AgentView
            onGoalsChanged={bumpRefresh}
            onNavigate={navigateFromAssistant}
            pendingQuestion={pendingQuestion}
            onClose={() => setAssistantOpen(false)}
          />
        </aside>
      )}
      {!assistantOpen && (
        <button
          type="button"
          onClick={() => setAssistantOpen(true)}
          aria-label="Abrir asistente (Alt+A)"
          title="Abrir asistente (Alt+A)"
          className="fixed right-0 top-1/2 z-30 hidden min-h-[48px] -translate-y-1/2 rounded-l-xl bg-brand px-3 py-4 text-[18px] font-semibold text-white shadow-lg focus-visible:outline focus-visible:outline-4 focus-visible:outline-offset-2 focus-visible:outline-brand lg:block"
        >
          Asistente
        </button>
      )}
      <button
        type="button"
        onClick={() => setMobileAssistantOpen(true)}
        aria-label="Abrir asistente"
        className="fixed bottom-4 right-4 z-40 min-h-[56px] min-w-[56px] rounded-full bg-brand px-5 text-[18px] font-semibold text-white shadow-xl focus-visible:outline focus-visible:outline-4 focus-visible:outline-offset-2 focus-visible:outline-brand lg:hidden"
      >
        Chat
      </button>
      {mobileAssistantOpen && (
        <div className="fixed inset-0 z-50 flex h-[100dvh] w-full flex-col bg-[var(--surface)] lg:hidden">
          <AgentView
            onGoalsChanged={bumpRefresh}
            onNavigate={navigateFromAssistant}
            pendingQuestion={pendingQuestion}
            onClose={() => setMobileAssistantOpen(false)}
          />
        </div>
      )}
      </div>
    </AppShell>
  );
}

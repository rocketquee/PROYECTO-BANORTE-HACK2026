"use client";

import { useState } from "react";
import FontSizeControl from "./FontSizeControl";
import { chatActions, useChatStore } from "@/lib/chatStore";

export type ViewId =
  | "dashboard" | "asistente" | "cuentas" | "movimientos" | "tarjetas"
  | "pagos" | "contactos" | "creditos" | "ahorro" | "inversiones"
  | "seguros" | "presupuesto" | "notificaciones" | "perfil" | "ayuda";

interface Props {
  view: ViewId;
  onChange: (view: ViewId) => void;
  onClose?: () => void; // mobile drawer
}

const GROUPS: { title: string; items: { id: ViewId; label: string; icon: string }[] }[] = [
  {
    title: "Principal",
    items: [
      { id: "dashboard", label: "Dashboard", icon: "M3 12l9-9 9 9M5 10v10h5v-6h4v6h5V10" },
      { id: "asistente", label: "Asistente IA", icon: "M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" },
    ],
  },
  {
    title: "Mis finanzas",
    items: [
      { id: "cuentas", label: "Mis cuentas", icon: "M3 21h18M5 21V7l7-4 7 4v14M9 21v-6h6v6" },
      { id: "movimientos", label: "Movimientos", icon: "M4 6h16M4 12h16M4 18h10" },
      { id: "tarjetas", label: "Tarjetas", icon: "M2 8h20M2 6a2 2 0 012-2h16a2 2 0 012 2v12a2 2 0 01-2 2H4a2 2 0 01-2-2z" },
      { id: "pagos", label: "Pagos y transferencias", icon: "M7 10h10M7 14h4m9-2a9 9 0 11-18 0 9 9 0 0118 0z" },
      { id: "presupuesto", label: "Presupuesto", icon: "M12 8v8m-4-4h8M3 12a9 9 0 1018 0 9 9 0 00-18 0z" },
      { id: "creditos", label: "Créditos y simulador", icon: "M12 2v20m5-15H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6" },
      { id: "ahorro", label: "Ahorro y metas", icon: "M12 3v2m0 14v2M5 12H3m18 0h-2M6.3 6.3L4.9 4.9m12.8 1.4l1.4-1.4M7 17a5 5 0 1110 0 5 5 0 01-10 0z" },
      { id: "inversiones", label: "Inversiones", icon: "M3 17l6-6 4 4 8-8M14 7h7v7" },
      { id: "seguros", label: "Seguros", icon: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z" },
    ],
  },
  {
    title: "Más",
    items: [
      { id: "notificaciones", label: "Notificaciones", icon: "M15 17h5l-1.4-1.4A2 2 0 0118 14.2V11a6 6 0 00-4-5.7V5a2 2 0 10-4 0v.3A6 6 0 006 11v3.2a2 2 0 01-.6 1.4L4 17h11zm-3 4a2 2 0 002-2h-4a2 2 0 002 2z" },
      { id: "perfil", label: "Perfil y preferencias", icon: "M16 7a4 4 0 11-8 0 4 4 0 018 0zM4 21a8 8 0 0116 0" },
      { id: "ayuda", label: "Ayuda y seguridad", icon: "M12 17h.01M12 14a2.5 2.5 0 10-2.5-2.5M12 21a9 9 0 110-18 9 9 0 010 18z" },
    ],
  },
];

function NavButton({ item, active, onClick }: {
  item: { id: ViewId; label: string; icon: string };
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      className={`flex min-h-[48px] w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-base transition-colors ${
        active ? "bg-brand/25 font-semibold text-white" : "text-neutral-300 hover:bg-white/10 hover:text-white"
      }`}
    >
      <svg className="h-5 w-5 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" d={item.icon} />
      </svg>
      {item.label}
    </button>
  );
}

export default function Sidebar({ view, onChange, onClose }: Props) {
  const store = useChatStore();
  const [historyOpen, setHistoryOpen] = useState(false);

  function go(id: ViewId) {
    onChange(id);
    onClose?.();
  }

  return (
    <aside className="flex h-full min-h-0 w-64 shrink-0 flex-col overflow-hidden bg-ink text-neutral-300">
      <div className="flex shrink-0 items-center gap-3 px-5 py-5">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand font-bold text-white">
          BF
        </div>
        <div className="min-w-0">
          <p className="truncate text-base font-semibold text-white">Banorte AI Finanzas</p>
          <p className="text-base text-neutral-300">Prototipo educativo</p>
        </div>
      </div>

      <div className="shrink-0 px-5 pb-4">
        <FontSizeControl />
      </div>

      {/* The sidebar owns its scroll when content doesn't fit (UI-1). */}
      <nav className="min-h-0 flex-1 overflow-y-auto px-3" aria-label="Secciones">
        {GROUPS.map((group) => (
          <div key={group.title} className="mb-4">
            <p className="mb-1 px-3 text-base font-semibold uppercase tracking-wide text-neutral-300">
              {group.title}
            </p>
            {group.items.map((item) => (
              <NavButton key={item.id} item={item}
                         active={view === item.id} onClick={() => go(item.id)} />
            ))}
          </div>
        ))}

        {/* Conversation history (BUG-002) */}
        <div className="mb-4">
          <button
            onClick={() => setHistoryOpen(!historyOpen)}
            aria-expanded={historyOpen}
            className="flex min-h-[48px] w-full items-center justify-between rounded-lg px-3 py-2.5 text-left text-base text-neutral-300 hover:bg-white/10 hover:text-white"
          >
            <span className="font-semibold uppercase tracking-wide text-neutral-300">
              Historial de conversaciones
            </span>
            <span aria-hidden="true">{historyOpen ? "▾" : "▸"}</span>
          </button>
          {historyOpen && (
            <div className="mt-1 max-h-64 space-y-1 overflow-y-auto pr-1">
              <button
                onClick={() => { chatActions.newConversation(); go("asistente"); }}
                className="flex min-h-[48px] w-full items-center gap-2 rounded-lg border border-white/20 px-3 py-2 text-base text-white hover:border-white"
              >
                + Nueva conversación
              </button>
              {store.conversations.map((c) => (
                <div key={c.id}
                     className={`group flex items-center gap-1 rounded-lg px-2 py-1.5 ${
                       c.id === store.activeId ? "bg-brand/20" : "hover:bg-white/5"
                     }`}>
                  <button
                    onClick={() => { chatActions.selectConversation(c.id); go("asistente"); }}
                    className="min-w-0 flex-1 text-left"
                  >
                    <p className="truncate text-base text-neutral-100">{c.title}</p>
                    <p className="text-base text-neutral-300">
                      {new Date(c.createdAt).toLocaleDateString("es-MX", {
                        day: "numeric", month: "short",
                      })}
                    </p>
                  </button>
                  <button
                    aria-label={`Borrar conversación: ${c.title}`}
                    onClick={() => {
                      if (window.confirm(`¿Borrar la conversación «${c.title}»? Esta acción no se puede deshacer.`)) {
                        chatActions.deleteConversation(c.id);
                      }
                    }}
                    className="min-h-[48px] min-w-[48px] rounded text-neutral-300 hover:text-brand"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </nav>

      <div className="shrink-0 border-t border-white/10 px-5 py-4 text-base leading-relaxed text-neutral-300">
        Prototipo educativo con datos ficticios.
        <br />
        No afiliado a Banorte.
      </div>
    </aside>
  );
}

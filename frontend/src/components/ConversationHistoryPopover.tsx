"use client";

import { useEffect } from "react";
import { chatActions, useChatStore } from "@/lib/chatStore";
import type { ViewId } from "@/lib/navigation";

export default function ConversationHistoryPopover({
  onClose, onChange,
}: {
  onClose: () => void;
  onChange: (view: ViewId) => void;
}) {
  const store = useChatStore();

  useEffect(() => {
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  function selectConversation(id: string) {
    chatActions.selectConversation(id);
    onChange("asistente");
    onClose();
  }

  function newConversation() {
    chatActions.newConversation();
    onChange("asistente");
    onClose();
  }

  return (
    <section
      aria-label="Historial de conversaciones"
      className="absolute left-[84px] top-[92px] z-50 flex max-h-[min(70dvh,620px)] w-[min(340px,calc(100vw-104px))] flex-col rounded-3xl border border-[var(--line)] bg-[var(--surface)] p-4 shadow-xl sm:left-[96px] lg:left-[260px]"
    >
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-semibold">Historial</h2>
        <button type="button" onClick={onClose} aria-label="Cerrar historial"
                className="min-h-[48px] min-w-[48px] rounded-full text-[var(--text)] hover:bg-[var(--surface-subtle)]">
          ×
        </button>
      </div>
      <button type="button" onClick={newConversation}
              className="mt-2 min-h-[48px] rounded-full bg-[#17171D] px-4 font-medium text-white hover:bg-[#33333D]">
        + Nueva conversación
      </button>
      <ul className="mt-2 min-h-0 space-y-1 overflow-y-auto">
        {store.conversations.map((conversation) => (
          <li key={conversation.id} className={`flex items-center gap-1 rounded-2xl px-2 ${
            conversation.id === store.activeId ? "bg-[var(--surface-subtle)]" : ""
          }`}>
            <button type="button" onClick={() => selectConversation(conversation.id)}
                    className="min-h-[56px] min-w-0 flex-1 rounded-xl px-2 text-left hover:bg-[var(--surface-subtle)]">
              <span className="block truncate font-medium">{conversation.title}</span>
              <span className="block text-base text-[var(--muted)]">
                {new Date(conversation.createdAt).toLocaleDateString("es-MX", {
                  day: "numeric", month: "short",
                })}
              </span>
            </button>
            <button
              type="button"
              aria-label={`Borrar conversación: ${conversation.title}`}
              onClick={() => {
                if (window.confirm(`¿Borrar la conversación «${conversation.title}»? Esta acción no se puede deshacer.`)) {
                  chatActions.deleteConversation(conversation.id);
                }
              }}
              className="min-h-[48px] min-w-[48px] rounded-full text-[var(--muted)] hover:bg-[var(--surface-subtle)] hover:text-brand-dark"
            >
              ×
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

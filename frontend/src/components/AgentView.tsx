"use client";

import { useEffect, useRef, useState } from "react";
import type { ChatResponse, UISpec } from "@/types/contract";
import { post } from "@/lib/api";
import DynamicRenderer from "@/components/dynamic/DynamicRenderer";
import { activeConversation, chatActions, useChatStore, type ChatMsg } from "@/lib/chatStore";

const QUICK_PROMPTS = [
  "¿En qué estoy gastando más dinero?",
  "¿Cómo han cambiado mis gastos en los últimos 4 meses?",
  "Analiza mis gastos de este mes",
  "Ayúdame a ahorrar $5,000",
  "¿Cuánto podría pagar mensualmente por un crédito?",
  "Muéstrame mis movimientos y clasifícalos",
  "¿Qué cargos fijos tengo?",
  "Recomiéndame cómo mejorar mis gastos",
];

type OnNavigate = (view: string) => void;

export default function AgentView({
  onGoalsChanged,
  onNavigate,
  pendingQuestion,
}: {
  onGoalsChanged: () => void;
  onNavigate: OnNavigate;
  pendingQuestion?: { text: string; nonce: number } | null;
}) {
  const store = useChatStore();
  const conversation = activeConversation(store);
  const messages = conversation.messages;
  const loading = store.loading;

  const [input, setInput] = useState("");
  const [lastFailed, setLastFailed] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages.length, loading]);

  // Questions sent from other sections ("Preguntar al asistente sobre esto").
  const lastNonce = useRef(0);
  useEffect(() => {
    if (pendingQuestion && pendingQuestion.nonce !== lastNonce.current) {
      lastNonce.current = pendingQuestion.nonce;
      send(pendingQuestion.text);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingQuestion?.nonce]);

  async function send(text: string) {
    const message = text.trim();
    if (!message || loading) return;
    setInput("");
    setLastFailed(null);
    chatActions.addMessage({ role: "user", text: message });
    chatActions.setLoading(true);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const resp = await post<ChatResponse>("/api/agent/chat", {
        message,
        history: conversation.history.slice(-6),
      }, controller.signal);
      chatActions.addMessage({ role: "assistant", resp });
      // Assistant-driven navigation ("llévame a mis tarjetas").
      const nav = resp.interaction_context?.navigate;
      if (typeof nav === "string" && nav) onNavigate(nav);
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setLastFailed(message);
        chatActions.addMessage({
          role: "system",
          error: "No pude hacer eso. ¿Lo intentamos de otra forma? Revisa que el backend esté encendido y presiona «Reintentar».",
        });
      }
    } finally {
      chatActions.setLoading(false);
      abortRef.current = null;
    }
  }

  function cancel() {
    abortRef.current?.abort();
  }

  async function confirmPending(actionId: string, msgIndex: number) {
    chatActions.setLoading(true);
    try {
      const resp = await post<ChatResponse>("/api/agent/confirm", { action_id: actionId });
      chatActions.updateMessage(msgIndex, (m) =>
        m.resp ? { ...m, resp: { ...m.resp, pending_action: null } } : m);
      chatActions.addMessage({ role: "assistant", resp });
      onGoalsChanged();
    } catch (err) {
      chatActions.addMessage({ role: "system", error: (err as Error).message });
    } finally {
      chatActions.setLoading(false);
    }
  }

  function goalCreatedFromForm(name: string, target: number) {
    chatActions.addMessage({
      role: "assistant",
      resp: {
        message: `Meta "${name}" guardada con objetivo de $${target.toLocaleString("es-MX")}. Ya aparece en tu panel de metas.`,
        mode: "demo", ui: [], tools_used: ["create_savings_goal"],
      },
    });
    onGoalsChanged();
  }

  return (
    <div className={`grid h-full min-h-0 grid-cols-1 ${store.detail ? "xl:grid-cols-[1fr_420px]" : ""}`}>
      <div className="flex h-full min-h-0 flex-col">
      {/* Chat header — business language only (BUG-003) */}
      <div className="shrink-0 border-b border-neutral-200 bg-white px-6 py-4">
        <h1 className="text-lg font-semibold">Asistente financiero</h1>
        <p className="text-base text-neutral-700">
          Te ayudo a revisar tus gastos, ahorro, créditos y presupuesto con tus propios datos.
        </p>
      </div>

      <div ref={scrollRef} className="min-h-0 flex-1 space-y-4 overflow-y-auto p-6">
        {messages.length === 0 && (
          <div className="rounded-2xl bg-white p-6 text-base shadow-sm">
            <p className="text-lg font-medium">¡Hola! Soy tu asistente financiero.</p>
            <p className="mt-2 text-neutral-700">
              Puedo mostrarte tus gastos, ayudarte a ahorrar, simular un crédito y organizar tu
              presupuesto. Elige una opción o escribe lo que necesites:
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {QUICK_PROMPTS.map((p) => (
                <button
                  key={p}
                  onClick={() => send(p)}
                  className="min-h-[48px] rounded-full border-2 border-neutral-300 bg-white px-4 py-2.5 text-base text-neutral-800 hover:border-brand hover:text-brand"
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m: ChatMsg, i: number) => {
          if (m.role === "user") {
            return (
              <div key={`${conversation.id}-${i}`} className="flex justify-end">
                <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-brand px-4 py-3 text-base text-white">
                  {m.text}
                </div>
              </div>
            );
          }
          if (m.role === "system") {
            return (
              <div key={`${conversation.id}-${i}`} className="rounded-xl bg-amber-50 p-4 text-base text-amber-900">
                <p>{m.error}</p>
                {lastFailed && (
                  <button
                    onClick={() => send(lastFailed)}
                    className="mt-3 min-h-[48px] rounded-xl bg-brand px-5 py-3 text-base font-medium text-white hover:bg-brand-dark"
                  >
                    Reintentar
                  </button>
                )}
              </div>
            );
          }
          const hasUi = (m.resp?.ui?.length ?? 0) > 0;
          const msgKey = `${conversation.id}-${i}`;
          const isDetailOpen = store.detailKey === msgKey;
          return (
            <div key={`${conversation.id}-${i}`} className="space-y-3">
              <div className="flex justify-start">
                <div className="max-w-[92%] rounded-2xl rounded-bl-sm bg-white px-4 py-3 text-base shadow-sm">
                  <p className="whitespace-pre-wrap">{m.resp?.message}</p>
                  {hasUi && (
                    <button
                      onClick={() =>
                        chatActions.setDetail(
                          isDetailOpen ? null : (m.resp!.ui as UISpec[]),
                          isDetailOpen ? null : msgKey
                        )
                      }
                      className="mt-3 min-h-[48px] rounded-xl border-2 border-brand px-4 py-2.5 text-base font-medium text-brand hover:bg-brand-soft"
                    >
                      {isDetailOpen ? "Ocultar detalle expandido" : "Ver detalle expandido"}
                    </button>
                  )}
                </div>
              </div>
              {m.resp?.ui?.map((spec, j) => (
                <DynamicRenderer
                  key={`${conversation.id}-${i}-${j}`}
                  spec={spec}
                  onAsk={send}
                  onGoalCreated={goalCreatedFromForm}
                  onGoalsChanged={onGoalsChanged}
                  pendingAction={m.resp?.pending_action
                    ? { id: m.resp.pending_action.id, description: m.resp.pending_action.description }
                    : null}
                  onConfirmPending={(actionId) => confirmPending(actionId, i)}
                />
              ))}
            </div>
          );
        })}

        {loading && (
          <div className="flex items-center gap-3 text-base text-neutral-700">
            <span className="h-3 w-3 animate-pulse rounded-full bg-brand" aria-hidden="true" />
            <span aria-live="polite">Estoy revisando tus datos…</span>
            <button
              onClick={cancel}
              className="min-h-[48px] rounded-lg border border-neutral-400 px-3 py-2 text-base text-neutral-800 hover:border-brand"
            >
              Cancelar
            </button>
          </div>
        )}
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); send(input); }}
        className="shrink-0 border-t border-neutral-200 bg-white p-4"
      >
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Escribe tu solicitud financiera…"
            className="min-h-[48px] flex-1 rounded-xl border border-neutral-300 px-4 py-3 text-base"
            aria-label="Mensaje para el asistente"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="min-h-[48px] rounded-xl bg-brand px-6 py-3 text-base font-semibold text-white hover:bg-brand-dark disabled:cursor-not-allowed disabled:bg-neutral-600 disabled:text-white"
          >
            Enviar
          </button>
        </div>
      </form>
      </div>

      {/* Expanded-detail panel (UI-2): only rendered while a result is open,
          so it never reserves space nor shows placeholder copy when closed. */}
      {store.detail && (
        <div className="flex h-full min-h-0 flex-col overflow-hidden border-l border-neutral-200 bg-neutral-50">
          <div className="flex shrink-0 items-center justify-between gap-3 border-b border-neutral-200 bg-neutral-50 px-5 py-4">
            <div className="min-w-0">
              <h2 className="text-base font-semibold">Detalle expandido</h2>
              <p className="text-base text-neutral-700">Resultado abierto desde el chat.</p>
            </div>
            <button
              onClick={() => chatActions.setDetail(null)}
              aria-label="Cerrar detalle expandido"
              className="min-h-[48px] min-w-[48px] shrink-0 rounded-lg border border-neutral-400 px-3 py-2 text-base text-neutral-800 hover:border-brand"
            >
              Cerrar
            </button>
          </div>
          <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-5">
            {store.detail.map((spec, i) => (
              <DynamicRenderer
                key={`detail-${i}`}
                spec={spec}
                onAsk={send}
                onGoalCreated={goalCreatedFromForm}
                onGoalsChanged={onGoalsChanged}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

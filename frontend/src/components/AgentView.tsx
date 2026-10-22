"use client";

import { useEffect, useRef, useState } from "react";
import type { ChatResponse, PurchaseOption, UIEvent, UISpec } from "@/types/contract";
import { post } from "@/lib/api";
import DynamicRenderer from "@/components/dynamic/DynamicRenderer";
import { activeConversation, chatActions, useChatStore, type ChatMsg } from "@/lib/chatStore";

const QUICK_PROMPTS = [
  "¿Cuánto dinero tengo?",
  "¿En qué gasté este mes?",
  "¿Cuándo me llega mi nómina?",
  "¿Tengo cobros repetidos?",
  "¿Cuánto puedo ahorrar?",
  "Explícame algo de forma sencilla",
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

  async function send(text: string, uiEvent?: UIEvent) {
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
        ui_event: uiEvent,
      }, controller.signal);
      chatActions.addMessage({ role: "assistant", resp });
      if (uiEvent?.type === "purchase_goal_confirmed" &&
          resp.ui.some((spec) => spec.type === "savings_progress")) {
        onGoalsChanged();
      }
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

  function selectPurchaseOption(
    optionId: PurchaseOption["option_id"],
    label: string,
    traceId: string,
  ) {
    send(`Elegí la opción: ${label}.`, {
      id: crypto.randomUUID(),
      type: "purchase_option_selected",
      payload: { option_id: optionId },
      trace_id: traceId,
    });
  }

  function requestPurchaseGoal(traceId: string) {
    send("Quiero preparar la meta de ahorro de este plan.", {
      id: crypto.randomUUID(),
      type: "purchase_goal_create_requested",
      payload: { option_id: "savings_12" },
      trace_id: traceId,
    });
  }

  function confirmPurchaseGoal(
    traceId: string,
    confirmationToken: string,
    idempotencyKey: string,
  ) {
    send("Confirmo crear la meta de ahorro de este plan.", {
      id: crypto.randomUUID(),
      type: "purchase_goal_confirmed",
      payload: {
        option_id: "savings_12",
        confirmation_token: confirmationToken,
        idempotency_key: idempotencyKey,
      },
      trace_id: traceId,
    });
  }

  function cancel() {
    abortRef.current?.abort();
  }

  function readAloud(text: string) {
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "es-MX";
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
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
        schema_version: "1.0", mode: "demo", ui: [], tools_used: ["create_savings_goal"],
      },
    });
    onGoalsChanged();
  }

  return (
    <div className={`relative grid h-full min-h-0 grid-cols-1 overflow-hidden ${store.detail ? "xl:grid-cols-[minmax(0,1fr)_420px]" : ""}`}>
      <div className="flex h-full min-h-0 flex-col">
      <div ref={scrollRef} className="min-h-0 flex-1 space-y-3 overflow-y-auto p-2">
        {messages.length === 0 && (
          <div className="rounded-2xl bg-white p-3 text-base shadow-sm">
            <p className="text-base font-medium">
              ¡Hola! Soy tu asistente de IA de demostración.
            </p>
            <p className="mt-2 text-neutral-700">
              Prototipo educativo inspirado en Banorte. No soy una persona ni el banco oficial;
              uso datos ficticios. Elige una pregunta:
            </p>
            <div className="mt-2 grid grid-cols-1 gap-1 sm:grid-cols-2">
              {QUICK_PROMPTS.map((p) => (
                <button
                  key={p}
                  onClick={() => send(p)}
                  className="min-h-[48px] rounded-xl border-2 border-neutral-300 bg-white px-4 py-2 text-left text-base text-neutral-800 hover:border-brand hover:text-brand"
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
          const navigateTo = typeof m.resp?.interaction_context?.navigate === "string"
            ? m.resp.interaction_context.navigate
            : null;
          const screenLabel = typeof m.resp?.interaction_context?.screen_label === "string"
            ? m.resp.interaction_context.screen_label
            : "la app";
          return (
            <div key={`${conversation.id}-${i}`} className="space-y-3">
              <div className="flex justify-start">
                <div className="max-w-[92%] rounded-2xl rounded-bl-sm bg-white px-4 py-2 text-base shadow-sm">
                  <p className="whitespace-pre-wrap">{m.resp?.message}</p>
                  {m.resp?.mode === "demo" && (
                    <p className="mt-2 text-[18px] text-neutral-600" role="status">
                      Respuesta con ayuda local; no requiere conexión con un proveedor de IA.
                    </p>
                  )}
                  {m.resp?.suggestions && m.resp.suggestions.length > 0 && (
                    <div className="mt-3">
                      <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
                        <p className="text-base font-medium text-neutral-800">
                          Puedes preguntar:
                        </p>
                        {typeof window !== "undefined" && "speechSynthesis" in window && (
                          <button
                            onClick={() => readAloud(m.resp?.message ?? "")}
                            className="min-h-[48px] rounded-xl border-2 border-neutral-300 px-4 py-2 text-base text-neutral-800 hover:border-brand"
                            aria-label="Leer respuesta en voz alta"
                          >
                            Leer en voz alta
                          </button>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {m.resp.suggestions.map((suggestion) => (
                          <button
                            key={suggestion}
                            onClick={() => send(suggestion)}
                            disabled={loading}
                            className="min-h-[48px] rounded-xl border-2 border-neutral-300 bg-white px-4 py-2 text-left text-base text-neutral-800 hover:border-brand hover:text-brand disabled:opacity-60"
                          >
                            {suggestion}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  {navigateTo && (
                    <button
                      onClick={() => onNavigate(navigateTo)}
                      className="mt-3 min-h-[48px] rounded-xl border-2 border-brand px-4 py-2.5 text-base font-medium text-brand hover:bg-brand-soft"
                    >
                      Ver en {screenLabel}
                    </button>
                  )}
                  {(!m.resp?.suggestions || m.resp.suggestions.length === 0) &&
                    typeof window !== "undefined" && "speechSynthesis" in window && (
                      <button
                        onClick={() => readAloud(m.resp?.message ?? "")}
                        className="mt-3 min-h-[48px] rounded-xl border-2 border-neutral-300 px-4 py-2.5 text-base text-neutral-800 hover:border-brand"
                        aria-label="Leer respuesta en voz alta"
                      >
                        Leer en voz alta
                      </button>
                    )}
                  {hasUi && (
                    <button
                      onClick={() =>
                        chatActions.setDetail(
                          isDetailOpen ? null : (m.resp!.ui as UISpec[]),
                          isDetailOpen ? null : msgKey,
                          isDetailOpen ? null : (m.resp?.trace_id ?? null)
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
                  traceId={m.resp?.trace_id}
                  loading={loading}
                  onPurchaseOptionSelect={selectPurchaseOption}
                  onPurchaseGoalRequest={requestPurchaseGoal}
                  onPurchaseGoalConfirm={confirmPurchaseGoal}
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
            placeholder="Escribe con tus palabras, por ejemplo: ¿en qué gasté?"
            className="min-h-[48px] min-w-0 flex-1 rounded-xl border border-neutral-300 px-4 py-3 text-base"
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
        <div className="absolute inset-y-0 right-0 z-20 flex h-full min-h-0 w-full max-w-[420px] flex-col overflow-hidden border-l border-neutral-200 bg-neutral-50 shadow-xl xl:static xl:w-auto xl:max-w-none xl:shadow-none">
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
                traceId={store.detailTraceId}
                loading={loading}
                onPurchaseOptionSelect={selectPurchaseOption}
                onPurchaseGoalRequest={requestPurchaseGoal}
                onPurchaseGoalConfirm={confirmPurchaseGoal}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

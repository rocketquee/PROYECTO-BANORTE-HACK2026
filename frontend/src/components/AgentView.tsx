"use client";

import { useEffect, useRef, useState } from "react";
import type { ChatResponse, UISpec } from "@/types/contract";
import { post } from "@/lib/api";
import DynamicRenderer from "@/components/dynamic/DynamicRenderer";

interface ChatMsg {
  role: "user" | "assistant" | "system";
  text?: string;
  resp?: ChatResponse;
  error?: string;
}

const QUICK_PROMPTS = [
  "¿En qué estoy gastando más dinero?",
  "Analiza mis gastos de este mes",
  "Ayúdame a ahorrar $5,000",
  "¿Cuánto podría pagar mensualmente por un crédito?",
  "Muéstrame mis movimientos y clasifícalos",
  "¿Cómo puedo organizar mi presupuesto?",
];

export default function AgentView({
  onGoalsChanged,
}: {
  onGoalsChanged: () => void;
}) {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [lastUi, setLastUi] = useState<UISpec[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const historyRef = useRef<{ role: "user" | "assistant"; content: string }[]>([]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  async function send(text: string) {
    const message = text.trim();
    if (!message || loading) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text: message }]);
    setLoading(true);
    try {
      const resp = await post<ChatResponse>("/api/agent/chat", {
        message,
        history: historyRef.current.slice(-6),
      });
      setMessages((prev) => [...prev, { role: "assistant", resp }]);
      if (resp.ui?.length) setLastUi(resp.ui);
      historyRef.current.push(
        { role: "user", content: message },
        { role: "assistant", content: resp.message }
      );
    } catch (err) {
      setMessages((prev) => [...prev, { role: "system", error: (err as Error).message }]);
    } finally {
      setLoading(false);
    }
  }

  async function confirmPending(actionId: string, msgIndex: number) {
    setLoading(true);
    try {
      const resp = await post<ChatResponse>("/api/agent/confirm", { action_id: actionId });
      setMessages((prev) =>
        prev.map((m, i) =>
          i === msgIndex && m.resp ? { ...m, resp: { ...m.resp, pending_action: null } } : m
        )
      );
      setMessages((prev) => [...prev, { role: "assistant", resp }]);
      if (resp.ui?.length) setLastUi(resp.ui);
      onGoalsChanged();
    } catch (err) {
      setMessages((prev) => [...prev, { role: "system", error: (err as Error).message }]);
    } finally {
      setLoading(false);
    }
  }

  function goalCreatedFromForm(name: string, target: number) {
    setMessages((prev) => [
      ...prev,
      { role: "assistant", resp: {
        message: `Meta "${name}" guardada con objetivo de $${target.toLocaleString("es-MX")}. Ya aparece en tu dashboard.`,
        mode: "demo", ui: [], tools_used: ["create_savings_goal"],
      } },
    ]);
    onGoalsChanged();
  }

  return (
    <div className="grid h-full grid-cols-1 gap-0 xl:grid-cols-[1fr_460px]">
      {/* Chat column */}
      <div className="flex h-full min-h-0 flex-col border-r border-neutral-200">
        <div className="border-b border-neutral-200 bg-white px-6 py-4">
          <h1 className="text-lg font-semibold">Asistente financiero</h1>
          <p className="text-xs text-neutral-500">
            El agente usa herramientas MCP reales y genera interfaces dinámicas.
          </p>
        </div>

        <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-6">
          {messages.length === 0 && (
            <div className="rounded-2xl bg-white p-6 text-sm shadow-sm">
              <p className="font-medium">¡Hola! Soy tu asistente financiero (prototipo con datos sintéticos).</p>
              <p className="mt-2 text-neutral-600">
                Pregúntame por tus gastos, pídeme organizar tu presupuesto, crear una meta de ahorro o
                simular un crédito. Generaré la interfaz que necesites en tiempo real.
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                {QUICK_PROMPTS.map((p) => (
                  <button
                    key={p}
                    onClick={() => send(p)}
                    className="rounded-full border border-neutral-300 px-3 py-1.5 text-xs text-neutral-700 hover:border-brand hover:text-brand"
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => {
            if (m.role === "user") {
              return (
                <div key={i} className="flex justify-end">
                  <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-brand px-4 py-3 text-sm text-white">
                    {m.text}
                  </div>
                </div>
              );
            }
            if (m.role === "system") {
              return (
                <div key={i} className="rounded-xl bg-amber-50 p-4 text-sm text-amber-800">
                  {m.error}
                </div>
              );
            }
            return (
              <div key={i} className="space-y-3">
                <div className="flex justify-start">
                  <div className="max-w-[92%] rounded-2xl rounded-bl-sm bg-white px-4 py-3 text-sm shadow-sm">
                    <p className="whitespace-pre-wrap">{m.resp?.message}</p>
                    <div className="mt-2 flex flex-wrap items-center gap-1.5">
                      {m.resp?.tools_used?.map((t) => (
                        <span key={t} className="rounded bg-neutral-100 px-2 py-0.5 text-[11px] text-neutral-600">
                          MCP · {t}
                        </span>
                      ))}
                      {m.resp?.mode === "demo" && (
                        <span className="rounded bg-brand-soft px-2 py-0.5 text-[11px] font-medium text-brand-dark">
                          Modo demostración
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                {m.resp?.ui?.map((spec, j) => (
                  <DynamicRenderer
                    key={j}
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
            <div className="flex items-center gap-2 text-sm text-neutral-500">
              <span className="h-2 w-2 animate-pulse rounded-full bg-brand" />
              El agente está consultando las herramientas MCP…
            </div>
          )}
        </div>

        <form
          onSubmit={(e) => { e.preventDefault(); send(input); }}
          className="border-t border-neutral-200 bg-white p-4"
        >
          <div className="flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Escribe tu solicitud financiera…"
              className="flex-1 rounded-xl border border-neutral-300 px-4 py-3 text-sm"
              aria-label="Mensaje para el asistente"
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="rounded-xl bg-brand px-5 py-3 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-50"
            >
              Enviar
            </button>
          </div>
        </form>
      </div>

      {/* Dynamic results panel */}
      <div className="hidden min-h-0 flex-col overflow-y-auto bg-neutral-50 xl:flex">
        <div className="sticky top-0 z-10 border-b border-neutral-200 bg-neutral-50 px-5 py-4">
          <h2 className="text-sm font-semibold">Panel de resultados dinámicos</h2>
          <p className="text-xs text-neutral-500">
            La interfaz se genera según tu intención (contrato JSON validado).
          </p>
        </div>
        <div className="space-y-4 p-5">
          {lastUi.length === 0 ? (
            <div className="rounded-2xl border-2 border-dashed border-neutral-300 p-8 text-center text-sm text-neutral-500">
              Aquí aparecerán los componentes que genere el agente: gráficos, tablas,
              simuladores, formularios y más.
            </div>
          ) : (
            lastUi.map((spec, i) => (
              <DynamicRenderer
                key={`${spec.type}-${i}-${loading ? "l" : "d"}`}
                spec={spec}
                onAsk={send}
                onGoalCreated={goalCreatedFromForm}
                onGoalsChanged={onGoalsChanged}
              />
            ))
          )}
        </div>
      </div>
    </div>
  );
}

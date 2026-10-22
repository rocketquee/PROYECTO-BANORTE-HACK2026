"use client";

import { useEffect, useState } from "react";
import type { DashboardData } from "@/types/contract";
import { apiFetch } from "@/lib/api";
import { fmtDate, money } from "@/lib/format";
import type { ViewId } from "@/lib/navigation";
import AnimatedProgressFill from "./AnimatedProgressFill";
import ProgressRing from "./ProgressRing";

const TITLES: Record<string, { title: string; blurb: string; ask: string }> = {
  cuentas: { title: "Mis cuentas", blurb: "Saldos de tus cuentas en este prototipo.",
             ask: "¿Cuál es el saldo de mis cuentas?" },
  movimientos: { title: "Movimientos", blurb: "Tus últimos movimientos registrados.",
                 ask: "Muéstrame mis movimientos del mes" },
  tarjetas: { title: "Tarjetas", blurb: "Tus tarjetas y sus fechas de corte y pago.",
              ask: "¿Cuándo tengo que pagar mi tarjeta?" },
  pagos: { title: "Pagos y transferencias", blurb: "Sección simulada del prototipo: aquí se mostrarían pagos y transferencias. No se mueve dinero real.",
           ask: "¿Qué pagos fijos tengo este mes?" },
  contactos: { title: "Contactos", blurb: "Sección simulada: contactos frecuentes para transferencias. No hay datos reales.",
               ask: "¿Cómo voy con la quincena?" },
  creditos: { title: "Créditos y simulador", blurb: "Simula pagos mensuales de un crédito. Los resultados son educativos: no son una oferta ni implican aprobación.",
              ask: "¿Cuánto pagaría mensualmente por un crédito de $250,000 a 24 meses?" },
  ahorro: { title: "Ahorro y metas", blurb: "El progreso de tus metas de ahorro.",
            ask: "¿Cómo voy con mis metas de ahorro?" },
  inversiones: { title: "Inversiones", blurb: "Sección simulada: aquí se mostrarían tus inversiones simples. Sin datos ni rendimientos reales.",
                 ask: "Si ahorro 2,000 al mes, ¿cuándo juntaré 24,000?" },
  seguros: { title: "Seguros", blurb: "Sección simulada: tus seguros contratados aparecerían aquí. Solo hay un seguro de vida ficticio en los datos.",
             ask: "¿Qué gastos fijos y seguros pago cada mes?" },
  presupuesto: { title: "Presupuesto", blurb: "Cómo va tu gasto contra los límites que definiste.",
                 ask: "¿Cómo voy con mi presupuesto este mes?" },
  notificaciones: { title: "Notificaciones", blurb: "Avisos del prototipo: cargos inusuales y recordatorios.",
                   ask: "¿Tengo cargos inusuales o duplicados?" },
  perfil: { title: "Perfil y preferencias", blurb: "Preferencias de la aplicación (tamaño de letra, idioma). Este prototipo no guarda datos personales reales.",
            ask: "¿Quién eres?" },
  ayuda: { title: "Ayuda y seguridad", blurb: "Qué puede y qué no puede hacer este asistente, y cómo cuidamos tu información.",
           ask: "¿Qué puedes hacer?" },
};

function Progress({ pct }: { pct: number }) {
  const clamped = Math.min(pct, 100);
  return (
    <div className="h-3 w-full rounded-full bg-neutral-200" role="progressbar"
         aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}>
      <AnimatedProgressFill
        value={clamped}
        className={pct > 100 ? "bg-brand" : "bg-[#1F6E43]"}
      />
    </div>
  );
}

export default function SectionView({ section, refreshKey }: {
  section: ViewId;
  refreshKey: number;
}) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const meta = TITLES[section] ?? TITLES.ayuda;

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError(null);
    apiFetch<DashboardData>("/api/dashboard")
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e: Error) => { if (!cancelled) setError(e.message); });
    return () => { cancelled = true; };
  }, [refreshKey]);

  return (
    <div className="w-full p-6 pt-2">
      {error && (
        <div className="mt-6 rounded-xl bg-amber-50 p-4 text-base text-amber-900">
          <p>{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-3 min-h-[48px] rounded-lg border border-amber-500 px-3 py-2"
          >
            Reintentar
          </button>
        </div>
      )}

      {!data && !error && <p className="mt-6 text-neutral-600">Cargando tus datos…</p>}

      {data && section === "cuentas" && (
        <ul className="mt-6 space-y-3">
          {data.accounts.map((a) => (
            <li key={a.id} className="flex items-center justify-between rounded-2xl bg-white p-5 shadow-sm">
              <div>
                <p className="font-semibold">{a.name}</p>
                <p className="text-base text-neutral-600">{a.type === "debit" ? "Débito" : a.type === "savings" ? "Ahorro" : a.type}</p>
              </div>
              <p className="text-lg font-semibold tabular-nums">{money(a.balance)}</p>
            </li>
          ))}
          <li className="flex items-center justify-between rounded-2xl bg-white p-5 shadow-sm">
            <p className="font-semibold">Saldo total</p>
            <p className="text-lg font-bold tabular-nums">{money(data.total_balance)}</p>
          </li>
        </ul>
      )}

      {data && section === "movimientos" && (
        <table className="mt-6 w-full text-left text-base">
          <caption className="sr-only">Últimos movimientos</caption>
          <thead>
            <tr className="border-b-2 border-neutral-300">
              <th scope="col" className="py-2">Fecha</th>
              <th scope="col" className="py-2">Concepto</th>
              <th scope="col" className="py-2">Categoría</th>
              <th scope="col" className="py-2 text-right">Importe</th>
            </tr>
          </thead>
          <tbody>
            {data.recent_transactions.map((t) => (
              <tr key={t.id} className="border-b border-neutral-200">
                <td className="py-2">{fmtDate(t.date)}</td>
                <td className="py-2">{t.description}</td>
                <td className="py-2">{t.category}</td>
                <td className={`py-2 text-right tabular-nums ${t.type === "income" ? "text-emerald-700" : "text-neutral-900"}`}>
                  {t.type === "income" ? "+" : "−"}{money(t.amount)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {data && section === "tarjetas" && (
        <ul className="mt-6 space-y-3">
          {data.cards.map((c) => (
            <li key={c.id} className="rounded-2xl bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <p className="font-semibold">{c.name} · •••• {c.last4}</p>
                <p className="font-semibold tabular-nums">{money(c.balance)}</p>
              </div>
              {c.credit_limit > 0 && (
                <p className="mt-1 text-base text-neutral-700">
                  Límite de crédito: {money(c.credit_limit)}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}

      {data && section === "presupuesto" && (
        <ul className="mt-6 space-y-4">
          {data.budget_overview.categories.map((c) => (
            <li key={c.category}>
              <div className="mb-1 flex justify-between text-base">
                <span className="font-medium">{c.category}</span>
                <span className="tabular-nums">
                  {money(c.spent)} de {money(c.limit)}
                  {c.pct != null && ` (${Math.round(c.pct)}%)`}
                </span>
              </div>
              <Progress pct={c.pct ?? 0} />
            </li>
          ))}
        </ul>
      )}

      {data && section === "ahorro" && (
        <ul className="mt-6 space-y-4">
          {data.goals.map((g) => (
            <li key={g.id} className="screen-stagger rounded-2xl bg-white p-5 shadow-sm">
              <div className="mb-2 flex items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-3">
                  <ProgressRing value={g.progress_pct} />
                  <p className="font-semibold">{g.name}</p>
                </div>
                <p className="tabular-nums">{money(g.saved_amount)} de {money(g.target_amount)}</p>
              </div>
              <Progress pct={g.progress_pct} />
              {g.deadline && (
                <p className="mt-1 text-base text-neutral-700">Fecha límite: {fmtDate(g.deadline)}</p>
              )}
            </li>
          ))}
        </ul>
      )}

      {data && section === "creditos" && (
        <div className="mt-6 rounded-2xl bg-white p-5 shadow-sm">
          <p className="text-base">
            Usa el asistente para simular: «¿Cuánto pagaría mensualmente por un crédito de
            $250,000 a 24 meses?». Verás la mensualidad estimada, los intereses totales y
            podrás ajustar monto, plazo y tasa.
          </p>
          <p className="mt-2 text-base text-neutral-600">
            Simulación educativa con una tasa de ejemplo. No es una oferta ni implica aprobación.
          </p>
        </div>
      )}

      {data && ["pagos", "contactos", "inversiones", "seguros", "notificaciones", "perfil", "ayuda"].includes(section) && (
        <div className="mt-6 rounded-2xl bg-white p-5 shadow-sm">
          <p className="text-base text-neutral-800">{meta.blurb}</p>
          {section === "ayuda" && (
            <ul className="mt-3 list-disc space-y-1 pl-5 text-base text-neutral-800">
              <li>Puedo revisar tus gastos, ayudarte a ahorrar, simular créditos y organizar tu presupuesto.</li>
              <li>No muevo dinero real ni hago transferencias: este es un prototipo educativo.</li>
              <li>No puedo hablar de temas ajenos a tus finanzas (clima, salud, política, etc.).</li>
              <li>Todos los datos son ficticios y se generan solo para la demostración.</li>
            </ul>
          )}
          {section === "notificaciones" && (
            <p className="mt-2 text-base">
              Pide al asistente: «¿tengo cargos duplicados?» y «¿tengo cargos inusuales?».
            </p>
          )}
        </div>
      )}
    </div>
  );
}

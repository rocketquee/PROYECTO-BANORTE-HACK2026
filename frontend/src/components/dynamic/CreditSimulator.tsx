"use client";

import { useEffect, useMemo, useState } from "react";
import type { CreditSimulatorSpec } from "@/types/contract";
import { post } from "@/lib/api";
import { money } from "@/lib/format";

export default function CreditSimulator({
  spec, onAsk,
}: { spec: CreditSimulatorSpec; onAsk: (message: string) => void }) {
  const [amount, setAmount] = useState(spec.params.amount.toString());
  const [months, setMonths] = useState(spec.params.months);
  const [rate, setRate] = useState(spec.params.annual_rate.toString());
  const [method, setMethod] = useState<"frances" | "aleman">(spec.params.method);
  const [result, setResult] = useState(spec.result);
  const [schedule, setSchedule] = useState(spec.schedule);
  const [error, setError] = useState<string | null>(null);
  const [showSchedule, setShowSchedule] = useState(false);

  const params = useMemo(
    () => ({ amount: Number(amount) || 0, months, annual_rate: Number(rate) || 0, method }),
    [amount, months, rate, method]
  );

  useEffect(() => {
    if (params.amount < 1000) return;
    const timer = setTimeout(async () => {
      try {
        const res = await post<typeof spec.result & { schedule: typeof schedule }>(
          "/api/credit/simulate", params
        );
        setResult({ monthly_payment: res.monthly_payment, total_interest: res.total_interest,
                    total_paid: res.total_paid });
        setSchedule(res.schedule);
        setError(null);
      } catch (err) {
        setError((err as Error).message);
      }
    }, 350);
    return () => clearTimeout(timer);
  }, [params]);

  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
      <h3 className="mb-4 text-base font-semibold">{spec.title}</h3>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="space-y-4">
          <label className="block text-base">
            <span className="mb-1 block font-medium text-neutral-700">
              Monto solicitado: {money(params.amount)}
            </span>
            <input
              type="range" min={10000} max={500000} step={5000}
              value={Math.min(params.amount, 500000)}
              onChange={(e) => setAmount(e.target.value)}
              className="w-full accent-brand"
            />
            <input
              value={amount}
              onChange={(e) => setAmount(e.target.value.replace(/[^\d.]/g, ""))}
              inputMode="decimal"
              className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2 text-base"
              aria-label="Monto solicitado"
            />
          </label>

          <label className="block text-base">
            <span className="mb-1 block font-medium text-neutral-700">Plazo: {months} meses</span>
            <input
              type="range" min={3} max={120} step={3}
              value={months}
              onChange={(e) => setMonths(Number(e.target.value))}
              className="w-full accent-brand"
            />
          </label>

          <div className="grid grid-cols-2 gap-3">
            <label className="block text-base">
              <span className="mb-1 block font-medium text-neutral-700">Tasa anual (%)</span>
              <input
                value={rate}
                onChange={(e) => setRate(e.target.value.replace(/[^\d.]/g, ""))}
                inputMode="decimal"
                className="w-full rounded-lg border border-neutral-300 px-3 py-2 text-base"
              />
            </label>
            <label className="block text-base">
              <span className="mb-1 block font-medium text-neutral-700">Método</span>
              <select
                value={method}
                onChange={(e) => setMethod(e.target.value as "frances" | "aleman")}
                className="w-full rounded-lg border border-neutral-300 bg-white px-2 py-2 text-base"
              >
                <option value="frances">Francés (pago fijo)</option>
                <option value="aleman">Alemán (pago decreciente)</option>
              </select>
            </label>
          </div>
        </div>

        <div className="flex flex-col justify-center rounded-xl bg-neutral-50 p-5">
          <p className="text-base font-medium uppercase tracking-wide text-neutral-700">
            Mensualidad estimada
          </p>
          <p className="text-4xl font-bold text-brand">{money(result.monthly_payment, 2)}</p>
          <div className="mt-4 space-y-1 text-base text-neutral-600">
            <p>Intereses totales: <strong>{money(result.total_interest, 2)}</strong></p>
            <p>Total a pagar: <strong>{money(result.total_paid, 2)}</strong></p>
            <p>Método: <strong>{method === "frances" ? "Francés (pago fijo)" : "Alemán (pago decreciente)"}</strong></p>
          </div>
          {error && <p className="mt-3 text-base text-brand">{error}</p>}
          <button
            onClick={() =>
              onAsk(`Analiza este plan de crédito: monto ${money(params.amount)}, plazo de ${months} meses, tasa de ${params.annual_rate}% anual, método ${method}. ¿Qué opinas y qué riesgos debo considerar?`)
            }
            className="mt-4 rounded-lg border border-brand px-4 py-2 text-base font-medium text-brand hover:bg-brand-soft"
          >
            Analizar este plan con el agente
          </button>
        </div>
      </div>

      <button
        onClick={() => setShowSchedule(!showSchedule)}
        className="mt-4 text-base font-medium text-neutral-600 underline-offset-2 hover:underline"
      >
        {showSchedule ? "Ocultar tabla de amortización" : "Ver tabla de amortización"}
      </button>
      {showSchedule && (
        <div className="mt-2 max-h-64 overflow-y-auto rounded-lg border border-neutral-200">
          <table className="w-full text-base">
            <thead className="sticky top-0 bg-neutral-50 text-base uppercase text-neutral-700">
              <tr>
                <th className="p-2 text-left">#</th>
                <th className="p-2 text-right">Pago</th>
                <th className="p-2 text-right">Interés</th>
                <th className="p-2 text-right">Capital</th>
                <th className="p-2 text-right">Saldo</th>
              </tr>
            </thead>
            <tbody>
              {schedule.map((r) => (
                <tr key={r.n} className="border-t border-neutral-100">
                  <td className="p-2">{r.n}</td>
                  <td className="p-2 text-right">{money(r.payment, 2)}</td>
                  <td className="p-2 text-right text-neutral-700">{money(r.interest, 2)}</td>
                  <td className="p-2 text-right">{money(r.principal, 2)}</td>
                  <td className="p-2 text-right">{money(r.balance, 2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <details className="mt-4 rounded-xl border border-neutral-200 p-3">
        <summary className="cursor-pointer text-base font-medium text-neutral-800">
          ¿Qué significa?
        </summary>
        <dl className="mt-2 space-y-2 text-base text-neutral-700">
          <div>
            <dt className="font-semibold">Tasa anual</dt>
            <dd>El costo del préstamo expresado como porcentaje del monto por año.</dd>
          </div>
          <div>
            <dt className="font-semibold">Plazo</dt>
            <dd>El número de meses que tomará pagar el crédito completo.</dd>
          </div>
          <div>
            <dt className="font-semibold">Mensualidad</dt>
            <dd>Lo que pagarías cada mes. Incluye una parte del préstamo y una parte de intereses.</dd>
          </div>
          <div>
            <dt className="font-semibold">Intereses totales</dt>
            <dd>El costo extra que pagarías por tomar el crédito, además de lo que prestaste.</dd>
          </div>
          <div>
            <dt className="font-semibold">Pago mínimo</dt>
            <dd>En una tarjeta de crédito, la cantidad más pequeña que puedes pagar para
                evitar cargos moratorios, aunque el resto sigue generando intereses.</dd>
          </div>
          <div>
            <dt className="font-semibold">CAT</dt>
            <dd>Costo Anual Total: incluye la tasa más las comisiones; es la forma más
                completa de comparar créditos.</dd>
          </div>
        </dl>
      </details>

      <p className="mt-4 text-base leading-relaxed text-neutral-600">{spec.disclaimer}</p>
      <p className="mt-1 text-base text-neutral-600">
        Simulación educativa: no es una oferta ni implica aprobación de crédito.
      </p>
    </div>
  );
}

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { transferFormAction, sliderAction, validateUIPlanShape } from "../src/lib/uiPlan.mjs";

const page = readFileSync(new URL("../src/app/page.tsx", import.meta.url), "utf8");
const agent = readFileSync(new URL("../src/components/AgentView.tsx", import.meta.url), "utf8");
const cards = readFileSync(new URL("../src/components/CardsView.tsx", import.meta.url), "utf8");
const navigation = readFileSync(new URL("../src/lib/navigation.ts", import.meta.url), "utf8");
const spendingChart = readFileSync(new URL("../src/components/dynamic/SpendingChart.tsx", import.meta.url), "utf8");
const uiRenderer = readFileSync(new URL("../src/components/UIRenderer.tsx", import.meta.url), "utf8");
const setup = readFileSync(new URL("../../scripts/setup.cmd", import.meta.url), "utf8");
const readme = readFileSync(new URL("../../README.md", import.meta.url), "utf8");

test("home restores the original card layout and keeps an explicit assistant action", () => {
  const homeBranch = page.split('view === "inicio" ? (')[1].split(': view === "asistente"')[0];
  assert.match(navigation, /description: "Tu tarjeta de demostración y controles, en un solo lugar\."/);
  assert.match(page, /label: "Hablar con el asistente", run: \(\) => changeView\("asistente"\)/);
  assert.match(homeBranch, /<CardsView[\s\S]*?variant="home"/);
  assert.doesNotMatch(homeBranch, /<AgentView/);
  assert.match(cards, /lg:grid-cols-\[minmax\(0,1\.08fr\)_minmax\(0,\.92fr\)\]/);
  assert.match(cards, /border-\[#30303A\] bg-black p-5 sm:p-6/);
  assert.match(cards, /mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4/);
  assert.match(cards, /Controles de la tarjeta/);
  assert.match(cards, /item\.description/);
  assert.match(cards, /Saldo total de demostración/);
  assert.match(cards, /Ver resumen completo/);
  assert.match(page, /view === "asistente"[\s\S]*?<AgentView/);
  assert.doesNotMatch(page, /fixed right-0|fixed bottom-4|mobileAssistantOpen|assistantOpen/);
  assert.match(agent, /overflow-y-auto/);
  assert.match(agent, /shrink-0 border-t border-neutral-200 bg-white/);
});

test("assistant is second in the sidebar order, including keyboard and mobile menu order", () => {
  const ids = [...navigation.matchAll(/\{ id: "([^"]+)", label:/g)].map((match) => match[1]);
  assert.deepEqual(ids.slice(0, 7), [
    "inicio", "asistente", "dashboard", "movimientos",
    "presupuesto", "ahorro", "tarjetas",
  ]);
  assert.equal((page.match(/<AgentView/g) ?? []).length, 1);
});

test("card flip controls use the clear reversible wording", () => {
  assert.match(cards, /flipped \? "Ver frente" : "Ver reverso"/);
  assert.match(cards, /Ver frente de la tarjeta/);
  assert.match(cards, /Ver reverso de la tarjeta/);
  assert.match(cards, /Toca la tarjeta para ver el reverso/);
  assert.doesNotMatch(cards, /Voltear|voltear/);
});

test("Windows setup script installs all dependencies and documents clean installation", () => {
  assert.match(setup, /Python 3\.11/);
  assert.match(setup, /Node\.js 18\.18/);
  assert.match(setup, /backend\\requirements\.txt/);
  assert.match(setup, /mcp-server\\requirements\.txt/);
  assert.match(setup, /npm\.cmd install/);
  assert.match(setup, /copy \/Y "\.env\.example" "\.env"/);
  assert.match(setup, /Listo, ejecuta scripts\\start-all\.cmd/);
  assert.match(setup, /exit \/b 1/);
  assert.match(readme, /## Instalación desde cero/);
  assert.match(readme, /scripts\\setup\.cmd/);
});

test("chat stays full-screen and exposes the assistant entry point without auto-navigation", () => {
  assert.match(page, /view === "asistente"[\s\S]*?<AgentView/);
  assert.match(agent, /QUICK_PROMPTS/);
  assert.match(agent, /messages\.length === 0/);
  assert.doesNotMatch(agent, /onNavigate\(nav\)/);
  assert.match(agent, /onClick=\{\(\) => onNavigate\(navigateTo\)\}/);
  assert.match(agent, /Abrir en \{screenLabel\}/);
});

test("spending donut hides external labels below 500 px and keeps the list legend", () => {
  assert.match(spendingChart, /entry\.contentRect\.width < 500/);
  assert.match(spendingChart, /label=\{compact\s*\?\s*false/);
  assert.match(spendingChart, /labelLine=\{!compact\}/);
  assert.match(spendingChart, /compact \? "" : "sm:grid-cols-2"/);
  assert.match(spendingChart, /flex-1 break-words/);
  assert.doesNotMatch(spendingChart, /truncate/);
});

test("expanded detail overlays the assistant area and can be closed", () => {
  assert.match(agent, /absolute inset-0 z-20 ml-auto/);
  assert.match(agent, /aria-label="Cerrar detalle expandido"/);
});

test("assistant exposes provider health and inline degradation notice", () => {
  assert.match(agent, /apiFetch<HealthResponse>\("\/api\/health"\)/);
  assert.match(agent, /Comprobando IA…/);
  assert.match(agent, /IA activa: \$\{provider\.model\}/);
  assert.match(agent, /Ayuda local \(IA no disponible\)/);
  assert.match(agent, /La IA dejó de responder; esta respuesta usa la ayuda local\./);
  assert.match(agent, /\{m\.notice && \(/);
});

test("A2UI renderer draws the nine validated components and closes the transfer loop", () => {
  assert.match(uiRenderer, /case "StatCard"/);
  assert.match(uiRenderer, /case "BarChart"/);
  assert.match(uiRenderer, /case "Table"/);
  assert.match(uiRenderer, /case "ProgressRing"/);
  assert.match(uiRenderer, /case "TransferForm"/);
  assert.match(uiRenderer, /case "PlanDePago"/);
  assert.match(uiRenderer, /case "LineChart"/);
  assert.match(uiRenderer, /case "Slider"/);
  assert.match(uiRenderer, /case "BudgetAllocator"/);
  assert.match(uiRenderer, /Confirmación enviada/);
  assert.match(uiRenderer, /onAction\(action\.message/);
  assert.match(agent, /UIRenderer/);
  assert.match(agent, /m\.resp\?\.ui_plan\?\.components\?\.length/);
  assert.match(agent, /type: action\.type/);
});

test("a ui_plan with catalog components validates and TransferForm emits a confirmation event", () => {
  const plan = {
    title: "Tu resumen",
    components: [
      { type: "StatCard", title: "Saldo total", value: "$85,921" },
      {
        type: "BarChart",
        title: "Gasto por categoría",
        series: [{ label: "Comida", value: 4200 }],
      },
      {
        type: "Table",
        title: "Movimientos",
        columns: ["Fecha", "Descripción", "Monto"],
        rows: [["2026-10-30", "Nómina", "$10,959"]],
      },
      { type: "ProgressRing", title: "Avance", label: "Fondo", value: 61.7 },
      {
        type: "TransferForm",
        title: "Confirmar abono",
        from_account: "Cuenta de origen",
        to_account: "Fondo de emergencia",
        amount: 500,
        concept: "Abono a Fondo de emergencia",
        confirmation_text: "Revisa y confirma.",
        goal_id: 1,
        confirmation_token: "12345678-1234-1234-1234-123456789012",
        idempotency_key: "abcdefab-1234-1234-1234-123456789012",
      },
    ],
  };

  assert.deepEqual(validateUIPlanShape(plan), { ok: true, errors: [] });
  const action = transferFormAction(plan.components[4]);
  assert.equal(action.event.type, "savings_contribution_confirmed");
  assert.equal(action.event.payload.goal_id, 1);
  assert.equal(action.event.payload.amount, 500);
  assert.match(action.message, /Confirmo el abono/);
});

test("the four new components validate with domain-computed props", () => {
  const plan = {
    title: "Crédito y presupuesto",
    components: [
      {
        type: "PlanDePago",
        title: "Plan de pago",
        amount: 100000,
        annual_rate: 15.9,
        terms: [
          { months: 6, monthly_payment: 17451.6, cat_pct: 15.9 },
          { months: 24, monthly_payment: 4896.4, cat_pct: 15.9 },
        ],
      },
      {
        type: "LineChart",
        title: "Tendencia de gasto",
        points: [
          { label: "may", value: 8120 },
          { label: "jun", value: 8450 },
          { label: "jul", value: 7980 },
        ],
        period: "may — jul",
      },
      {
        type: "Slider",
        title: "Ajusta el monto",
        label: "Monto del crédito",
        param: "amount",
        min_value: 10000,
        max_value: 500000,
        step: 10000,
        value: 100000,
        recalculate_message: "Simula un crédito de {value} a 24 meses.",
      },
      {
        type: "BudgetAllocator",
        title: "Distribución 50/30/20",
        income: 10000,
        buckets: [
          { bucket: "necesidades", pct: 50, amount: 5000 },
          { bucket: "deseos", pct: 30, amount: 3000 },
          { bucket: "ahorro", pct: 20, amount: 2000 },
        ],
      },
    ],
  };

  assert.deepEqual(validateUIPlanShape(plan), { ok: true, errors: [] });
});

test("sliderAction emits the exact message the backend recalculates", () => {
  const amount = sliderAction(
    {
      type: "Slider",
      param: "amount",
      unit: "MXN",
      recalculate_message: "Recalcula el crédito con un monto de {value} a 24 meses al 15.9% anual.",
    },
    150000,
  );
  assert.equal(
    amount,
    "Recalcula el crédito con un monto de $150,000.00 a 24 meses al 15.9% anual.",
  );

  const months = sliderAction(
    {
      type: "Slider",
      param: "months",
      unit: "meses",
      recalculate_message: "Recalcula el crédito de $100,000 a un plazo de {value} meses al 15.9% anual.",
    },
    36,
  );
  assert.equal(
    months,
    "Recalcula el crédito de $100,000 a un plazo de 36 meses al 15.9% anual.",
  );
});

test("new components reject props outside their catalog contract", () => {
  const invalid = [
    {
      type: "PlanDePago",
      title: "Plan",
      amount: 100000,
      annual_rate: 15.9,
      terms: [
        { months: 6, monthly_payment: 100, cat_pct: 15.9 },
        { months: 6, monthly_payment: 100, cat_pct: 15.9 },
      ],
    },
    {
      type: "LineChart",
      title: "Puntos",
      points: [{ label: "solo uno", value: 1 }],
      period: "un mes",
    },
    {
      type: "Slider",
      title: "Control",
      label: "Monto",
      param: "amount",
      min_value: 100,
      max_value: 50,
      step: 10,
      value: 100,
      recalculate_message: "Calcula {value}.",
    },
    {
      type: "BudgetAllocator",
      title: "Distribución",
      income: 10000,
      buckets: [
        { bucket: "necesidades", pct: 60, amount: 6000 },
        { bucket: "deseos", pct: 30, amount: 3000 },
        { bucket: "ahorro", pct: 10, amount: 1000 },
      ],
    },
  ];

  invalid.forEach((component) => {
    assert.equal(validateUIPlanShape({ title: "Plan", components: [component] }).ok, false);
  });
});

test("optional ui_plan props may be missing without invalidating the plan", () => {
  const plan = {
    title: "Mínimo",
    components: [
      { type: "StatCard", title: "Saldo", value: "$1" },
      { type: "ProgressRing", title: "Meta", label: "Viaje", value: 0 },
      { type: "Table", title: "Sin filas", columns: ["A"], rows: [] },
    ],
  };
  assert.equal(validateUIPlanShape(plan).ok, true);
});

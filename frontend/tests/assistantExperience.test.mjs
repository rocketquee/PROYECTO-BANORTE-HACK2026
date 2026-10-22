import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const page = readFileSync(new URL("../src/app/page.tsx", import.meta.url), "utf8");
const agent = readFileSync(new URL("../src/components/AgentView.tsx", import.meta.url), "utf8");

test("assistant has a persistent desktop dock and full-screen mobile launcher", () => {
  assert.match(page, /w-\[min\(420px,38vw\)\].*lg:flex/s);
  assert.match(page, /aria-label="Abrir asistente"/);
  assert.match(page, /fixed inset-0 z-50 flex h-\[100dvh\].*lg:hidden/s);
  assert.match(page, /event\.altKey.*event\.key\.toLowerCase\(\) === "a"/s);
  assert.match(agent, /overflow-y-auto/);
  assert.match(agent, /shrink-0 border-t border-neutral-200 bg-white/);
});

test("assistant is initially open on desktop and starts with concrete suggestions", () => {
  assert.match(page, /useState\(true\)/);
  assert.match(page, /syncAssistantToViewport\(\)/);
  assert.match(page, /setMobileAssistantOpen\(!media\.matches\)/);
  assert.match(agent, /QUICK_PROMPTS/);
  assert.match(agent, /messages\.length === 0/);
});

test("chat responses never navigate automatically; only the explicit screen button does", () => {
  assert.doesNotMatch(agent, /onNavigate\(nav\)/);
  assert.match(agent, /onClick=\{\(\) => onNavigate\(navigateTo\)\}/);
  assert.match(agent, /Abrir en \{screenLabel\}/);
});

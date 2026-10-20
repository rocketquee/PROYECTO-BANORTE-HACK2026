/**
 * UI-1 / UI-2 / UI-3 / UI-4 verification (reported interface findings).
 *
 * - UI-1: the document never scrolls; the app fills the viewport exactly
 *          (100dvh). Checked at 768 / 1366 / 1920 px and at zoom 150% / 200%
 *          (browser zoom shrinks the CSS layout viewport, so it is emulated
 *          with viewport = width / zoom plus deviceScaleFactor = zoom).
 * - UI-2: "Ver detalle expandido" opens the right panel, it can be closed, and
 *          when closed it takes no space and shows no helper text.
 * - UI-3: the disabled "Enviar" button keeps >= 3:1 contrast; no visible text
 *          is under 16px nor under 4.5:1 contrast against its real backdrop.
 * - UI-4: budget limits show "$" plus a thousands separator and stay editable.
 *
 * Usage: node ui_verify.mjs   (requires the dev server on :3000)
 */
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const BASE = process.env.APP_URL || "http://localhost:3000";
const OUT =
  process.env.UI_OUT ||
  join(dirname(fileURLToPath(import.meta.url)), "ui-evidence");
mkdirSync(OUT, { recursive: true });

const CASES = [
  { name: "w768", width: 768, height: 900, zoom: 1 },
  { name: "w1366", width: 1366, height: 900, zoom: 1 },
  { name: "w1920", width: 1920, height: 1080, zoom: 1 },
  { name: "w1366-zoom150", width: 1366, height: 900, zoom: 1.5 },
  { name: "w1920-zoom200", width: 1920, height: 1080, zoom: 2 },
];

const results = [];
const record = (id, ok, detail) => {
  results.push({ id, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"} ${id}: ${detail}`);
};

const browser = await chromium.launch();

for (const c of CASES) {
  const page = await browser.newPage({
    viewport: {
      width: Math.round(c.width / c.zoom),
      height: Math.round(c.height / c.zoom),
    },
    deviceScaleFactor: c.zoom,
  });
  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.waitForTimeout(700);

  const label = `${c.name} (${c.width}px @ zoom ${c.zoom * 100}%)`;

  // ---- UI-1: no page scroll, app fills the window exactly
  const s = await page.evaluate(() => {
    const el = document.scrollingElement;
    const sidebar = document.querySelector("aside");
    const nav = sidebar?.querySelector("nav");
    const main = document.querySelector("main");
    return {
      docScrollH: el.scrollHeight,
      docClientH: el.clientHeight,
      winH: window.innerHeight,
      bodyOverflow: getComputedStyle(document.body).overflowY,
      sidebarOverflow: nav ? getComputedStyle(nav).overflowY : "none",
      sidebarBottom: sidebar ? Math.round(sidebar.getBoundingClientRect().bottom) : 0,
      mainBottom: main ? Math.round(main.getBoundingClientRect().bottom) : 0,
    };
  });
  record(
    `UI-1 ${label}`,
    s.docScrollH <= s.docClientH + 1 &&
      s.bodyOverflow === "hidden" &&
      s.sidebarOverflow === "auto" &&
      s.sidebarBottom <= s.winH + 1 &&
      s.mainBottom <= s.winH + 1,
    `documento scrollH ${s.docScrollH} <= clientH ${s.docClientH} (sin scroll de página); ` +
      `body overflow-y=${s.bodyOverflow}; barra lateral overflow-y=${s.sidebarOverflow}; ` +
      `borde inferior barra lateral ${s.sidebarBottom} y main ${s.mainBottom} <= ventana ${s.winH}`
  );
  await page.screenshot({ path: join(OUT, `${c.name}-01-inicio.png`) });

  // ---- UI-2: expanded detail panel
  await page.getByRole("button", { name: /Asistente IA/i }).first().click().catch(() => {});
  await page.waitForTimeout(700);
  await page.getByLabel("Mensaje para el asistente").fill("Muéstrame mis movimientos y clasifícalos");
  await page.getByRole("button", { name: "Enviar" }).click();
  await page.waitForTimeout(3000);

  const panelBefore = await page.evaluate(() =>
    document.body.innerText.includes("Detalle expandido")
  );
  const detailBtn = page.getByRole("button", { name: /Ver detalle expandido/ }).first();
  const hasBtn = (await detailBtn.count()) > 0;
  if (hasBtn) {
    await detailBtn.click();
    await page.waitForTimeout(800);
  }
  const panelOpen = await page.evaluate(() => {
    const h = Array.from(document.querySelectorAll("h2")).find(
      (n) => n.textContent?.trim() === "Detalle expandido"
    );
    if (!h) return { open: false, width: 0 };
    const panel = h.parentElement?.parentElement;
    return { open: true, width: panel ? Math.round(panel.getBoundingClientRect().width) : 0 };
  });
  record(
    `UI-2 ${label}`,
    hasBtn && panelOpen.open && panelOpen.width > 100 && !panelBefore,
    `panel cerrado ocupaba espacio/texto: ${panelBefore}; botón encontrado: ${hasBtn}; ` +
      `panel abierto tras el clic: ${panelOpen.open} (${panelOpen.width}px de ancho)`
  );
  await page.screenshot({ path: join(OUT, `${c.name}-02-detalle-abierto.png`) });

  const closeBtn = page.getByRole("button", { name: "Cerrar detalle expandido" });
  const hasClose = (await closeBtn.count()) > 0;
  if (hasClose) {
    await closeBtn.click();
    await page.waitForTimeout(600);
  }
  const after = await page.evaluate(() => ({
    heading: document.body.innerText.includes("Detalle expandido"),
    help: document.body.innerText.includes("presiona «Ver detalle expandido»"),
  }));
  record(
    `UI-2-cierre ${label}`,
    hasClose && !after.heading && !after.help,
    `botón «Cerrar» presente: ${hasClose}; tras cerrar, encabezado visible: ${after.heading}; ` +
      `texto de ayuda visible: ${after.help}`
  );

  // ---- UI-3: contrast and text size (real backdrops)
  const a11y = await page.evaluate(() => {
    const lum = ([r, g, b]) => {
      const f = (v) => {
        v /= 255;
        return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
      };
      return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
    };
    const ratio = (c1, c2) => {
      const [a, b] = [lum(c1), lum(c2)].sort((x, y) => y - x);
      return (a + 0.05) / (b + 0.05);
    };
    const rgb = (css) => css.match(/\d+/g)?.slice(0, 3).map(Number) ?? [255, 255, 255];
    const backdrop = (node) => {
      let n = node;
      while (n) {
        const bg = getComputedStyle(n).backgroundColor;
        const m = bg.match(/rgba?\(([^)]+)\)/);
        if (m) {
          const parts = m[1].split(",").map((x) => parseFloat(x));
          const alpha = parts.length > 3 ? parts[3] : 1;
          if (alpha > 0.5) return parts.slice(0, 3).map(Math.round);
        }
        n = n.parentElement;
      }
      return [255, 255, 255];
    };

    const enSend = Array.from(document.querySelectorAll("button")).find(
      (b) => b.textContent?.trim() === "Enviar"
    );
    const cs = enSend ? getComputedStyle(enSend) : null;

    const leaves = Array.from(document.querySelectorAll("span, p, label, td, th, li, button, h1, h2, h3"))
      .filter((n) => {
        if (n.children.length !== 0) return false;
        const t = n.textContent?.trim();
        if (!t) return false;
        const r = n.getBoundingClientRect();
        return r.width > 0 && r.height > 0;
      })
      .map((n) => {
        const st = getComputedStyle(n);
        const bg = backdrop(n);
        return {
          text: n.textContent.trim().slice(0, 32),
          size: Math.round(parseFloat(st.fontSize) * 10) / 10,
          contrast: Math.round(ratio(rgb(st.color), bg) * 100) / 100,
        };
      });

    return {
      enSend: enSend
        ? {
            disabled: enSend.disabled,
            size: Math.round(parseFloat(cs.fontSize) * 10) / 10,
            contrast: Math.round(ratio(rgb(cs.color), rgb(cs.backgroundColor)) * 100) / 100,
          }
        : null,
      tooSmall: leaves.filter((l) => l.size < 16),
      lowContrast: leaves.filter((l) => l.contrast < 4.5),
      total: leaves.length,
    };
  });
  record(
    `UI-3 ${label}`,
    Boolean(a11y.enSend) &&
      a11y.enSend.contrast >= 3 &&
      a11y.tooSmall.length === 0 &&
      a11y.lowContrast.length === 0,
    `«Enviar» deshabilitado: contraste ${a11y.enSend?.contrast}:1 (>=3) a ${a11y.enSend?.size}px; ` +
      `${a11y.total} textos medidos; <16px: ${a11y.tooSmall.length}` +
      `${a11y.tooSmall.length ? " -> " + a11y.tooSmall.slice(0, 4).map((l) => `"${l.text}" ${l.size}px`).join("; ") : ""}; ` +
      `<4.5:1: ${a11y.lowContrast.length}` +
      `${a11y.lowContrast.length ? " -> " + a11y.lowContrast.slice(0, 4).map((l) => `"${l.text}" ${l.contrast}:1`).join("; ") : ""}`
  );

  // ---- UI-4: budget limits ($1,500) editable in the assistant panel
  await page.getByLabel("Mensaje para el asistente").fill("¿Cómo voy con mi presupuesto?");
  await page.getByRole("button", { name: "Enviar" }).click();
  await page.waitForTimeout(3000);

  const editable = await page.evaluate(() => {
    const input = document.querySelector('input[aria-label^="Límite mensual de"]');
    if (!input) return null;
    const wrap = input.parentElement;
    return {
      raw: input.value,
      aria: input.getAttribute("aria-label"),
      dollars: Boolean(wrap?.textContent?.includes("$")),
      editable: !input.disabled && !input.readOnly,
      sample: wrap?.textContent?.trim(),
    };
  });
  if (editable) {
    await page.locator('input[aria-label^="Límite mensual de"]').first().fill("2500");
    await page.locator('input[aria-label^="Límite mensual de"]').first().blur();
    await page.waitForTimeout(400);
  }
  const afterEdit = await page.evaluate(() => {
    const input = document.querySelector('input[aria-label^="Límite mensual de"]');
    return input ? input.value : null;
  });
  const initialOk = Boolean(
    editable &&
      /^[\d,]+$/.test(editable.raw) &&
      editable.dollars &&
      editable.editable &&
      // A limit below 1,000 needs no separator; the edit step proves the
      // separator is applied ("2500" -> "2,500").
      (editable.raw.includes(",") || Number(editable.raw.replace(/,/g, "")) < 1000)
  );
  record(
    `UI-4 ${label}`,
    initialOk && afterEdit === "2,500",
    editable
      ? `límite "${editable.raw}" con "$": ${editable.dollars}, editable: ${editable.editable}; ` +
        `tras editar 2500 quedó "${afterEdit}"; campo: ${editable.sample?.replace(/\s+/g, " ")}`
      : "no se encontró el campo editable de límite de presupuesto"
  );
  await page.screenshot({ path: join(OUT, `${c.name}-03-presupuesto.png`) });

  await page.close();
}

await browser.close();

const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} verificaciones OK`);
console.log(`Evidencia en ${OUT}`);
process.exit(failed.length ? 1 : 0);

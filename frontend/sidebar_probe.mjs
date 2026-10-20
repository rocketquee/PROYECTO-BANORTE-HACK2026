import { chromium } from "playwright";

const browser = await chromium.launch();
for (const [w, h] of [[768, 900], [1366, 900], [1920, 1080], [1366 / 1.5, 900 / 1.5]]) {
  const page = await browser.newPage({ viewport: { width: Math.round(w), height: Math.round(h) } });
  await page.goto("http://localhost:3000", { waitUntil: "networkidle" });
  await page.waitForTimeout(600);
  const info = await page.evaluate(() => {
    const aside = document.querySelector("aside");
    const footer = aside?.lastElementChild;
    const nav = aside?.querySelector("nav");
    const r = (n) => {
      const b = n.getBoundingClientRect();
      return { top: Math.round(b.top), bottom: Math.round(b.bottom), h: Math.round(b.height) };
    };
    return {
      winH: window.innerHeight,
      aside: r(aside),
      nav: r(nav),
      navScroll: { sh: nav.scrollHeight, ch: nav.clientHeight },
      footer: r(footer),
      footerText: footer.textContent.trim().slice(0, 60),
      footerOverflows: footer.getBoundingClientRect().bottom > aside.getBoundingClientRect().bottom + 1,
    };
  });
  console.log(`${Math.round(w)}x${Math.round(h)}:`, JSON.stringify(info));
  await page.close();
}
await browser.close();

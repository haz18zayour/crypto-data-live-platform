import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { pathToFileURL, fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../../../..");
const web = resolve(root, "web");
const evidence = resolve(
  root,
  "prds/PRD-010-integrity-dashboard/50-evidence/US-1004",
);
const require = createRequire(resolve(web, "package.json"));
const { chromium } = require("playwright");
const { createServer } = await import(pathToFileURL(require.resolve("vite")).href);

const server = await createServer({
  root: web,
  configLoader: "runner",
  logLevel: "error",
  clearScreen: false,
  server: {
    host: "127.0.0.1",
    port: 5174,
    strictPort: true,
  },
});

await server.listen();

const browser = await chromium.launch();
try {
  const context = await browser.newContext({
    colorScheme: "light",
    viewport: { width: 1280, height: 900 },
  });
  const page = await context.newPage();
  await page.goto("http://localhost:5174/mixed-board.html");

  const row = page.locator("tbody tr", { hasText: "mvrv" }).first();
  const cell = row.locator("td.cell--ok", { hasText: "unchanged since 10 Sep 2026" }).first();
  await cell.waitFor({ timeout: 30_000 });
  await cell.locator("summary").click();
  await cell.locator("text=Frozen value unchanged since").waitFor({ timeout: 5_000 });

  const className = await cell.getAttribute("class");
  const badgeText = await cell.locator(".frozen-badge").innerText();
  const statusText = await cell.locator(".cell-word").innerText();
  const valueText = await cell.locator("[data-testid='cell-value']").innerText();
  if (!className?.split(/\s+/).includes("cell--ok")) {
    throw new Error(`frozen badge changed the cell status class: ${className}`);
  }
  if (statusText !== "OK") {
    throw new Error(`frozen badge changed the visible status: ${statusText}`);
  }
  if (badgeText.replace(/\s+/g, " ") !== "unchanged since 10 Sep 2026") {
    throw new Error(`unexpected frozen badge text: ${badgeText}`);
  }
  if (!valueText.trim()) {
    throw new Error("frozen badge displaced the cell value");
  }

  await page.evaluate(() => document.fonts.ready.then(() => undefined));
  mkdirSync(evidence, { recursive: true });
  await page.screenshot({
    path: resolve(evidence, "frozen-badge-live-board-fixture.png"),
    fullPage: true,
  });
  await cell.screenshot({
    path: resolve(evidence, "frozen-badge-cell-open.png"),
  });
  console.log(
    "captured frozen badge fixture at http://localhost:5174/mixed-board.html with OK status unchanged",
  );
} finally {
  await browser.close();
  await server.close();
}

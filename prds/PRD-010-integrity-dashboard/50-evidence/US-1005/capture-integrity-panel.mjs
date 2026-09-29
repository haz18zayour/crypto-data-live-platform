// Owner-run verification for US-1005-C7 (no capture script was left by the implementer).
// Loads the real live board against production and screenshots the integrity panel.
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { pathToFileURL, fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../../../..");
const web = resolve(root, "web");
const evidence = resolve(root, "prds/PRD-010-integrity-dashboard/50-evidence/US-1005");
const require = createRequire(resolve(web, "package.json"));
const { chromium } = require("playwright");
const { createServer } = await import(pathToFileURL(require.resolve("vite")).href);

const server = await createServer({
  root: web,
  configLoader: "runner",
  logLevel: "error",
  clearScreen: false,
  server: { host: "127.0.0.1", port: 5176, strictPort: true },
});
await server.listen();

const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  page.on("pageerror", (err) => console.log("PAGE ERROR:", err.message));
  await page.goto("http://localhost:5176/");
  await page.waitForSelector(".integrity-panel", { timeout: 30_000 });

  const rows = await page.locator(".integrity-rollup-row").allTextContents();
  console.log(`integrity panel rows found: ${rows.length}`);
  rows.forEach((r) => console.log(" -", r.replace(/\s+/g, " ")));

  mkdirSync(evidence, { recursive: true });
  await page.screenshot({
    path: resolve(evidence, "integrity-panel-live.png"),
    fullPage: true,
  });
  console.log("captured integrity panel against the real live board");
} finally {
  await browser.close();
  await server.close();
}

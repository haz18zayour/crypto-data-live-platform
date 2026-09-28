// US-908-C7: the sparkline on the live board, at the board's own cell size, in a real browser.
// Starts the web dev server (which reads VITE_SUPABASE_* from the repo-root .env.local), opens
// the live board in headless Chromium, opens the BTC daily-close cell, waits for its sparkline,
// checks the labels are legible, and photographs the cell in both themes next to this file.
//
//   node prds/PRD-009-history-charts/50-evidence/US-908/capture-sparkline.mjs
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "../../../..");
const web = resolve(root, "web");
const require = createRequire(resolve(web, "package.json"));
const { chromium } = require("playwright");
const { createServer } = await import(
  pathToFileURL(resolve(web, "node_modules/vite/dist/node/index.js")).href
);

const server = await createServer({ root: web, configLoader: "runner", logLevel: "error" });
await server.listen();
const browser = await chromium.launch();
const failures = [];
try {
  for (const colorScheme of ["light", "dark"]) {
    const context = await browser.newContext({ colorScheme, viewport: { width: 1280, height: 900 } });
    const page = await context.newPage();
    await page.goto(server.resolvedUrls.local[0]);
    await page.locator("table.board-matrix td").nth(47).waitFor({ timeout: 30_000 });

    const row = page.locator("tbody tr", { has: page.locator("th", { hasText: /^daily close$/ }) });
    const cell = row.locator("td").first();
    await cell.locator("summary").click();
    await cell.locator(".sparkline svg, .sparkline-insufficient, .cell-history-note").first().waitFor();
    await page.waitForFunction(() => !document.querySelector(".cell-history-note"), undefined, {
      timeout: 30_000,
    });

    const measured = await cell.evaluate((td) => {
      const svg = td.querySelector(".sparkline svg");
      const px = (selector) => parseFloat(getComputedStyle(td.querySelector(selector)).fontSize);
      return svg
        ? {
            drawn: true,
            cellWidth: td.getBoundingClientRect().width,
            plotWidth: svg.getBoundingClientRect().width,
            vertices: svg.querySelector("polyline").getAttribute("points").split(" ").length,
            maxPx: px(".sparkline-max"),
            minPx: px(".sparkline-min"),
            windowPx: px(".sparkline-window"),
            text: td.querySelector(".sparkline").innerText,
          }
        : { drawn: false, text: td.querySelector(".cell-history").innerText };
    });
    console.log(`${colorScheme}: ${JSON.stringify(measured)}`);

    if (!measured.drawn) failures.push(`${colorScheme}: no sparkline drawn — ${measured.text}`);
    else {
      for (const key of ["maxPx", "minPx", "windowPx"]) {
        if (measured[key] < 11) failures.push(`${colorScheme}: ${key} is ${measured[key]}px`);
      }
      if (measured.plotWidth > measured.cellWidth) failures.push(`${colorScheme}: plot overflows its cell`);
    }
    await cell.screenshot({ path: resolve(here, `sparkline-live-${colorScheme}.png`) });
    await page.screenshot({ path: resolve(here, `board-live-${colorScheme}.png`), fullPage: true });
    await context.close();
  }
} finally {
  await browser.close();
  await server.close();
}

if (failures.length > 0) {
  console.error(`\nfailed:\n- ${failures.join("\n- ")}`);
  process.exit(1);
}

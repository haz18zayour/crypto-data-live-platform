import { createServer } from "node:http";
import { mkdirSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, extname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../../../..");
const web = resolve(root, "web");
const evidence = resolve(root, "prds/PRD-010-integrity-dashboard/50-evidence/US-1004");
const require = createRequire(resolve(web, "package.json"));
const { chromium } = require("playwright");

const html = String.raw`<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>US-1004 frozen badge fixture</title>
    <link rel="stylesheet" href="/src/styles.css" />
  </head>
  <body>
    <main>
      <p class="eyebrow">Frozen badge fixture - live browser</p>
      <h1>Data completeness</h1>
      <div class="board-matrix-scroll" role="region" aria-labelledby="board-matrix-caption" tabindex="0">
        <table class="board-matrix">
          <caption id="board-matrix-caption">Completeness by indicator and asset</caption>
          <thead>
            <tr>
              <th scope="col">Indicator</th>
              <th scope="col">BTC</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th scope="row">daily close</th>
              <td class="cell cell--ok" data-asset="BTC">
                <details class="cell-disclosure">
                  <summary>
                    <span class="cell-primary">
                      <span class="cell-glyph" aria-hidden="true">&#9679;</span>
                      <span class="cell-word">OK</span>
                      <span class="cell-detail" data-testid="cell-value">11,111.1</span>
                    </span>
                    <span class="cell-provenance">
                      <span class="cell-vendor">OKX</span>
                      <span aria-hidden="true"> - </span>
                      <span>Source</span>
                      <time dateTime="2026-09-29T00:00:00Z">29 Sep 2026, 00:00:00 UTC</time>
                    </span>
                    <span class="frozen-badge">
                      unchanged since
                      <time dateTime="2026-09-24T00:00:00Z">24 Sep 2026</time>
                    </span>
                    <span class="cell-detail-cue">Details</span>
                  </summary>
                  <dl class="cell-source-detail" aria-label="Source detail">
                    <div>
                      <dt>Endpoint</dt>
                      <dd>https://fixture.example.test/okx/candles</dd>
                    </div>
                    <div>
                      <dt>Source field</dt>
                      <dd>close</dd>
                    </div>
                    <div>
                      <dt>Fetch time</dt>
                      <dd>29 Sep 2026, 00:01:00 UTC</dd>
                    </div>
                    <div>
                      <dt>Integrity</dt>
                      <dd>
                        Frozen value unchanged since
                        <time dateTime="2026-09-24T00:00:00Z">24 Sep 2026, 00:00:00 UTC</time>
                      </dd>
                    </div>
                  </dl>
                </details>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </main>
  </body>
</html>`;

const contentTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
};

const server = createServer((request, response) => {
  if (request.url === "/" || request.url === "/index.html") {
    response.writeHead(200, { "Content-Type": contentTypes[".html"] });
    response.end(html);
    return;
  }

  if (request.url === "/src/styles.css") {
    const path = resolve(web, "src/styles.css");
    response.writeHead(200, { "Content-Type": contentTypes[extname(path)] });
    response.end(readFileSync(path));
    return;
  }

  response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
  response.end("Not found");
});

await new Promise((resolveListen) => {
  server.listen(5174, "127.0.0.1", resolveListen);
});

const browser = await chromium.launch();
try {
  const context = await browser.newContext({
    colorScheme: "light",
    viewport: { width: 1280, height: 900 },
  });
  const page = await context.newPage();
  await page.goto("http://localhost:5174/");

  const cell = page.locator("td.cell--ok", { hasText: "unchanged since 24 Sep 2026" }).first();
  await cell.waitFor({ timeout: 30_000 });
  await cell.locator("summary").click();
  await cell.locator("text=Frozen value unchanged since").waitFor({ timeout: 5_000 });

  const className = await cell.getAttribute("class");
  const badgeText = await cell.locator(".frozen-badge").innerText();
  const statusText = await cell.locator(".cell-word").innerText();
  if (!className?.split(/\s+/).includes("cell--ok")) {
    throw new Error(`frozen badge changed the cell status class: ${className}`);
  }
  if (statusText !== "OK") {
    throw new Error(`frozen badge changed the visible status: ${statusText}`);
  }
  if (badgeText.replace(/\s+/g, " ") !== "unchanged since 24 Sep 2026") {
    throw new Error(`unexpected frozen badge text: ${badgeText}`);
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
  console.log("captured frozen badge fixture at http://localhost:5174/ with OK status unchanged");
} finally {
  await browser.close();
  await new Promise((resolveClose) => server.close(resolveClose));
}

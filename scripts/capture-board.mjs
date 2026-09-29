// US-511: the board in a real browser. jsdom resolves ARIA roles from the element and never
// applies CSS, so it cannot see a stylesheet destroy the table or a colour fail contrast.
// Starts the web dev server itself, drives headless Chromium, and shuts both down.
//
//   node scripts/capture-board.mjs                    photograph the live and mixed boards
//   node scripts/capture-board.mjs --check-semantics  Chromium's accessibility tree is a real table
//   node scripts/capture-board.mjs --check-contrast   axe-core, both themes, both boards
//   node scripts/capture-board.mjs --capture-sparkline  US-908: a real cell's drawn history
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const web = resolve(root, "web");
// The dependencies live in web/node_modules, which a script at the root does not resolve from.
const require = createRequire(resolve(web, "package.json"));
const { chromium } = require("playwright");
const AxeBuilder = require("@axe-core/playwright").default;
const { createServer } = await import(
  pathToFileURL(resolve(web, "node_modules/vite/dist/node/index.js")).href
);

const evidence = resolve(root, "prds/PRD-005-dashboard/50-evidence/US-512");
const ASSETS = ["BTC", "ETH", "SOL", "BNB"];
const FACES = ["ok", "stale", "not-definable", "paywalled", "fetch-failed"];
const BOARDS = { live: "/", mixed: "/mixed-board.html" };
const mode = process.argv[2] ?? "--capture";

if (!["--capture", "--check-semantics", "--check-contrast", "--capture-sparkline"].includes(mode)) {
  console.error(`unknown mode ${mode}`);
  process.exit(2);
}

async function openBoard(browser, baseUrl, board, colorScheme) {
  const context = await browser.newContext({
    colorScheme,
    viewport: { width: 1280, height: 900 },
  });
  const page = await context.newPage();
  await page.goto(new URL(BOARDS[board], baseUrl).href);
  // Wait on the 48th cell, never on a timer: a screenshot of a loading state passes a file check
  // and proves nothing.
  try {
    await page.locator("table.board-matrix td").nth(47).waitFor({ timeout: 30_000 });
    await page.waitForFunction(
      () => !/Loading/.test(document.querySelector("main")?.textContent ?? ""),
      undefined,
      { timeout: 30_000 },
    );
  } catch {
    const text = await page.locator("body").innerText();
    throw new Error(`${board} board never rendered 48 cells. The page read:\n${text.slice(0, 500)}`);
  }
  await page.evaluate(() => document.fonts.ready.then(() => undefined));
  return page;
}

async function capture(browser, baseUrl) {
  mkdirSync(evidence, { recursive: true });
  for (const [board, colorScheme] of [
    ["live", "light"],
    ["live", "dark"],
    ["mixed", "light"],
  ]) {
    const page = await openBoard(browser, baseUrl, board, colorScheme);
    if (board === "mixed") {
      const present = await page.$$eval("td.cell", (cells) =>
        cells.map((cell) => [...cell.classList].find((name) => name.startsWith("cell--"))),
      );
      const missing = FACES.filter((face) => !present.includes(`cell--${face}`));
      if (missing.length > 0) throw new Error(`mixed board is missing faces: ${missing.join(", ")}`);
    }
    const path = resolve(evidence, `board-${board}-${colorScheme}.png`);
    await page.screenshot({ path, fullPage: true });
    console.log(`captured ${path}`);
    await page.context().close();
  }
  return [];
}

// US-908: open the live board's cells one by one until a real one draws its history, then
// photograph that cell at the board's own size. A cell that shows "not enough history yet" is
// skipped, never photographed as if it were the chart.
async function captureSparkline(browser, baseUrl) {
  const sparklineEvidence = resolve(root, "prds/PRD-009-history-charts/50-evidence/US-908");
  mkdirSync(sparklineEvidence, { recursive: true });
  const failures = [];
  for (const colorScheme of ["light", "dark"]) {
    const page = await openBoard(browser, baseUrl, "live", colorScheme);
    const cells = page.locator("td.cell--ok");
    const count = await cells.count();
    let found = null;
    for (let index = 0; index < count && !found; index += 1) {
      const cell = cells.nth(index);
      await cell.locator("summary").click();
      const outcome = cell.locator(".sparkline polyline, .sparkline-insufficient, .cell-history-note:not(:has-text('Loading'))");
      await outcome.first().waitFor({ timeout: 15_000 });
      if ((await cell.locator(".sparkline polyline").count()) > 0) found = cell;
      else await cell.locator("summary").click();
    }
    if (!found) {
      failures.push(`${colorScheme}: none of ${count} OK cells on the live board drew a sparkline`);
      await page.context().close();
      continue;
    }

    // Legible at the board's own cell size: every label is inside the cell, not clipped, and
    // set no smaller than 11px.
    const labels = await found.evaluate((cell) => {
      const box = cell.getBoundingClientRect();
      return [...cell.querySelectorAll(".sparkline-max, .sparkline-min, .sparkline-window")].map(
        (label) => {
          const rect = label.getBoundingClientRect();
          return {
            name: label.className,
            text: label.textContent,
            fontSize: parseFloat(getComputedStyle(label).fontSize),
            inside:
              rect.width > 0 &&
              rect.left >= box.left - 0.5 &&
              rect.right <= box.right + 0.5 &&
              label.scrollWidth <= Math.ceil(rect.width),
          };
        },
      );
    });
    if (labels.length !== 3) failures.push(`${colorScheme}: expected max, min and window labels, found ${labels.length}`);
    for (const label of labels) {
      if (label.fontSize < 11) failures.push(`${colorScheme}: ${label.name} is ${label.fontSize}px`);
      if (!label.inside) failures.push(`${colorScheme}: ${label.name} "${label.text}" overflows its cell`);
    }

    const heading = await found.evaluate(
      (cell) => `${cell.closest("tr")?.querySelector("th")?.textContent} / ${cell.getAttribute("data-asset") ?? cell.cellIndex}`,
    );
    const path = resolve(sparklineEvidence, `sparkline-live-${colorScheme}.png`);
    await found.scrollIntoViewIfNeeded();
    await page.screenshot({ path, fullPage: true });
    await found.screenshot({ path: resolve(sparklineEvidence, `sparkline-cell-${colorScheme}.png`) });
    console.log(`captured ${path} (cell ${heading}): ${labels.map((label) => label.text).join(" | ")}`);
    await page.context().close();
  }
  return failures;
}

// Read the accessibility tree Chromium builds, not the DOM: this is what a screen reader gets.
async function checkSemantics(browser, baseUrl) {
  const failures = [];
  for (const board of Object.keys(BOARDS)) {
    const page = await openBoard(browser, baseUrl, board, "light");
    const cdp = await page.context().newCDPSession(page);
    await cdp.send("Accessibility.enable");
    const { nodes } = await cdp.send("Accessibility.getFullAXTree");
    const byId = new Map(nodes.map((node) => [node.nodeId, node]));
    const role = (node) => (node.ignored ? "" : String(node.role?.value ?? "").toLowerCase());
    const below = (node, wanted) =>
      (node.childIds ?? [])
        .map((id) => byId.get(id))
        .filter(Boolean)
        .flatMap((child) => (role(child) === wanted ? [child] : below(child, wanted)));

    const tables = nodes.filter((node) => role(node) === "table");
    if (tables.length !== 1) {
      failures.push(`${board}: expected one accessible table, found ${tables.length}`);
      continue;
    }
    const [table] = tables;
    const rows = below(table, "row");
    const columnHeaders = rows.flatMap((row) => below(row, "columnheader"));
    const bodyRows = rows.filter((row) => below(row, "rowheader").length > 0);
    const rowHeaders = bodyRows.flatMap((row) => below(row, "rowheader"));
    const cells = bodyRows.flatMap((row) => below(row, "cell"));
    const names = columnHeaders.map((node) => node.name?.value);
    // Chromium's accname computation applies CSS text-transform to the computed name, so a
    // header rendered with text-transform: uppercase reports as "INDICATOR" not "Indicator".
    // Letter case carries no meaning to a screen reader; compare case-insensitively.
    const namesLower = names.map((name) => name?.toLowerCase());
    const expectedLower = ["Indicator", ...ASSETS].map((name) => name.toLowerCase());
    if (JSON.stringify(namesLower) !== JSON.stringify(expectedLower)) {
      failures.push(`${board}: column headers were ${JSON.stringify(names)}`);
    }
    if (rowHeaders.length !== 12) failures.push(`${board}: ${rowHeaders.length} row headers, expected 12`);
    if (cells.length !== 48) failures.push(`${board}: ${cells.length} cells, expected 48`);
    for (const row of bodyRows) {
      const count = below(row, "cell").length;
      if (count !== ASSETS.length) {
        failures.push(`${board}: row "${below(row, "rowheader")[0]?.name?.value}" has ${count} cells`);
      }
    }

    // Chromium repairs some display overrides in its tree, so the rule itself is checked too.
    const displays = await page.$$eval(
      "table.board-matrix, table.board-matrix tr, table.board-matrix th, table.board-matrix td",
      (elements) => elements.map((element) => [element.tagName, getComputedStyle(element).display]),
    );
    const expected = { TABLE: "table", TR: "table-row", TH: "table-cell", TD: "table-cell" };
    for (const [tag, display] of displays) {
      if (expected[tag] !== display) failures.push(`${board}: a ${tag} renders as display: ${display}`);
    }

    console.log(
      `${board}: accessible table with ${rowHeaders.length} row headers, ` +
        `${names.length - 1} asset column headers and ${cells.length} cells`,
    );
    await page.context().close();
  }
  return failures;
}

// link-in-text-block is axe-core's automated WCAG 1.4.1 (use of colour) rule. The status faces
// are covered for 1.4.1 by the greyscale test in web/src/board.browser.test.ts.
async function checkContrast(browser, baseUrl) {
  const failures = [];
  for (const board of Object.keys(BOARDS)) {
    for (const colorScheme of ["light", "dark"]) {
      const page = await openBoard(browser, baseUrl, board, colorScheme);
      const { violations, incomplete, passes } = await new AxeBuilder({ page })
        .withRules(["color-contrast", "link-in-text-block"])
        // Decorative glyphs are aria-hidden — the accessible weight is on the adjacent visible
        // word (the design system's glyph-and-word rule). Axe still visually evaluates
        // aria-hidden nodes for sighted low-vision users, but these render icon/symbol content
        // it cannot rasterize to measure, so it reports "incomplete" rather than a real result.
        .exclude('[aria-hidden="true"]')
        .analyze();
      // An undecidable check is not a pass: axe could not work out the colours it was shown.
      for (const [kind, results] of [
        ["violation", violations],
        ["could not be decided", incomplete],
      ]) {
        for (const result of results) {
          for (const node of result.nodes) {
            failures.push(
              `${board}/${colorScheme} ${result.id} ${kind}: ${node.target.join(" ")} — ${node.failureSummary ?? node.any?.[0]?.message ?? ""}`,
            );
          }
        }
      }
      const checked = passes.reduce((total, result) => total + result.nodes.length, 0);
      console.log(`${board}/${colorScheme}: ${checked} elements pass colour-contrast and use-of-colour`);
      await page.context().close();
    }
  }
  return failures;
}

const server = await createServer({
  root: web,
  configLoader: "runner",
  logLevel: "error",
  clearScreen: false,
});
await server.listen();
const baseUrl = server.resolvedUrls.local[0];
const browser = await chromium.launch();
let failures;
try {
  if (mode === "--check-semantics") failures = await checkSemantics(browser, baseUrl);
  else if (mode === "--check-contrast") failures = await checkContrast(browser, baseUrl);
  else if (mode === "--capture-sparkline") failures = await captureSparkline(browser, baseUrl);
  else failures = await capture(browser, baseUrl);
} finally {
  await browser.close();
  await server.close();
}

if (failures.length > 0) {
  console.error(`\n${mode} failed:\n- ${failures.join("\n- ")}`);
  process.exit(1);
}

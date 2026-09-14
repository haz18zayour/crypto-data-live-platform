// @vitest-environment node
// US-511: what jsdom cannot see. jsdom never applies the stylesheet, so pixels and layout are
// checked here in headless Chromium, against the mixed board served by the dev server.
/// <reference types="node" />
import { fileURLToPath } from "node:url";
import { chromium, type Browser, type Page } from "playwright";
import { createServer, type ViteDevServer } from "vite";
import { afterAll, beforeAll, describe, expect, test } from "vitest";

const webRoot = fileURLToPath(new URL("..", import.meta.url));
const FACES = ["ok", "stale", "not-definable", "paywalled", "fetch-failed"];

let server: ViteDevServer;
let browser: Browser;

beforeAll(async () => {
  server = await createServer({
    root: webRoot,
    configLoader: "runner",
    logLevel: "error",
    clearScreen: false,
  });
  await server.listen();
  browser = await chromium.launch();
}, 120_000);

afterAll(async () => {
  await browser?.close();
  await server?.close();
});

async function openMixedBoard(width: number): Promise<Page> {
  const page = await browser.newPage({ viewport: { width, height: 900 } });
  await page.goto(new URL("/mixed-board.html", server.resolvedUrls!.local[0]).href);
  await page.locator("table.board-matrix td").nth(47).waitFor();
  await page.evaluate(() => document.fonts.ready.then(() => undefined));
  return page;
}

// The same text in the same font, drawn alone at the same spot in the same box. Two parts that
// look alike give byte-identical screenshots, including two glyphs that both fell back to tofu.
async function drawAlone(page: Page, text: string, font: string) {
  await page.evaluate(
    ({ text, font }) => {
      const probe =
        document.getElementById("probe") ??
        document.body.appendChild(Object.assign(document.createElement("div"), { id: "probe" }));
      probe.style.cssText = `position: fixed; top: 0; left: 0; z-index: 9; width: 12rem; height: 2rem; padding: 4px; white-space: nowrap; font: ${font}`;
      probe.textContent = text;
    },
    { text, font },
  );
  return page.locator("#probe").screenshot();
}

describe("the board in a real browser", () => {
  test("every state face is distinguishable with colour removed", async () => {
    const page = await openMixedBoard(1280);
    // Colour removed twice over: every hue and tint flattened to one ink on one paper, then the
    // page rendered greyscale. Whatever still separates the faces is not colour.
    await page.addStyleTag({
      content:
        "html { filter: grayscale(1); } * { color: #000 !important; background: #fff !important; }",
    });

    const renders = [];
    for (const face of FACES) {
      const cell = page.locator(`td.cell--${face}`).first();
      const parts: Record<string, Buffer> = {};
      for (const part of ["glyph", "word"]) {
        const { text, font } = await cell
          .locator(`.cell-${part}`)
          .evaluate((element) => ({
            text: element.textContent ?? "",
            font: getComputedStyle(element).font,
          }));
        const blank = await drawAlone(page, "", font);
        parts[part] = await drawAlone(page, text, font);
        expect(parts[part].equals(blank), `the ${face} ${part} draws nothing`).toBe(false);
      }
      renders.push({ face, ...parts });
    }

    for (const [index, a] of renders.entries()) {
      for (const b of renders.slice(index + 1)) {
        expect(a.glyph.equals(b.glyph), `${a.face} and ${b.face} glyphs look the same`).toBe(false);
        expect(a.word.equals(b.word), `${a.face} and ${b.face} words look the same`).toBe(false);
      }
    }
    await page.close();
  }, 60_000);

  test("the board is readable at 400px wide with no horizontal scrolling of the page body", async () => {
    const page = await openMixedBoard(400);
    const layout = await page.evaluate(() => {
      const scroller = document.querySelector(".board-matrix-scroll")!;
      return {
        viewport: window.innerWidth,
        document: document.documentElement.scrollWidth,
        body: document.body.scrollWidth,
        headlineRight: document.querySelector(".coverage-headline")!.getBoundingClientRect().right,
        scrollerRight: scroller.getBoundingClientRect().right,
        scrollerOverflow: getComputedStyle(scroller).overflowX,
        scrollerClient: scroller.clientWidth,
        scrollerContent: scroller.scrollWidth,
        cellFontPx: parseFloat(getComputedStyle(document.querySelector("td.cell")!).fontSize),
      };
    });

    expect(layout.document).toBeLessThanOrEqual(layout.viewport);
    expect(layout.body).toBeLessThanOrEqual(layout.viewport);
    expect(layout.headlineRight).toBeLessThanOrEqual(layout.viewport);
    expect(layout.scrollerRight).toBeLessThanOrEqual(layout.viewport);
    // The matrix is wider than a phone, and it scrolls inside its own box instead.
    expect(layout.scrollerOverflow).toBe("auto");
    expect(layout.scrollerContent).toBeGreaterThan(layout.scrollerClient);
    expect(layout.cellFontPx).toBeGreaterThanOrEqual(12);

    // Scrolled to the far right, the row header is still in view, so every cell keeps its row.
    const scroller = page.locator(".board-matrix-scroll");
    await scroller.evaluate((element) => {
      element.scrollLeft = element.scrollWidth;
    });
    const scrollerBox = await scroller.boundingBox();
    const rowHeaderBox = await page.locator("tbody th").first().boundingBox();
    expect(Math.abs(rowHeaderBox!.x - scrollerBox!.x)).toBeLessThanOrEqual(1);
    await page.close();
  }, 60_000);
});

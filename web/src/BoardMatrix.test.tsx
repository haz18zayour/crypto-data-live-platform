import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import { App } from "./App";
import { BOARD_ASSETS, buildBoard, type BoardModel } from "./board";
import { BoardMatrix } from "./BoardMatrix";
import { mixedBoard } from "./fixtures/mixedBoard";
import { definitions } from "./registry";

// The fixture's source timestamp is 2026-09-13T00:00Z, so the stale cell is one day old.
const NOW = new Date("2026-09-14T00:01:00Z");
const emptyResponseBoard = buildBoard(definitions, [], BOARD_ASSETS);

function renderMatrix(board: BoardModel) {
  render(<BoardMatrix board={board} now={NOW} />);
  return screen.getAllByRole("cell");
}

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

function part(cell: HTMLElement, name: "glyph" | "word" | "detail") {
  return cell.querySelector(`.cell-${name}`)?.textContent?.trim() ?? "";
}

function faceClass(cell: HTMLElement) {
  return [...cell.classList].find((name) => name.startsWith("cell--"));
}

function cellFor(board: BoardModel, cells: HTMLElement[], indicatorKey: string, asset: string) {
  const index = board.cells.findIndex(
    (cell) => cell.indicatorKey === indicatorKey && cell.asset === asset,
  );
  expect(index).toBeGreaterThanOrEqual(0);
  return cells[index];
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("completeness matrix", () => {
  test("the matrix renders as a table element with a row header per family and a column header per asset", () => {
    render(<BoardMatrix board={mixedBoard} now={NOW} />);

    const table = screen.getByRole("table");
    expect(table.tagName).toBe("TABLE");
    expect(
      within(table)
        .getAllByRole("columnheader")
        .map((header) => header.textContent),
    ).toEqual(["Indicator", ...BOARD_ASSETS]);
    expect(
      within(table)
        .getAllByRole("rowheader")
        .map((header) => header.textContent),
    ).toEqual(mixedBoard.families.map((family) => family.replaceAll("_", " ")));
    expect(mixedBoard.families).toHaveLength(12);

    const bodyRows = within(table).getAllByRole("row").slice(1);
    expect(bodyRows).toHaveLength(12);
    for (const row of bodyRows) {
      expect(within(row).getAllByRole("rowheader")).toHaveLength(1);
      expect(within(row).getAllByRole("cell")).toHaveLength(BOARD_ASSETS.length);
    }
  });

  test("48 data cells render and every one has non-empty text content", () => {
    for (const board of [mixedBoard, emptyResponseBoard]) {
      const cells = renderMatrix(board);

      expect(cells).toHaveLength(48);
      for (const cell of cells) {
        expect(cell.textContent?.trim()).not.toBe("");
      }
      cleanup();
    }
  });

  test("every cell carries a state word and a glyph in addition to its colour class", () => {
    for (const board of [mixedBoard, emptyResponseBoard]) {
      const cells = renderMatrix(board);

      expect(cells).toHaveLength(48);
      for (const cell of cells) {
        expect(faceClass(cell)).toBeDefined();
        expect(part(cell, "glyph")).not.toBe("");
        expect(part(cell, "word")).not.toBe("");
        // With no stylesheet at all, the glyph and word are still in the text itself.
        expect(cell.textContent).toContain(part(cell, "glyph"));
        expect(cell.textContent).toContain(part(cell, "word"));
      }
      cleanup();
    }
  });

  test("no cell renders 0 or an empty string for an absent value", () => {
    for (const board of [mixedBoard, emptyResponseBoard]) {
      const cells = renderMatrix(board);
      const absent = board.cells
        .map((cell, index) => ({ state: cell.state, element: cells[index] }))
        .filter(({ state }) => state.status !== "OK" && state.status !== "STALE");

      expect(absent.length).toBeGreaterThan(0);
      for (const { element } of absent) {
        expect(part(element, "detail")).not.toBe("");
        expect(element.textContent).not.toMatch(/(^|[^\d.])0(\.0+)?([^\d.]|$)/);
      }
      cleanup();
    }
  });

  test("a NOT_DEFINABLE cell and a FETCH_FAILED cell render with different words glyphs and classes", () => {
    const cells = renderMatrix(mixedBoard);
    const notDefinable = cellFor(mixedBoard, cells, "sol_daily_close", "SOL");
    const fetchFailed = cellFor(mixedBoard, cells, "eth_rsi", "ETH");

    expect(faceClass(notDefinable)).toBe("cell--not-definable");
    expect(faceClass(fetchFailed)).toBe("cell--fetch-failed");
    expect(part(notDefinable, "word")).toBe("n/a");
    expect(part(fetchFailed, "word")).toBe("Unavailable");
    expect(part(notDefinable, "glyph")).not.toBe(part(fetchFailed, "glyph"));
    expect(part(notDefinable, "word")).not.toBe(part(fetchFailed, "word"));
    expect(faceClass(notDefinable)).not.toBe(faceClass(fetchFailed));
    expect(part(notDefinable, "detail")).toBe(
      "Daily close is intentionally BTC-only on this board.",
    );
    expect(part(fetchFailed, "detail")).toBe("Synthetic upstream timeout");
  });

  test("the page issues one request to board_read and does not fetch per cell", async () => {
    vi.stubEnv("VITE_SUPABASE_URL", "https://example.supabase.co");
    vi.stubEnv("VITE_SUPABASE_ANON_KEY", "test-key");
    const boardRows = definitions.map((definition, index) => ({
      id: index + 1,
      indicator_key: definition.key,
      asset: definition.definable_for[0],
      measured_on: definition.definable_for[0],
      value: 100 + index,
      status: "OK",
      reason: null,
      source_vendor: definition.vendor,
      endpoint: definition.endpoint,
      source_field: definition.source_field,
      fetched_at: new Date().toISOString(),
      source_timestamp: new Date().toISOString(),
    }));
    const fetchMock = vi.fn<typeof fetch>(async (input) => {
      const { pathname } = new URL(String(input));
      const body =
        pathname === "/rest/v1/board_read"
          ? boardRows
          : pathname === "/rest/v1/datapoints_read"
            ? [boardRows[0]]
            : [
                {
                  datapoint_a_id: 1,
                  datapoint_b_id: null,
                  divergence_bps: null,
                  tolerance_bps_at_write: null,
                  status: "NOT_CORROBORATED",
                  reason: "FETCH_FAILED",
                },
              ];
      return new Response(JSON.stringify(body), { status: 200 });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    await waitFor(() => expect(screen.getAllByRole("cell")).toHaveLength(48));
    await screen.findByLabelText("Not corroborated value");

    const urls = fetchMock.mock.calls.map(([input]) => new URL(String(input)));
    const boardRequests = urls.filter(
      (url) => url.pathname === "/rest/v1/board_read",
    );
    expect(boardRequests).toHaveLength(1);
    expect(boardRequests[0].searchParams.get("select")).toBe("*");
    expect(boardRequests[0].searchParams.has("indicator_key")).toBe(false);
    expect(boardRequests[0].searchParams.has("asset")).toBe(false);
    // The only other requests belong to the one BTC corroboration panel, not to the cells.
    expect(urls.map((url) => url.pathname).sort()).toEqual([
      "/rest/v1/board_read",
      "/rest/v1/corroborations_read",
      "/rest/v1/datapoints_read",
    ]);
    expect(
      screen.getAllByRole("cell").filter((cell) => faceClass(cell) === "cell--ok"),
    ).toHaveLength(definitions.length);
  });

  test("rendering the mixed fixture produces all five faces at once", () => {
    const cells = renderMatrix(mixedBoard);
    const faces = new Set(cells.map(faceClass));

    expect(faces).toEqual(
      new Set([
        "cell--ok",
        "cell--stale",
        "cell--not-definable",
        "cell--paywalled",
        "cell--fetch-failed",
      ]),
    );

    const stale = cellFor(mixedBoard, cells, "btc_daily_close", "BTC");
    expect(part(stale, "word")).toBe("Stale");
    expect(part(stale, "detail")).toBe("11,111.1 · 1 day old");

    const paywalled = cellFor(mixedBoard, cells, "sol_atr", "SOL");
    expect(part(paywalled, "word")).toBe("Requires paid tier");

    const ok = cells.find((cell) => faceClass(cell) === "cell--ok");
    expect(ok && part(ok, "word")).toBe("OK");
    expect(ok && part(ok, "detail")).toMatch(/^\d[\d,]*(\.\d+)?$/);

    const fetchFailed = cellFor(mixedBoard, cells, "eth_rsi", "ETH");
    expect(part(fetchFailed, "word")).toBe("Unavailable");
    expect(part(fetchFailed, "detail")).toBe("Synthetic upstream timeout");
  });
});

describe("integration: the assembled page against live Supabase", () => {
  test("the assembled page loads 48 cells from the live board_read endpoint", async () => {
    // Real URL, real anon key, real fetch. Missing configuration fails here; it never skips.
    expect(import.meta.env.VITE_SUPABASE_URL).toBeTruthy();
    expect(import.meta.env.VITE_SUPABASE_ANON_KEY).toBeTruthy();
    const liveFetch = vi.spyOn(globalThis, "fetch");

    renderPage();

    await waitFor(
      () => expect(screen.getAllByRole("cell")).toHaveLength(48),
      { timeout: 20_000 },
    );
    const cells = screen.getAllByRole("cell");
    for (const cell of cells) {
      expect(cell.textContent?.trim()).not.toBe("");
    }
    expect(screen.getByRole("status")).toHaveTextContent(/of 48 indicators OK/);

    const boardRequests = liveFetch.mock.calls.filter(
      ([input]) => new URL(String(input)).pathname === "/rest/v1/board_read",
    );
    expect(boardRequests).toHaveLength(1);

    liveFetch.mockRestore();

    // Every registered row the live view holds landed on a cell: the only NOT_FETCHED cells are
    // the ones the view has no row for, beside the three the registry declares not definable.
    const liveRows = (await (
      await fetch(String(boardRequests[0][0]), boardRequests[0][1])
    ).json()) as { indicator_key: string; asset: string }[];
    const registeredRows = liveRows.filter((row) =>
      definitions.some(
        (definition) =>
          definition.key === row.indicator_key &&
          definition.definable_for.includes(row.asset),
      ),
    );
    expect(registeredRows.length).toBeGreaterThan(0);
    const declaredNotDefinable = emptyResponseBoard.cells.filter(
      (cell) => "reason" in cell.state && cell.state.reason === "NOT_DEFINABLE",
    ).length;
    expect(
      cells.filter((cell) => faceClass(cell) === "cell--not-fetched"),
    ).toHaveLength(48 - declaredNotDefinable - registeredRows.length);
  }, 30_000);
});

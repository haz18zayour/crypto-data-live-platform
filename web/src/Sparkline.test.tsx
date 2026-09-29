// Reads styles.css from disk, so it needs the node types tsconfig.app.json does not load.
/// <reference types="node" />
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import type { BoardCell } from "./board";
import { CellFace } from "./CellFace";
import type { Datapoint } from "./datapoint";
import type { HistoryPoint } from "./history";
import { Sparkline } from "./Sparkline";

// Not a `?raw` import: vitest does not process CSS by default and hands that import back empty.
// Resolved from the working directory, which `npm --prefix web test` sets to web/: under jsdom
// import.meta.url is an http URL, not a file path.
const styles = readFileSync(join(process.cwd(), "src", "styles.css"), "utf8");

const DAY = 86_400_000;
const MINUTE = 60_000;
const START = Date.parse("2026-07-01T00:00:00Z");

function point(time: number, value: number): HistoryPoint {
  return {
    id: time,
    indicatorKey: "btc_daily_close",
    asset: "BTC",
    measuredOn: "BTC",
    value,
    status: "OK",
    sourceVendor: "okx",
    endpoint: "https://example.test/history",
    sourceField: "close",
    fetchedAt: new Date(time).toISOString(),
    sourceTimestamp: new Date(time).toISOString(),
    referencePeriod: null,
    publishedAt: null,
    origin: "live",
  };
}

function daily(values: number[], start = START): HistoryPoint[] {
  return values.map((value, index) => point(start + index * DAY, value));
}

// The polyline's vertices, in drawing order.
function vertices(container: HTMLElement): [number, number][] {
  const line = container.querySelector("polyline");
  expect(line).not.toBeNull();
  return line!
    .getAttribute("points")!
    .split(" ")
    .map((pair) => pair.split(",").map(Number) as [number, number]);
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("min and max labels", () => {
  test("the max and min are each printed with the real date of their own point, at the axis ends", () => {
    const history = daily([100, 104, 131.5, 99, 87.25, 110, 120, 118]);
    const { container } = render(<Sparkline history={history} />);

    const max = container.querySelector(".sparkline-max") as HTMLElement;
    const min = container.querySelector(".sparkline-min") as HTMLElement;
    expect(within(max).getByText("max")).toBeInTheDocument();
    expect(within(max).getByText("131.5")).toBeInTheDocument();
    expect(within(max).getByText("03 Jul 2026")).toHaveAttribute(
      "dateTime",
      history[2].sourceTimestamp,
    );
    expect(within(min).getByText("min")).toBeInTheDocument();
    expect(within(min).getByText("87.25")).toBeInTheDocument();
    expect(within(min).getByText("05 Jul 2026")).toHaveAttribute(
      "dateTime",
      history[4].sourceTimestamp,
    );

    // The max sits above the plot and the min below it: the two ends of the value axis.
    const svg = container.querySelector("svg")!;
    expect(max.compareDocumentPosition(svg) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(svg.compareDocumentPosition(min) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // And the drawn extremes are the top and bottom of the plot.
    const ys = vertices(container).map(([, y]) => y);
    expect(ys[2]).toBe(Math.min(...ys));
    expect(ys[4]).toBe(Math.max(...ys));
  });

  test("the RPC's newest-first order does not change which dates are labelled", () => {
    const history = daily([5, 9, 1, 4, 6, 7, 8]);
    const { container } = render(<Sparkline history={[...history].reverse()} />);

    expect(container.querySelector(".sparkline-max time")).toHaveAttribute(
      "dateTime",
      history[1].sourceTimestamp,
    );
    expect(container.querySelector(".sparkline-min time")).toHaveAttribute(
      "dateTime",
      history[2].sourceTimestamp,
    );
  });
});

describe("no verdict drawn as a shape or a colour", () => {
  const MARK_SELECTOR = "svg *";

  test("the chart is one unfilled line and one last-point marker, with no band, percentile or range-position mark", () => {
    const { container } = render(
      <Sparkline history={daily([3, 1, 4, 1, 5, 9, 2, 6, 5, 3])} />,
    );
    const marks = [...container.querySelectorAll(MARK_SELECTOR)].map((element) =>
      element.tagName.toLowerCase(),
    );

    expect(marks).toEqual(["polyline", "circle"]);
    expect(container.querySelectorAll("rect, path, polygon, line, linearGradient, pattern")).toHaveLength(0);
    expect(container.textContent).not.toMatch(
      /percentile|%ile|rank|range position|normal|overbought|oversold|high|low|above|below|average|mean|\d+\s*%/i,
    );
    // No inline colour anywhere: every mark takes its ink from the stylesheet.
    for (const element of container.querySelectorAll("*")) {
      for (const attribute of ["fill", "stroke", "style", "color"]) {
        expect(element.hasAttribute(attribute), `${element.tagName} has ${attribute}`).toBe(false);
      }
    }
  });

  test("a series ending at its max and one ending at its min render identical marks apart from coordinates", () => {
    const endsHigh = render(<Sparkline history={daily([2, 3, 1, 4, 2, 3, 9])} />);
    const highMarkup = endsHigh.container.querySelector("svg")!.outerHTML;
    endsHigh.unmount();
    const endsLow = render(<Sparkline history={daily([8, 7, 9, 6, 8, 7, 1])} />);
    const lowMarkup = endsLow.container.querySelector("svg")!.outerHTML;

    const shapeOnly = (markup: string) => markup.replace(/-?\d+(\.\d+)?/g, "#");
    expect(shapeOnly(highMarkup)).toBe(shapeOnly(lowMarkup));
  });

  test("the sparkline's styles use neutral ink only, never a status colour", () => {
    const sparklineRules = styles.match(/[^{}]*\.(sparkline|cell-history)[^{}]*\{[^}]*\}/g) ?? [];

    expect(sparklineRules.length).toBeGreaterThan(0);
    for (const rule of sparklineRules) {
      expect(rule).not.toMatch(/--(ok|stale|paywalled|failed)|#[0-9a-f]{3,8}\b|rgb|hsl|gradient|opacity/i);
    }
  });
});

describe("the printed time window", () => {
  test("each cell prints the span its own points cover, so different depths never read alike", () => {
    const shallow = render(<Sparkline history={daily([1, 2, 3, 4, 5, 6, 7, 8])} />);
    expect(shallow.container.querySelector(".sparkline-window")).toHaveTextContent(/^7d$/);
    shallow.unmount();

    const deep = render(
      <Sparkline history={daily(Array.from({ length: 91 }, (_, index) => index % 7))} />,
    );
    expect(deep.container.querySelector(".sparkline-window")).toHaveTextContent(/^90d$/);
    deep.unmount();

    const fast = render(
      <Sparkline
        history={Array.from({ length: 12 }, (_, index) => point(START + index * 5 * MINUTE, index))}
      />,
    );
    expect(fast.container.querySelector(".sparkline-window")).toHaveTextContent(/^1h$/);
  });
});

describe("the cadence-tiered minimum", () => {
  test("a daily series with six points shows the not-enough-history state instead of a line", () => {
    const { container } = render(<Sparkline history={daily([1, 2, 3, 4, 5, 6])} />);

    expect(container.querySelector("svg")).toBeNull();
    expect(container).toHaveTextContent("Not enough history yet (6 points since 01 Jul 2026)");
    expect(container.querySelector(".sparkline-insufficient time")).toHaveAttribute(
      "dateTime",
      new Date(START).toISOString(),
    );
  });

  test("a daily series with seven points but one distinct value does not draw a flat line", () => {
    const { container } = render(<Sparkline history={daily([4, 4, 4, 4, 4, 4, 4])} />);

    expect(container.querySelector("svg")).toBeNull();
    expect(container).toHaveTextContent("Not enough history yet (7 points since 01 Jul 2026)");
  });

  test("a daily series with seven points and two distinct values draws", () => {
    const { container } = render(<Sparkline history={daily([4, 4, 4, 4, 4, 4, 5])} />);

    expect(container.querySelector("svg polyline")).not.toBeNull();
    expect(container.querySelector(".sparkline-insufficient")).toBeNull();
  });

  test("a monthly series draws from four points, and three is still not enough", () => {
    const monthly = (count: number) =>
      Array.from({ length: count }, (_, index) =>
        point(Date.UTC(2026, index, 1), 21_000 + index * 40),
      );

    const four = render(<Sparkline history={monthly(4)} />);
    expect(four.container.querySelector("svg polyline")).not.toBeNull();
    four.unmount();

    const three = render(<Sparkline history={monthly(3)} />);
    expect(three.container.querySelector("svg")).toBeNull();
    expect(three.container).toHaveTextContent(
      "Not enough history yet (3 points since 01 Jan 2026)",
    );
  });

  test("no points at all is still the not-enough-history state, never a blank", () => {
    render(<Sparkline history={[]} />);

    expect(screen.getByText(/Not enough history yet \(0 points\)/)).toBeInTheDocument();
  });
});

describe("not enough history is its own state", () => {
  test("its glyph, words and styling differ from every existing absence face", () => {
    const provenance = {
      indicatorKey: "btc_daily_close",
      asset: "BTC",
      measuredOn: "BTC",
      sourceVendor: "okx",
      endpoint: "https://example.test",
      sourceField: "close",
      fetchedAt: null,
      sourceTimestamp: null,
    };
    const absences: Datapoint[] = [
      { ...provenance, status: "UNAVAILABLE", reason: "NOT_DEFINABLE" },
      { ...provenance, status: "UNAVAILABLE", reason: "PAYWALLED" },
      { ...provenance, status: "ERROR", reason: "FETCH_FAILED", detail: "HTTP 500" },
      { ...provenance, status: "UNAVAILABLE", reason: "NOT_FETCHED" },
    ];
    const cells: BoardCell[] = absences.map((state) => ({
      family: "daily_close",
      asset: "BTC",
      indicatorKey: state.indicatorKey,
      state,
    }));
    const board = render(
      <table>
        <tbody>
          <tr>
            {cells.map((cell, index) => (
              <CellFace key={index} cell={cell} now={new Date(START)} />
            ))}
          </tr>
        </tbody>
      </table>,
    );
    const faces = [...board.container.querySelectorAll("td")].map((cell) => ({
      className: cell.className,
      glyph: cell.querySelector(".cell-glyph")!.textContent!,
      word: cell.querySelector(".cell-word")!.textContent!,
      text: cell.textContent!,
    }));
    board.unmount();

    const { container } = render(<Sparkline history={daily([1, 2])} />);
    const insufficient = container.querySelector(".sparkline-insufficient") as HTMLElement;
    const glyph = insufficient.querySelector(".sparkline-insufficient-glyph")!.textContent!;

    expect(insufficient).toHaveTextContent(/not enough history yet/i);
    for (const face of faces) {
      expect(glyph).not.toBe(face.glyph);
      expect(insufficient.textContent).not.toContain(face.word);
      expect(face.text).not.toMatch(/not enough history/i);
      expect(face.className.split(" ")).not.toContain(insufficient.className);
    }
    // Every absence word the board uses, none of which this state may borrow.
    expect(insufficient.textContent).not.toMatch(
      /n\/a|not definable|paid tier|unavailable|fetch failed|not fetched/i,
    );
  });
});

describe("a real time axis", () => {
  test("sparse daily history then dense 5-minute points are all drawn, spaced by time", () => {
    const backfill = daily([100, 104, 99, 101, 97, 103, 105, 102, 98, 100]);
    const liveStart = START + 10 * DAY;
    const live = Array.from({ length: 60 }, (_, index) =>
      point(liveStart + index * 5 * MINUTE, 100 + Math.sin(index) * 3),
    );
    const history = [...backfill, ...live];
    const { container } = render(<Sparkline history={history} />);
    const drawn = vertices(container);

    // No resampling: one vertex per returned point.
    expect(drawn).toHaveLength(history.length);

    // Each x is proportional to the point's own time, not its index.
    const t0 = Date.parse(history[0].sourceTimestamp);
    const tEnd = Date.parse(history[history.length - 1].sourceTimestamp);
    const [xStart] = drawn[0];
    const [xEnd] = drawn[drawn.length - 1];
    history.forEach((entry, index) => {
      const expected =
        xStart + ((Date.parse(entry.sourceTimestamp) - t0) / (tEnd - t0)) * (xEnd - xStart);
      expect(drawn[index][0]).toBeCloseTo(expected, 1);
    });

    // So the 60 dense points (about 5 hours) crowd into a sliver at the right, while the ten
    // daily points spread across the rest: the density change stays visible.
    const liveWidth = xEnd - drawn[backfill.length][0];
    expect(liveWidth / (xEnd - xStart)).toBeLessThan(0.03);
    expect(drawn[backfill.length - 1][0] - xStart).toBeGreaterThan((xEnd - xStart) * 0.85);
  });
});

describe("history in the cell detail", () => {
  test("opening an OK cell reads its history pinned to the cell's own vendor and draws it", async () => {
    const rows = daily([10, 12, 11, 13, 9, 14, 12, 15]).map((entry) => ({
      id: entry.id,
      indicator_key: entry.indicatorKey,
      asset: entry.asset,
      measured_on: entry.measuredOn,
      value: entry.value,
      status: entry.status,
      source_vendor: entry.sourceVendor,
      endpoint: entry.endpoint,
      source_field: entry.sourceField,
      fetched_at: entry.fetchedAt,
      source_timestamp: entry.sourceTimestamp,
      reference_period: null,
      published_at: null,
      origin: entry.origin,
    }));
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify(rows), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    vi.stubEnv("VITE_SUPABASE_URL", "https://example.supabase.co");
    vi.stubEnv("VITE_SUPABASE_ANON_KEY", "test-key");

    const cell: BoardCell = {
      family: "daily_close",
      asset: "BTC",
      indicatorKey: "btc_daily_close",
      state: {
        indicatorKey: "btc_daily_close",
        asset: "BTC",
        measuredOn: "BTC",
        sourceVendor: "okx",
        endpoint: "https://example.test",
        sourceField: "close",
        fetchedAt: "2026-07-08T00:01:00Z",
        sourceTimestamp: "2026-07-08T00:00:00Z",
        status: "OK",
        value: 15,
      },
    };
    const { container } = render(
      <table>
        <tbody>
          <tr>
            <CellFace cell={cell} now={new Date("2026-07-08T00:05:00Z")} />
          </tr>
        </tbody>
      </table>,
    );

    expect(fetchMock).not.toHaveBeenCalled();
    fireEvent.click(container.querySelector("summary")!);
    fireEvent(container.querySelector("details")!, new Event("toggle"));

    await waitFor(() => expect(container.querySelector(".sparkline polyline")).not.toBeNull());
    expect(JSON.parse(fetchMock.mock.calls[0][1]!.body as string)).toMatchObject({
      p_indicator_key: "btc_daily_close",
      p_asset: "BTC",
      p_source_vendor: "okx",
    });
    expect(container.querySelector(".sparkline-window")).toHaveTextContent("7d");
  });
});

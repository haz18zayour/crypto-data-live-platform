import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import { buildBoard, type BoardRegistryEntry } from "./board";
import { CoverageHeadline } from "./CoverageHeadline";
import { countCoverage } from "./coverage";
import type { Datapoint, Provenance } from "./datapoint";
import { mixedBoard } from "./fixtures/mixedBoard";

const assets = ["BTC", "ETH", "SOL", "BNB"] as const;
const registry: BoardRegistryEntry[] = assets.map((asset) => ({
  key: `${asset.toLowerCase()}_metric`,
  definable_for: [asset],
}));

function ok(indicatorKey: string, asset: string): Datapoint {
  const provenance = {
    indicatorKey,
    asset,
    measuredOn: asset,
    sourceVendor: "TEST",
    endpoint: "https://example.test/data",
    sourceField: "value",
    fetchedAt: "2026-09-14T00:01:00Z",
    sourceTimestamp: "2026-09-14T00:00:00Z",
  } satisfies Provenance;
  return { ...provenance, status: "OK", value: 1 };
}

describe("coverage headline", () => {
  test("the denominator stays equal to the board cell count when database rows are missing", () => {
    const oneReturnedRow = [ok("btc_metric", "BTC")];
    const board = buildBoard(registry, oneReturnedRow, assets);

    const coverage = countCoverage(board);

    expect(oneReturnedRow).toHaveLength(1);
    expect(board.cells).toHaveLength(4);
    expect(coverage.total).toBe(board.cells.length);
    expect(coverage.total).not.toBe(oneReturnedRow.length);
    expect(coverage).toMatchObject({ ok: 1, unavailable: 3 });
  });

  test("the mixed fixture reports every state separately", () => {
    expect(countCoverage(mixedBoard)).toEqual({
      total: 145,
      ok: 76,
      stale: 1,
      unavailable: 55,
      notDefinable: 11,
      paywalled: 1,
      fetchFailed: 1,
    });
  });

  test("the mutually exclusive state counts sum to the denominator", () => {
    const { total, ...states } = countCoverage(mixedBoard);

    expect(Object.values(states).reduce((sum, count) => sum + count, 0)).toBe(
      total,
    );
  });

  test("not definable, paywalled and fetch failed render as separate figures", () => {
    render(<CoverageHeadline board={mixedBoard} />);

    const status = screen.getByRole("status");
    expect(status).toHaveTextContent("11 not definable");
    expect(status).toHaveTextContent("1 paywalled");
    expect(status).toHaveTextContent("1 fetch failed");
    expect(status).not.toHaveTextContent(/(^|\D)5 (missing|unavailable)/i);
  });

  test("an all-OK board still shows its denominator and every zero count", () => {
    const allOkBoard = buildBoard(
      registry,
      registry.map((definition) =>
        ok(definition.key, definition.definable_for[0]),
      ),
      assets,
    );

    render(<CoverageHeadline board={allOkBoard} />);

    expect(screen.getByRole("status")).toHaveTextContent(
      "4 of 4 indicators OK · 0 stale · 0 unavailable 0 not definable · 0 paywalled · 0 fetch failed",
    );
  });

  test("assistive technology receives the entire headline as one atomic status region", () => {
    render(<CoverageHeadline board={mixedBoard} />);

    const statuses = screen.getAllByRole("status");
    expect(statuses).toHaveLength(1);
    expect(statuses[0]).toHaveAttribute("aria-atomic", "true");
    expect(statuses[0]).toHaveTextContent(
      "76 of 145 indicators OK · 1 stale · 55 unavailable 11 not definable · 1 paywalled · 1 fetch failed",
    );
    expect(statuses[0]).toHaveStyle({ fontVariantNumeric: "tabular-nums" });
  });
});

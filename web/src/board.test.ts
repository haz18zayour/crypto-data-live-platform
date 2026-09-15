import { parse } from "yaml";
import { describe, expect, test } from "vitest";

import registryYaml from "../../ingest/registry.yaml?raw";
import {
  BOARD_ASSETS,
  buildBoard,
  type BoardRegistryEntry,
} from "./board";
import type { Datapoint } from "./datapoint";

const registry = parse(registryYaml) as BoardRegistryEntry[];

function provenance(indicatorKey: string, asset: string) {
  return {
    indicatorKey,
    asset,
    measuredOn: asset,
    sourceVendor: "TEST",
    endpoint: "https://example.test/data",
    sourceField: "value",
    fetchedAt: "2026-09-14T00:01:00Z",
    sourceTimestamp: "2026-09-14T00:00:00Z",
  };
}

describe("buildBoard", () => {
  test("the board model built from the parsed registry and the four assets yields exactly 56 cells", () => {
    const board = buildBoard(registry, [], BOARD_ASSETS);

    expect(board.families).toHaveLength(14);
    expect(board.assets).toHaveLength(4);
    expect(board.cells).toHaveLength(
      board.families.length * board.assets.length,
    );
  });

  test("every one of the 56 cells carries a state and none is undefined or empty", () => {
    const board = buildBoard(registry, [], BOARD_ASSETS);

    expect(board.cells).toHaveLength(
      board.families.length * board.assets.length,
    );
    for (const cell of board.cells) {
      expect(cell.state).toBeDefined();
      expect(cell.state).not.toBe("");
      expect(cell.state.status).toBeTruthy();
    }
  });

  test("declared daily close gaps are NOT_DEFINABLE and carry the registry reason unchanged", () => {
    const board = buildBoard(registry, [], BOARD_ASSETS);
    const declaration = registry.find(
      (entry) => entry.key === "btc_daily_close",
    )?.not_definable;
    const dailyCloseGaps = board.cells.filter(
      (cell) => cell.family === "daily_close" && cell.asset !== "BTC",
    );

    expect(dailyCloseGaps).toHaveLength(BOARD_ASSETS.length - 1);
    expect(declaration?.assets).toEqual(["ETH", "SOL", "BNB"]);
    expect(dailyCloseGaps.map((cell) => cell.state)).toEqual([
      {
        status: "UNAVAILABLE",
        reason: "NOT_DEFINABLE",
        detail: declaration?.reason,
      },
      {
        status: "UNAVAILABLE",
        reason: "NOT_DEFINABLE",
        detail: declaration?.reason,
      },
      {
        status: "UNAVAILABLE",
        reason: "NOT_DEFINABLE",
        detail: declaration?.reason,
      },
    ]);
  });

  test("without the declaration all three daily close gaps return to NOT_FETCHED", () => {
    const registryWithoutDeclaration = registry.map((entry) => {
      const { not_definable: _removed, ...definition } = entry;
      return definition;
    });
    const board = buildBoard(registryWithoutDeclaration, [], BOARD_ASSETS);
    const dailyCloseGaps = board.cells.filter(
      (cell) => cell.family === "daily_close" && cell.asset !== "BTC",
    );

    expect(dailyCloseGaps.map((cell) => cell.state)).toEqual([
      { status: "UNAVAILABLE", reason: "NOT_FETCHED" },
      { status: "UNAVAILABLE", reason: "NOT_FETCHED" },
      { status: "UNAVAILABLE", reason: "NOT_FETCHED" },
    ]);
  });

  test("a registry key that does not begin with its own lowercased asset throws", () => {
    const malformedRegistry: BoardRegistryEntry[] = [
      { key: "btc_daily_close", definable_for: ["BNB"] },
    ];

    expect(() => buildBoard(malformedRegistry, [], BOARD_ASSETS)).toThrow(
      /btc_daily_close.*bnb_/,
    );
  });

  test("a cell whose registry entry exists but whose board row is missing is also NOT_FETCHED", () => {
    const board = buildBoard(registry, [], BOARD_ASSETS);
    const registeredButMissing = board.cells.find(
      (cell) => cell.indicatorKey === "btc_daily_close",
    );

    expect(registeredButMissing?.state).toEqual({
      status: "UNAVAILABLE",
      reason: "NOT_FETCHED",
    });
  });

  test("the model maps OK STALE UNAVAILABLE and ERROR rows onto their cells without altering the value", () => {
    const smallRegistry: BoardRegistryEntry[] = BOARD_ASSETS.map((asset) => ({
      key: `${asset.toLowerCase()}_metric`,
      definable_for: [asset],
    }));
    const rows = [
      { ...provenance("btc_metric", "BTC"), status: "OK", value: 12.25 },
      { ...provenance("eth_metric", "ETH"), status: "STALE", value: -4.5 },
      {
        ...provenance("sol_metric", "SOL"),
        status: "UNAVAILABLE",
        reason: "PAYWALLED",
      },
      {
        ...provenance("bnb_metric", "BNB"),
        status: "ERROR",
        reason: "FETCH_FAILED",
        detail: "upstream timeout",
      },
    ] satisfies Datapoint[];

    const board = buildBoard(smallRegistry, rows, BOARD_ASSETS);

    expect(board.cells.map((cell) => cell.state.status)).toEqual([
      "OK",
      "STALE",
      "UNAVAILABLE",
      "ERROR",
    ]);
    expect(board.cells.map((cell) => cell.state)).toEqual(rows);
    expect(board.cells[0].state).toHaveProperty("value", 12.25);
    expect(board.cells[1].state).toHaveProperty("value", -4.5);
  });
});

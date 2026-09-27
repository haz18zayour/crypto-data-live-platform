import { parse } from "yaml";
import { describe, expect, test, vi } from "vitest";

import registryYaml from "../../../ingest/registry.yaml?raw";
import {
  BOARD_ASSETS,
  buildBoard,
  type BoardRegistryEntry,
} from "../board";
import type { Datapoint } from "../datapoint";
import { mixedBoard } from "./mixedBoard";

vi.mock("../board", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../board")>();
  return { ...actual, buildBoard: vi.fn(actual.buildBoard) };
});

type FixtureRegistryEntry = BoardRegistryEntry & {
  vendor: string;
  endpoint: string;
  source_field: string;
};

const registry = parse(registryYaml) as FixtureRegistryEntry[];
const boardAssetSet: ReadonlySet<string> = new Set(BOARD_ASSETS);
const boardRegistry = registry.filter((definition) =>
  definition.definable_for.some((asset) => boardAssetSet.has(asset)),
);

describe("mixed board fixture", () => {
  test("the fixture contains at least one cell in each of OK STALE NOT_DEFINABLE and FETCH_FAILED", () => {
    expect(mixedBoard.cells.some((cell) => cell.state.status === "OK")).toBe(
      true,
    );
    expect(
      mixedBoard.cells.some((cell) => cell.state.status === "STALE"),
    ).toBe(true);
    expect(
      mixedBoard.cells.some(
        (cell) =>
          cell.state.status === "UNAVAILABLE" &&
          cell.state.reason === "NOT_DEFINABLE",
      ),
    ).toBe(true);
    const notDefinableCells = mixedBoard.cells.filter(
      (cell) =>
        cell.state.status === "UNAVAILABLE" &&
        cell.state.reason === "NOT_DEFINABLE",
    );
    expect(notDefinableCells).toHaveLength(10);
    for (const cell of notDefinableCells) {
      expect(cell.state).toHaveProperty("detail");
      expect("detail" in cell.state && cell.state.detail.trim()).toBeTruthy();
    }
    expect(
      mixedBoard.cells.find(
        (cell) => cell.indicatorKey === "btc_daily_close",
      )?.state,
    ).toMatchObject({ status: "STALE", value: 11111.11 });
    expect(
      mixedBoard.cells.some(
        (cell) =>
          cell.state.status === "ERROR" &&
          cell.state.reason === "FETCH_FAILED",
      ),
    ).toBe(true);
    expect(
      mixedBoard.cells.some(
        (cell) =>
          cell.state.status === "UNAVAILABLE" &&
          cell.state.reason === "PAYWALLED",
      ),
    ).toBe(true);
  });

  test("the fixture has the same cell shape the live board model produces", () => {
    const liveShape = buildBoard(registry, [], BOARD_ASSETS);

    expect(mixedBoard.assets).toEqual(liveShape.assets);
    expect(mixedBoard.families).toEqual(liveShape.families);
    expect(mixedBoard.cells).toHaveLength(liveShape.cells.length);
    expect(mixedBoard.cells.map(({ family, asset }) => ({ family, asset }))).toEqual(
      liveShape.cells.map(({ family, asset }) => ({ family, asset })),
    );
  });

  test("the fixture passes registry rows through the real board model", () => {
    const fixtureBuild = vi.mocked(buildBoard).mock;
    const fixtureDatapoints = mixedBoard.cells
      .map((cell) => cell.state)
      .filter((state): state is Datapoint => "indicatorKey" in state);
    const [calledRegistry, calledRows, calledAssets] = fixtureBuild.calls[0];

    expect(fixtureDatapoints).toHaveLength(boardRegistry.length);
    expect(calledRegistry).toEqual(registry);
    expect(calledRows).toHaveLength(boardRegistry.length);
    expect(calledRows.map((row) => row.indicatorKey)).toEqual(
      boardRegistry.map((definition) => definition.key),
    );
    expect(calledAssets).toEqual(BOARD_ASSETS);
    expect(fixtureBuild.results[0]?.value).toBe(mixedBoard);
    expect(buildBoard(registry, fixtureDatapoints, BOARD_ASSETS)).toEqual(
      mixedBoard,
    );
  });

  test("the fixture cells carry real provenance including vendor and source timestamp", () => {
    const registryByKey = new Map(registry.map((entry) => [entry.key, entry]));
    const populatedCells = mixedBoard.cells.filter(
      (cell): cell is typeof cell & { state: Datapoint } =>
        "indicatorKey" in cell.state,
    );

    expect(populatedCells).toHaveLength(boardRegistry.length);
    for (const cell of populatedCells) {
      const definition = registryByKey.get(cell.indicatorKey);
      expect(definition).toBeDefined();
      expect(cell.state.sourceVendor).toBe(definition?.vendor);
      expect(cell.state.endpoint).toBe(definition?.endpoint);
      expect(cell.state.sourceField).toBe(definition?.source_field);
      expect(cell.state.sourceTimestamp).toMatch(
        /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/,
      );
    }
  });

  test("the fixture board is reachable only when import.meta.env.DEV is true", async () => {
    vi.resetModules();
    vi.stubEnv("DEV", false);

    await expect(import("./mixedBoard")).rejects.toThrow(
      /development-only mixed board fixture/i,
    );

    vi.unstubAllEnvs();
  });
});

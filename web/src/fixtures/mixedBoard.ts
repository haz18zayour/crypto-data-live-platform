import { parse } from "yaml";

import registryYaml from "../../../ingest/registry.yaml?raw";
import {
  BOARD_ASSETS,
  buildBoard,
  type BoardIntegrityRow,
  type BoardRegistryEntry,
} from "../board";
import type { Datapoint, Provenance } from "../datapoint";

const FIXTURE_SENTINEL = "US_505__MIXED_BOARD_FIXTURE__DEV_ONLY";

if (!import.meta.env.DEV) {
  throw new Error(`${FIXTURE_SENTINEL}: development-only mixed board fixture`);
}

type FixtureRegistryEntry = BoardRegistryEntry & {
  vendor: string;
  endpoint: string;
  source_field: string;
};

const registry = parse(registryYaml) as FixtureRegistryEntry[];
const boardAssetSet: ReadonlySet<string> = new Set(BOARD_ASSETS);
const SOURCE_TIMESTAMP = "2026-09-13T00:00:00Z";

const rows = registry.flatMap((definition, index): Datapoint[] => {
  const asset = definition.definable_for[0];
  if (!boardAssetSet.has(asset)) {
    return [];
  }
  const provenance = {
    indicatorKey: definition.key,
    asset,
    measuredOn: asset,
    sourceVendor: definition.vendor,
    endpoint: definition.endpoint,
    sourceField: definition.source_field,
    fetchedAt: "2026-09-14T00:01:00Z",
    sourceTimestamp: SOURCE_TIMESTAMP,
  } satisfies Provenance;

  if (definition.key === "btc_daily_close") {
    return [{ ...provenance, status: "STALE", value: 11111.11 }];
  }
  if (definition.key === "eth_rsi") {
    return [
      {
        ...provenance,
        status: "ERROR",
        reason: "FETCH_FAILED",
        detail: "Synthetic upstream timeout",
      },
    ];
  }
  if (definition.key === "sol_atr") {
    return [{ ...provenance, status: "UNAVAILABLE", reason: "PAYWALLED" }];
  }
  if (definition.key === "bnb_rsi") {
    return [{ ...provenance, status: "UNAVAILABLE", reason: "NOT_FETCHED" }];
  }
  return [{ ...provenance, status: "OK", value: index + 1.11 }];
});

export const mixedBoardIntegrityRows = [
  {
    indicatorKey: "btc_mvrv",
    asset: "BTC",
    sourceVendor: "coinmetrics",
    frozen: true,
    frozenState: "frozen",
    frozenSinceSourceTimestamp: "2026-09-10T00:00:00Z",
    derivesFrom: null,
  },
] satisfies BoardIntegrityRow[];

export const mixedBoard = buildBoard(
  registry,
  rows,
  BOARD_ASSETS,
  mixedBoardIntegrityRows,
);

import type { Datapoint } from "./datapoint";

// MACRO is not a tracked crypto asset — it is the board's pseudo-asset column for
// market-wide indicators (FRED macro series, Fear & Greed) that have no per-asset value.
// Owner decision, 2026-09-28: represent it as a 5th column rather than a separate panel.
export const BOARD_ASSETS = ["BTC", "ETH", "SOL", "BNB", "MACRO"] as const;

export type BoardRegistryEntry = {
  key: string;
  definable_for: readonly string[];
  not_definable?: {
    assets: readonly string[];
    reason?: string;
    reasons?: readonly string[];
  };
};

// Unregistered and registered-but-unfetched are both absences, and neither is settled. Only an
// explicit registry declaration may make a gap read as settled; without one it is NOT_FETCHED.
export type NotFetched = { status: "UNAVAILABLE"; reason: "NOT_FETCHED" };
export type DeclaredNotDefinable = {
  status: "UNAVAILABLE";
  reason: "NOT_DEFINABLE";
  detail: string;
};

export type BoardCell = {
  family: string;
  asset: string;
  indicatorKey: string;
  state: Datapoint | NotFetched | DeclaredNotDefinable;
};

export type BoardModel = {
  assets: readonly string[];
  families: string[];
  cells: BoardCell[];
};

// The strip is asserted, never defaulted: a key that does not begin with its own asset would
// otherwise be filed quietly under the wrong row.
function familyOf(key: string, asset: string): string {
  const prefix = `${asset.toLowerCase()}_`;
  if (!key.startsWith(prefix)) {
    throw new Error(
      `Registry key ${key} does not begin with its asset prefix ${prefix}`,
    );
  }
  return key.slice(prefix.length);
}

export function buildBoard(
  definitions: readonly BoardRegistryEntry[],
  datapoints: readonly Datapoint[],
  assets: readonly string[],
): BoardModel {
  const families = new Set<string>();
  const definitionsByCell = new Map<string, BoardRegistryEntry>();
  const notDefinableByCell = new Map<string, string>();
  for (const definition of definitions) {
    for (const asset of definition.definable_for) {
      if (!assets.includes(asset)) {
        continue;
      }
      const family = familyOf(definition.key, asset);
      families.add(family);
      definitionsByCell.set(`${family}:${asset}`, definition);
      const notDefinable = definition.not_definable;
      if (notDefinable) {
        for (const excludedAsset of notDefinable.assets) {
          const assetPrefix = `${excludedAsset}:`;
          const assetReason = notDefinable.reasons
            ?.find((candidate) => candidate.startsWith(assetPrefix))
            ?.slice(assetPrefix.length)
            .trim();
          const reason =
            assetReason ?? notDefinable.reason;
          if (reason === undefined) {
            throw new Error(
              `Registry not_definable declaration for ${definition.key} is missing ${excludedAsset}'s reason`,
            );
          }
          notDefinableByCell.set(
            `${family}:${excludedAsset}`,
            reason,
          );
        }
      }
    }
  }

  const familyList = [...families];
  return {
    assets: [...assets],
    families: familyList,
    cells: familyList.flatMap((family) =>
      assets.map((asset): BoardCell => {
        const definition = definitionsByCell.get(`${family}:${asset}`);
        const indicatorKey =
          definition?.key ?? `${asset.toLowerCase()}_${family}`;
        const datapoint = datapoints.find(
          (candidate) =>
            candidate.indicatorKey === indicatorKey && candidate.asset === asset,
        );
        const notDefinableReason = notDefinableByCell.get(
          `${family}:${asset}`,
        );
        return {
          family,
          asset,
          indicatorKey,
          state:
            datapoint ??
            (notDefinableReason === undefined
              ? { status: "UNAVAILABLE", reason: "NOT_FETCHED" }
              : {
                  status: "UNAVAILABLE",
                  reason: "NOT_DEFINABLE",
                  detail: notDefinableReason,
                }),
        };
      }),
    ),
  };
}

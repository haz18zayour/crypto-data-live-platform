import { render, screen, within } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import { IntegrityPanel, rollUpFreshnessByVendor } from "./IntegrityPanel";
import type { IntegrityRead, IntegrityRow } from "./integrity";

const computedAt = "2026-09-29T12:00:00.000Z";

function row(
  override: Partial<IntegrityRow> & Pick<IntegrityRow, "sourceVendor">,
): IntegrityRow {
  const { sourceVendor, ...rest } = override;
  return {
    indicatorKey: "btc_daily_close",
    asset: "BTC",
    sourceVendor,
    computedAt,
    latestSourceTimestamp: "2026-09-29T00:00:00.000Z",
    sourceTimestampAgeSeconds: 30 * 60,
    freshnessState: "fresh",
    freshnessWarnSeconds: 60 * 60,
    freshnessStaleSeconds: 2 * 60 * 60,
    freshnessUnmeasurableReason: null,
    frozen: false,
    frozenState: "not_frozen",
    frozenSinceSourceTimestamp: null,
    frozenAfterObservations: 3,
    expectedConstantReason: null,
    derivesFrom: null,
    frozenPropagationUnavailableReason: null,
    ...rest,
  };
}

function read(
  rows: IntegrityRow[],
  selfCheckState: IntegrityRead["selfCheckState"] = "current",
): IntegrityRead {
  return { computedAt, selfCheckState, rows };
}

describe("per-source freshness rollup", () => {
  test("renders one row per source vendor instead of one row per indicator cell", () => {
    render(
      <IntegrityPanel
        read={read([
          row({ sourceVendor: "OKX", indicatorKey: "btc_daily_close" }),
          row({ sourceVendor: "OKX", indicatorKey: "btc_rsi", asset: "BTC" }),
          row({ sourceVendor: "FRED", indicatorKey: "macro_vixcls", asset: "MACRO" }),
        ])}
      />,
    );

    const bodyRows = within(screen.getByRole("table")).getAllByRole("row").slice(1);
    expect(bodyRows).toHaveLength(2);
    expect(screen.getByRole("row", { name: /OKX/i })).toBeInTheDocument();
    expect(screen.getByRole("row", { name: /FRED/i })).toBeInTheDocument();
  });

  test("shows the vendor's worst real age against its freshness thresholds", () => {
    render(
      <IntegrityPanel
        read={read([
          row({
            sourceVendor: "OKX",
            indicatorKey: "btc_daily_close",
            freshnessState: "fresh",
            sourceTimestampAgeSeconds: 30 * 60,
          }),
          row({
            sourceVendor: "OKX",
            indicatorKey: "btc_open_interest",
            freshnessState: "warn",
            sourceTimestampAgeSeconds: 90 * 60,
            freshnessWarnSeconds: 60 * 60,
            freshnessStaleSeconds: 2 * 60 * 60,
          }),
          row({
            sourceVendor: "FRED",
            indicatorKey: "macro_vixcls",
            asset: "MACRO",
            freshnessState: "stale",
            sourceTimestampAgeSeconds: 3 * 24 * 60 * 60,
            freshnessWarnSeconds: 24 * 60 * 60,
            freshnessStaleSeconds: 2 * 24 * 60 * 60,
          }),
        ])}
      />,
    );

    expect(screen.getByRole("row", { name: /OKX/i })).toHaveTextContent(
      "warn: 1.5h old against warn 1.0h / stale 2.0h",
    );
    expect(screen.getByRole("row", { name: /FRED/i })).toHaveTextContent(
      "stale: 3.0d old against warn 1.0d / stale 2.0d",
    );
  });

  test("renders freshness_unmeasurable vendors as unmeasurable instead of a green or numeric age", () => {
    render(
      <IntegrityPanel
        read={read([
          row({
            sourceVendor: "DEFILLAMA",
            indicatorKey: "stablecoin_supply",
            asset: "MACRO",
            freshnessState: "unmeasurable",
            sourceTimestampAgeSeconds: 30,
            freshnessUnmeasurableReason:
              "DefiLlama stablecoinchains provides no per-chain observation timestamp.",
          }),
        ])}
      />,
    );

    const defillama = screen.getByRole("row", { name: /DEFILLAMA/i });
    expect(defillama).toHaveTextContent(
      "unmeasurable: DefiLlama stablecoinchains provides no per-chain observation timestamp.",
    );
    expect(defillama).not.toHaveTextContent(/fresh|warn|stale|old/i);
  });

  test("surfaces a stale integrity read separately from per-vendor freshness", () => {
    render(
      <IntegrityPanel
        read={read(
          [
            row({
              sourceVendor: "OKX",
              freshnessState: "fresh",
              sourceTimestampAgeSeconds: 30,
            }),
          ],
          "stale-self-check",
        )}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Integrity check itself may be stale.",
    );
    expect(screen.getByRole("row", { name: /OKX/i })).toHaveTextContent(
      "fresh: 30s old",
    );
  });

  test("aggregates the real registry vendors with wall-clock-stamped sources unmeasurable", () => {
    const rollups = rollUpFreshnessByVendor([
      row({ sourceVendor: "OKX" }),
      row({ sourceVendor: "COINMETRICS" }),
      row({ sourceVendor: "HELIUS" }),
      row({
        sourceVendor: "VALIDATORS_APP",
        freshnessState: "unmeasurable",
        freshnessUnmeasurableReason:
          "Validators.app validators/mainnet provides no aggregate observation timestamp.",
      }),
      row({ sourceVendor: "FRED" }),
      row({ sourceVendor: "SOSOVALUE" }),
      row({
        sourceVendor: "DEFILLAMA",
        freshnessState: "unmeasurable",
        freshnessUnmeasurableReason:
          "DefiLlama stablecoinchains provides no per-chain observation timestamp.",
      }),
      row({ sourceVendor: "ALTERNATIVE.ME" }),
    ]);

    expect(rollups.map((rollup) => rollup.sourceVendor)).toEqual([
      "ALTERNATIVE.ME",
      "COINMETRICS",
      "DEFILLAMA",
      "FRED",
      "HELIUS",
      "OKX",
      "SOSOVALUE",
      "VALIDATORS_APP",
    ]);
    expect(rollups.filter((rollup) => rollup.kind === "unmeasurable")).toEqual([
      expect.objectContaining({ sourceVendor: "DEFILLAMA" }),
      expect.objectContaining({ sourceVendor: "VALIDATORS_APP" }),
    ]);
  });
});

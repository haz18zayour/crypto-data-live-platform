import { afterEach, describe, expect, it, vi } from "vitest";

import {
  INTEGRITY_SELF_CHECK_STALE_AFTER_MS,
  classifyIntegritySelfCheck,
  fetchIntegrityRead,
  integrityReadFromRpcRows,
} from "./integrity";

const computedAt = "2026-09-29T12:00:00.000Z";

const row = {
  indicator_key: "btc_daily_close",
  asset: "BTC",
  source_vendor: "okx",
  computed_at: computedAt,
  latest_source_timestamp: "2026-09-29T00:00:00.000Z",
  source_timestamp_age_seconds: 43_200,
  freshness_state: "fresh",
  freshness_warn_seconds: 108_000,
  freshness_stale_seconds: 172_800,
  freshness_unmeasurable_reason: null,
  frozen: false,
  frozen_state: "not_frozen",
  frozen_since_source_timestamp: null,
  frozen_after_observations: 3,
  expected_constant_reason: null,
  derives_from: null,
  frozen_propagation_unavailable_reason: null,
} as const;

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("integrity read self-check", () => {
  it("surfaces the server computed_at timestamp alongside the integrity rows", async () => {
    vi.setSystemTime(new Date(computedAt).getTime());
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse([row]));
    vi.stubGlobal("fetch", fetchMock);

    const read = await fetchIntegrityRead({
      supabaseUrl: "https://example.supabase.co",
      anonKey: "test-key",
    });

    expect(read.computedAt).toBe(computedAt);
    expect(read.rows).toEqual([
      expect.objectContaining({
        indicatorKey: "btc_daily_close",
        computedAt,
        freshnessState: "fresh",
        frozenState: "not_frozen",
      }),
    ]);
    expect(String(fetchMock.mock.calls[0][0])).toBe(
      "https://example.supabase.co/rest/v1/rpc/integrity_read",
    );
  });

  it("classifies an old panel read as stale-self-check without changing indicator states", () => {
    vi.setSystemTime(
      new Date(computedAt).getTime() + INTEGRITY_SELF_CHECK_STALE_AFTER_MS + 1,
    );

    const read = integrityReadFromRpcRows([
      {
        ...row,
        freshness_state: "fresh",
        frozen: false,
        frozen_state: "not_frozen",
      },
    ]);

    expect(read.selfCheckState).toBe("stale-self-check");
    expect(read.rows[0]).toMatchObject({
      freshnessState: "fresh",
      frozen: false,
      frozenState: "not_frozen",
    });
  });

  it("classifies a panel read inside the threshold as current", () => {
    vi.setSystemTime(
      new Date(computedAt).getTime() + INTEGRITY_SELF_CHECK_STALE_AFTER_MS,
    );

    expect(classifyIntegritySelfCheck(computedAt)).toBe("current");
  });

  it("uses the browser Date.now for the self-check comparison", () => {
    const browserNow = new Date(computedAt).getTime() + 1;
    const dateNow = vi.spyOn(Date, "now").mockReturnValue(browserNow);

    expect(classifyIntegritySelfCheck(computedAt, 0)).toBe("stale-self-check");
    expect(dateNow).toHaveBeenCalled();
  });
});

import { definitions } from "./registry";
import type { IndicatorKey } from "./registry";

type SupabaseBrowserConfig = {
  supabaseUrl: string;
  anonKey: string;
};

export type IntegrityFreshnessState =
  | "fresh"
  | "warn"
  | "stale"
  | "unmeasurable";

export type IntegrityFrozenState =
  | "frozen"
  | "not_frozen"
  | "expected_constant"
  | "propagation_unavailable"
  | "root_unavailable";

export type IntegritySelfCheckState = "current" | "stale-self-check";

type IntegrityReadRpcRow = {
  indicator_key: IndicatorKey;
  asset: string;
  source_vendor: string;
  computed_at: string;
  latest_source_timestamp: string | null;
  source_timestamp_age_seconds: number | null;
  freshness_state: IntegrityFreshnessState;
  freshness_warn_seconds: number;
  freshness_stale_seconds: number;
  freshness_unmeasurable_reason: string | null;
  frozen: boolean | null;
  frozen_state: IntegrityFrozenState;
  frozen_since_source_timestamp: string | null;
  frozen_after_observations: number | null;
  expected_constant_reason: string | null;
  derives_from: IndicatorKey | null;
  frozen_propagation_unavailable_reason: string | null;
};

export type IntegrityRow = {
  indicatorKey: IndicatorKey;
  asset: string;
  sourceVendor: string;
  computedAt: string;
  latestSourceTimestamp: string | null;
  sourceTimestampAgeSeconds: number | null;
  freshnessState: IntegrityFreshnessState;
  freshnessWarnSeconds: number;
  freshnessStaleSeconds: number;
  freshnessUnmeasurableReason: string | null;
  frozen: boolean | null;
  frozenState: IntegrityFrozenState;
  frozenSinceSourceTimestamp: string | null;
  frozenAfterObservations: number | null;
  expectedConstantReason: string | null;
  derivesFrom: IndicatorKey | null;
  frozenPropagationUnavailableReason: string | null;
};

export type IntegrityRead = {
  computedAt: string;
  selfCheckState: IntegritySelfCheckState;
  rows: IntegrityRow[];
};

// The panel polls through browser/query/cache layers, so two minutes is deliberately wider than
// normal request latency while still tight enough to expose a stuck response during the next poll.
export const INTEGRITY_SELF_CHECK_STALE_AFTER_MS = 2 * 60 * 1000;

function browserConfig(
  override?: SupabaseBrowserConfig,
): SupabaseBrowserConfig {
  const supabaseUrl = override?.supabaseUrl ?? import.meta.env.VITE_SUPABASE_URL;
  const anonKey = override?.anonKey ?? import.meta.env.VITE_SUPABASE_ANON_KEY;
  if (!supabaseUrl || !anonKey) {
    throw new Error("Supabase browser configuration is missing.");
  }
  return { supabaseUrl, anonKey };
}

export function classifyIntegritySelfCheck(
  computedAt: string,
  thresholdMs = INTEGRITY_SELF_CHECK_STALE_AFTER_MS,
): IntegritySelfCheckState {
  const ageMs = Date.now() - new Date(computedAt).getTime();
  return ageMs > thresholdMs ? "stale-self-check" : "current";
}

function rowFromRpc(row: IntegrityReadRpcRow): IntegrityRow {
  return {
    indicatorKey: row.indicator_key,
    asset: row.asset,
    sourceVendor: row.source_vendor.toUpperCase(),
    computedAt: row.computed_at,
    latestSourceTimestamp: row.latest_source_timestamp,
    sourceTimestampAgeSeconds: row.source_timestamp_age_seconds,
    freshnessState: row.freshness_state,
    freshnessWarnSeconds: row.freshness_warn_seconds,
    freshnessStaleSeconds: row.freshness_stale_seconds,
    freshnessUnmeasurableReason: row.freshness_unmeasurable_reason,
    frozen: row.frozen,
    frozenState: row.frozen_state,
    frozenSinceSourceTimestamp: row.frozen_since_source_timestamp,
    frozenAfterObservations: row.frozen_after_observations,
    expectedConstantReason: row.expected_constant_reason,
    derivesFrom: row.derives_from,
    frozenPropagationUnavailableReason:
      row.frozen_propagation_unavailable_reason,
  };
}

export function integrityReadFromRpcRows(
  rpcRows: readonly IntegrityReadRpcRow[],
): IntegrityRead {
  const computedAt = rpcRows[0]?.computed_at;
  if (!computedAt) {
    throw new Error("The integrity read did not include a computed_at timestamp.");
  }

  return {
    computedAt,
    selfCheckState: classifyIntegritySelfCheck(computedAt),
    rows: rpcRows.map(rowFromRpc),
  };
}

export async function fetchIntegrityRead(
  configOverride?: SupabaseBrowserConfig,
): Promise<IntegrityRead> {
  const config = browserConfig(configOverride);
  const query = new URL("/rest/v1/rpc/integrity_read", config.supabaseUrl);
  const response = await fetch(query, {
    method: "POST",
    headers: {
      apikey: config.anonKey,
      Authorization: `Bearer ${config.anonKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ p_registry: definitions }),
  });
  if (!response.ok) {
    throw new Error(`Supabase returned HTTP ${response.status}.`);
  }

  return integrityReadFromRpcRows((await response.json()) as IntegrityReadRpcRow[]);
}

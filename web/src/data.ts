import type { Datapoint, Provenance, UnavailableReason } from "./datapoint";
import type { IndicatorDefinition } from "./registry";

type DatapointRow = {
  indicator_key: string;
  asset: string;
  measured_on: string;
  value: number | null;
  status: "OK" | "STALE" | "UNAVAILABLE" | "ERROR";
  reason: UnavailableReason | null;
  source_vendor: string;
  endpoint: string;
  source_field: string;
  fetched_at: string;
  source_timestamp: string | null;
};

function provenanceFromRow(row: DatapointRow): Provenance {
  return {
    indicatorKey: row.indicator_key,
    asset: row.asset,
    measuredOn: row.measured_on,
    sourceVendor: row.source_vendor,
    endpoint: row.endpoint,
    sourceField: row.source_field,
    fetchedAt: row.fetched_at,
    sourceTimestamp: row.source_timestamp,
  };
}

export function unavailableDatapoint(
  definition: IndicatorDefinition,
  reason: UnavailableReason,
): Extract<Datapoint, { status: "UNAVAILABLE" }> {
  return {
    status: "UNAVAILABLE",
    reason,
    indicatorKey: definition.key,
    asset: "BTC",
    measuredOn: "BTC",
    sourceVendor: definition.vendor.toUpperCase(),
    endpoint: definition.endpoint,
    sourceField: definition.source_field,
    fetchedAt: null,
    sourceTimestamp: null,
  };
}

export function errorDatapoint(
  definition: IndicatorDefinition,
  detail: string,
): Datapoint {
  return {
    ...unavailableDatapoint(definition, "FETCH_FAILED"),
    status: "ERROR",
    detail,
  };
}

function rowToDatapoint(row: DatapointRow): Datapoint {
  const provenance = provenanceFromRow(row);

  switch (row.status) {
    case "OK":
    case "STALE":
      if (typeof row.value !== "number") {
        return {
          ...provenance,
          status: "ERROR",
          reason: "FETCH_FAILED",
          detail: `The database returned ${row.status} without a numeric value.`,
        };
      }
      if (!row.source_timestamp) {
        return {
          ...provenance,
          status: "ERROR",
          reason: "FETCH_FAILED",
          detail: `The database returned ${row.status} without a source timestamp.`,
        };
      }
      return {
        ...provenance,
        status: row.status,
        value: row.value,
        sourceTimestamp: row.source_timestamp,
      };
    case "UNAVAILABLE":
      return {
        ...provenance,
        status: "UNAVAILABLE",
        reason: row.reason ?? "FETCH_FAILED",
      };
    case "ERROR":
      return {
        ...provenance,
        status: "ERROR",
        reason: row.reason ?? "FETCH_FAILED",
        detail: "The ingestion pipeline recorded an error for this datapoint.",
      };
  }
}

export function applyFreshness(
  datapoint: Datapoint,
  staleAfterSeconds: number,
  now: Date,
): Datapoint {
  if (datapoint.status !== "OK" && datapoint.status !== "STALE") {
    return datapoint;
  }

  const publishedAt = datapoint.publishedAt ?? datapoint.sourceTimestamp;
  const ageSeconds = (now.getTime() - new Date(publishedAt).getTime()) / 1000;
  if (datapoint.status === "OK" && ageSeconds > staleAfterSeconds) {
    return { ...datapoint, status: "STALE" };
  }
  return datapoint;
}

export async function fetchLatestDatapoint(
  definition: IndicatorDefinition,
): Promise<Datapoint> {
  const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
  const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;
  if (!supabaseUrl || !anonKey) {
    throw new Error("Supabase browser configuration is missing.");
  }

  const query = new URL("/rest/v1/datapoints_read", supabaseUrl);
  query.searchParams.set("select", "*");
  query.searchParams.set("indicator_key", `eq.${definition.key}`);
  query.searchParams.set("asset", "eq.BTC");
  query.searchParams.set("order", "fetched_at.desc");
  query.searchParams.set("limit", "1");

  const response = await fetch(query, {
    headers: {
      apikey: anonKey,
      Authorization: `Bearer ${anonKey}`,
    },
  });
  if (!response.ok) {
    throw new Error(`Supabase returned HTTP ${response.status}.`);
  }

  const rows = (await response.json()) as DatapointRow[];
  return rows[0]
    ? rowToDatapoint(rows[0])
    : unavailableDatapoint(definition, "NOT_FETCHED");
}

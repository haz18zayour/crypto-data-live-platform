import type { Datapoint, Provenance, UnavailableReason } from "./datapoint";
import type { Corroboration, VenueDatapoint } from "./corroboration";
import { BOARD_ASSETS, buildBoard, type BoardModel } from "./board";
import { definitions, type IndicatorDefinition } from "./registry";

type DatapointRow = {
  id: number;
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
    sourceVendor: row.source_vendor.toUpperCase(),
    endpoint: row.endpoint,
    sourceField: row.source_field,
    fetchedAt: row.fetched_at,
    sourceTimestamp: row.source_timestamp,
  };
}

type CorroborationRow = {
  datapoint_a_id: number;
  datapoint_b_id: number | null;
  divergence_bps: number | null;
  tolerance_bps_at_write: number | null;
  status: "CORROBORATED" | "DIVERGED" | "NOT_CORROBORATED";
  reason: string | null;
};

type SupabaseBrowserConfig = {
  supabaseUrl: string;
  anonKey: string;
};

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

async function fetchRows<Row>(
  table: string,
  params: URLSearchParams,
  config: SupabaseBrowserConfig,
): Promise<Row[]> {
  const query = new URL(`/rest/v1/${table}`, config.supabaseUrl);
  query.search = params.toString();
  const response = await fetch(query, {
    headers: {
      apikey: config.anonKey,
      Authorization: `Bearer ${config.anonKey}`,
    },
  });
  if (!response.ok) {
    throw new Error(`Supabase returned HTTP ${response.status}.`);
  }
  return (await response.json()) as Row[];
}

function availableDatapoint(row: DatapointRow): VenueDatapoint {
  const datapoint = rowToDatapoint(row);
  if (datapoint.status !== "OK" && datapoint.status !== "STALE") {
    throw new Error("A corroboration venue has no available numeric value.");
  }
  return datapoint;
}

export async function fetchLatestCorroboration(
  definition: IndicatorDefinition,
  configOverride?: SupabaseBrowserConfig,
): Promise<Corroboration> {
  const config = browserConfig(configOverride);
  const datapointParams = new URLSearchParams({
    select: "*",
    indicator_key: `eq.${definition.key}`,
    asset: "eq.BTC",
    source_vendor: `eq.${definition.vendor}`,
    order: "fetched_at.desc",
    limit: "1",
  });
  const [anchorRow] = await fetchRows<DatapointRow>(
    "datapoints_read",
    datapointParams,
    config,
  );
  if (!anchorRow) {
    throw new Error("No sourced value is available for this indicator.");
  }
  const anchor = availableDatapoint(anchorRow);

  if (definition.uncorroborated) {
    return {
      status: "UNCORROBORATED",
      datapoint: anchor,
      reason: definition.uncorroborated.note,
    };
  }

  const comparisonParams = new URLSearchParams({
    select: "*",
    or: `(datapoint_a_id.eq.${anchorRow.id},datapoint_b_id.eq.${anchorRow.id})`,
    order: "id.desc",
    limit: "1",
  });
  const [comparison] = await fetchRows<CorroborationRow>(
    "corroborations_read",
    comparisonParams,
    config,
  );
  if (!comparison) {
    throw new Error("The latest sourced value has no corroboration record.");
  }
  if (comparison.status === "NOT_CORROBORATED") {
    return {
      status: "NOT_CORROBORATED",
      datapoint: anchor,
      reason: `Second venue did not provide a comparable bar (${comparison.reason ?? "reason unavailable"}).`,
    };
  }

  const peerId =
    comparison.datapoint_a_id === anchorRow.id
      ? comparison.datapoint_b_id
      : comparison.datapoint_a_id;
  if (
    peerId === null ||
    comparison.divergence_bps === null ||
    comparison.tolerance_bps_at_write === null
  ) {
    throw new Error("The stored comparison is missing its peer or measured values.");
  }

  const peerParams = new URLSearchParams({
    select: "*",
    id: `eq.${peerId}`,
    limit: "1",
  });
  const [peerRow] = await fetchRows<DatapointRow>(
    "datapoints_read",
    peerParams,
    config,
  );
  if (!peerRow) {
    throw new Error("The corroborating venue value is unavailable.");
  }

  return {
    status: comparison.status,
    divergenceBps: comparison.divergence_bps,
    toleranceBpsAtWrite: comparison.tolerance_bps_at_write,
    datapoints: [anchor, availableDatapoint(peerRow)],
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

// One request for the whole board: board_read already holds the latest row per cell, so the
// page never fetches per cell. The cells themselves come from the registry, not the response.
export async function fetchBoard(now: Date): Promise<BoardModel> {
  const rows = await fetchRows<DatapointRow>(
    "board_read",
    new URLSearchParams({ select: "*" }),
    browserConfig(),
  );
  const staleAfter = new Map(
    definitions.map((definition) => [
      definition.key,
      definition.freshness_stale_seconds,
    ]),
  );
  const datapoints = rows.map((row) => {
    const datapoint = rowToDatapoint(row);
    const staleAfterSeconds = staleAfter.get(row.indicator_key);
    return staleAfterSeconds === undefined
      ? datapoint
      : applyFreshness(datapoint, staleAfterSeconds, now);
  });
  return buildBoard(definitions, datapoints, BOARD_ASSETS);
}

export async function fetchLatestDatapoint(
  definition: IndicatorDefinition,
): Promise<Datapoint> {
  const { supabaseUrl, anonKey } = browserConfig();

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

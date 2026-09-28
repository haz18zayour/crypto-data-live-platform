export type HistoryPoint = {
  id: number;
  indicatorKey: string;
  asset: string;
  measuredOn: string;
  value: number;
  status: "OK" | "STALE";
  sourceVendor: string;
  endpoint: string;
  sourceField: string;
  fetchedAt: string;
  sourceTimestamp: string;
  referencePeriod: string | null;
  publishedAt: string | null;
  origin: "live" | "backfill";
};

type HistoryPointRow = {
  id: number;
  indicator_key: string;
  asset: string;
  measured_on: string;
  value: number;
  status: "OK" | "STALE";
  source_vendor: string;
  endpoint: string;
  source_field: string;
  fetched_at: string;
  source_timestamp: string;
  reference_period: string | null;
  published_at: string | null;
  origin: "live" | "backfill";
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

function rowToHistoryPoint(row: HistoryPointRow): HistoryPoint {
  return {
    id: row.id,
    indicatorKey: row.indicator_key,
    asset: row.asset,
    measuredOn: row.measured_on,
    value: row.value,
    status: row.status,
    sourceVendor: row.source_vendor,
    endpoint: row.endpoint,
    sourceField: row.source_field,
    fetchedAt: row.fetched_at,
    sourceTimestamp: row.source_timestamp,
    referencePeriod: row.reference_period,
    publishedAt: row.published_at,
    origin: row.origin,
  };
}

export async function fetchHistory(
  indicatorKey: string,
  asset: string,
  sourceVendor: string,
  pointLimit: number,
  configOverride?: SupabaseBrowserConfig,
): Promise<HistoryPoint[]> {
  const config = browserConfig(configOverride);
  const query = new URL("/rest/v1/rpc/history_read", config.supabaseUrl);
  const response = await fetch(query, {
    method: "POST",
    headers: {
      apikey: config.anonKey,
      Authorization: `Bearer ${config.anonKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      p_indicator_key: indicatorKey,
      p_asset: asset,
      p_source_vendor: sourceVendor,
      p_point_limit: pointLimit,
    }),
  });
  if (!response.ok) {
    throw new Error(`Supabase returned HTTP ${response.status}.`);
  }

  const rows = (await response.json()) as HistoryPointRow[];
  return rows.map(rowToHistoryPoint);
}

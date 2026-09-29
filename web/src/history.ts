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

// The RPC caps by count, not time, so a dense 5-minute series reaches back less far than a daily
// one. That is why the sparkline prints the window its points actually cover.
export const HISTORY_POINT_LIMIT = 500;

const DAY_MS = 86_400_000;
const MONTHLY_GAP_MS = 28 * DAY_MS;

export type HistorySufficiency =
  | { sufficient: true; points: HistoryPoint[] }
  | { sufficient: false; count: number; since: string | null };

function timeOf(point: HistoryPoint): number {
  return Date.parse(point.sourceTimestamp);
}

function medianGap(points: readonly HistoryPoint[]): number {
  const gaps = points
    .slice(1)
    .map((point, index) => timeOf(point) - timeOf(points[index]))
    .sort((a, b) => a - b);
  return gaps.length === 0 ? 0 : gaps[Math.floor(gaps.length / 2)];
}

// The threshold is tiered by the cadence the points themselves show, since the registry's
// polling interval is daily even for monthly FRED series. With fewer than two points the cadence
// is unknowable, but both tiers already call that insufficient.
export function minimumPointsFor(points: readonly HistoryPoint[]): number {
  return medianGap(points) >= MONTHLY_GAP_MS ? 4 : 7;
}

export function historySufficiency(
  history: readonly HistoryPoint[],
): HistorySufficiency {
  const points = [...history].sort((a, b) => timeOf(a) - timeOf(b));
  const distinctValues = new Set(points.map((point) => point.value)).size;
  if (points.length >= minimumPointsFor(points) && distinctValues >= 2) {
    return { sufficient: true, points };
  }
  return {
    sufficient: false,
    count: points.length,
    since: points[0]?.sourceTimestamp ?? null,
  };
}

export function formatWindow(fromTimestamp: string, toTimestamp: string): string {
  const span = Date.parse(toTimestamp) - Date.parse(fromTimestamp);
  if (span < 2 * DAY_MS) return `${Math.max(1, Math.round(span / 3_600_000))}h`;
  const days = Math.round(span / DAY_MS);
  return days < 730 ? `${days}d` : `${(days / 365.25).toFixed(1)}y`;
}

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

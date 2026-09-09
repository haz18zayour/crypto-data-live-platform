import { useQuery } from "@tanstack/react-query";

import { DatapointValue } from "./DatapointValue";
import {
  applyFreshness,
  errorDatapoint,
  fetchLatestDatapoint,
} from "./data";
import { getIndicatorDefinition } from "./registry";

const definition = getIndicatorDefinition("btc_daily_close");

export function App() {
  const query = useQuery({
    queryKey: [definition.key, "BTC"],
    queryFn: () => fetchLatestDatapoint(definition),
    refetchInterval: 60_000,
  });

  if (query.isPending) {
    return <p className="loading">Loading the latest sourced value…</p>;
  }

  const now = new Date();
  const datapoint = query.isError
    ? errorDatapoint(
        definition,
        query.error instanceof Error
          ? query.error.message
          : "The latest datapoint could not be loaded.",
      )
    : applyFreshness(query.data, definition.freshness_stale_seconds, now);

  return (
    <main>
      <p className="eyebrow">Market data spine</p>
      <h1>BTC daily close</h1>
      <p className="lede">One value, with its freshness and source attached.</p>
      <DatapointValue datapoint={datapoint} now={now} />
    </main>
  );
}

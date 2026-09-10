import { useQuery } from "@tanstack/react-query";

import { CorroborationPanel } from "./CorroborationPanel";
import { fetchLatestCorroboration } from "./data";
import { getIndicatorDefinition } from "./registry";

const definition = getIndicatorDefinition("btc_daily_close");

export function App() {
  const query = useQuery({
    queryKey: [definition.key, "BTC", "corroboration"],
    queryFn: () => fetchLatestCorroboration(definition),
    refetchInterval: 60_000,
  });

  if (query.isPending) {
    return <p className="loading">Loading the latest sourced value…</p>;
  }

  return (
    <main>
      <p className="eyebrow">Market data spine</p>
      <h1>BTC daily close</h1>
      <p className="lede">Independent venue values, shown without reconciliation.</p>
      {query.isError ? (
        <article className="corroboration corroboration--error" role="alert">
          <strong>Corroboration unavailable</strong>
          <p>
            {query.error instanceof Error
              ? query.error.message
              : "The latest corroboration could not be loaded."}
          </p>
        </article>
      ) : (
        <CorroborationPanel corroboration={query.data} />
      )}
    </main>
  );
}

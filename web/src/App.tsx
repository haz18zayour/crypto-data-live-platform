import { useQuery } from "@tanstack/react-query";

import { BoardMatrix } from "./BoardMatrix";
import { CorroborationPanel } from "./CorroborationPanel";
import { CoverageHeadline } from "./CoverageHeadline";
import { fetchBoard, fetchLatestCorroboration } from "./data";
import { getIndicatorDefinition } from "./registry";

const definition = getIndicatorDefinition("btc_daily_close");

export function App() {
  const board = useQuery({
    queryKey: ["board_read"],
    queryFn: () => fetchBoard(new Date()),
    refetchInterval: 60_000,
  });
  const query = useQuery({
    queryKey: [definition.key, "BTC", "corroboration"],
    queryFn: () => fetchLatestCorroboration(definition),
    refetchInterval: 60_000,
  });

  return (
    <main>
      <p className="eyebrow">Market data spine</p>
      <h1>Data completeness</h1>
      {board.isPending ? (
        <p>Loading the board…</p>
      ) : board.isError ? (
        <article className="corroboration corroboration--error" role="alert">
          <strong>Board unavailable</strong>
          <p>
            {board.error instanceof Error
              ? board.error.message
              : "The board could not be loaded."}
          </p>
        </article>
      ) : (
        <>
          <CoverageHeadline board={board.data} />
          <BoardMatrix board={board.data} />
        </>
      )}
      <h2>BTC daily close</h2>
      <p className="lede">Independent venue values, shown without reconciliation.</p>
      {query.isPending ? (
        <p>Loading the latest sourced value…</p>
      ) : query.isError ? (
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

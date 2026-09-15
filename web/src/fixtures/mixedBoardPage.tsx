import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { BoardMatrix } from "../BoardMatrix";
import { CoverageHeadline } from "../CoverageHeadline";
import "../styles.css";
import { mixedBoard } from "./mixedBoard";

// The adversarial case as a page, for the real-browser checks in scripts/capture-board.mjs and
// board.browser.test.ts. The clock is pinned to the fixture's so the stale age never drifts.
const NOW = new Date("2026-09-14T00:01:00Z");

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <main>
      <p className="eyebrow">Mixed board fixture · not live data</p>
      <h1>Data completeness</h1>
      <CoverageHeadline board={mixedBoard} />
      <BoardMatrix board={mixedBoard} now={NOW} />
    </main>
  </StrictMode>,
);

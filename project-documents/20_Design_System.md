# 20 · Design system

Design intent for the dashboard. Written 2026-09-09 from the owner's framing: *"I should
always be able to see data completeness."* That sentence changes what the page **is**, so it
belongs here rather than in a story.

---

## The organising principle

**The page's primary object is coverage, not values.**

Most dashboards show numbers and let absence hide as a blank cell. This one inverts that: the
first thing visible is *how much of the board is real right now*, and the numbers are what you
drill into. A value you cannot trust is worse than a value you know is missing, so missingness
is promoted to a first-class citizen of the layout.

Concretely, the top of the page answers one question before anything else:

```
34 of 41 indicators OK   ·   3 stale   ·   4 unavailable
                                            2 not definable · 1 paywalled · 1 fetch failed
```

That line is the product. Everything below it is detail.

## The completeness matrix

The core view is a grid — **assets across, indicators down** — where every cell carries a state,
never an empty space:

| | BTC | ETH | SOL | BNB |
|---|---|---|---|---|
| daily close | ● | ● | ● | ● |
| RSI(14) | ● | ● | ● | ● |
| funding | ● | ● | ● | ○ *no venue* |
| MVRV | ● | ● | ⊘ *not definable* | ● |
| exchange flow | ● | ● | ⊘ | ○ *no metric* |
| M2 | ◐ *69d lag* | — | — | — |

Reading the column tells you how complete an asset is. Reading the row tells you how complete an
indicator is. **Neither ever renders as a blank.**

## The five states, and why each looks different

| State | Reads as | Means | Feels |
|---|---|---|---|
| `OK` | the value | fetched, fresh, native to this asset | normal |
| `STALE` | value + age, visibly dimmed | real but past its freshness budget | uneasy |
| `UNAVAILABLE / NOT_DEFINABLE` | `n/a for this chain` | has no meaning here and never will (SOPR on Solana) | **settled, not alarming** |
| `UNAVAILABLE / PAYWALLED` | `requires paid tier` | exists, we lack credentials | actionable |
| `ERROR / FETCH_FAILED` | `unavailable` + reason | should have arrived, didn't | **alarming** |

The distinction that matters most: **`NOT_DEFINABLE` is not a gap.** SOL has no MVRV because
Solana is account-based and has no UTXO to timestamp — that is a fact about the chain, not a
failure of ours, and it must not nag. `FETCH_FAILED` on the same cell means something broke and
should draw the eye immediately. Rendering both as an empty cell destroys the only information
the owner actually needs.

## Non-negotiables

Carried from `11_Data_Model.md`; these are correctness, not taste.

1. **Never render `0` for absence.** An em dash and a reason, always.
2. **A stale value is shown, never shown as current.** Age on the face of it.
3. **Provenance is visible without a click** — vendor, and the source timestamp.
4. **Lagged series show both dates.** M2's July figure reads as July, with its publication date.
   Measured: 69 days behind.
5. **No "last known good" fallback** that quietly presents an old number as fresh.

## Visual direction

Apple-grade: restrained, dense, legible. Reference `open-design:apple-hig` (Apple HIG as 14
skills), with `taste-skill`, `color-expert` and `wise-ui-skill` for typography, colour and
tokens; `design-review` for the audit pass.

- **Dense but calm.** Forty-eight cells on one screen without feeling like a trading
  terminal. Generous type scale, tight vertical rhythm, few rules and borders.
- **Colour carries meaning, but never alone.** Colour is reserved for status, and values are
  neutral: if a cell is coloured, something is wrong or notable. Colour is never the sole
  status channel, though. Relying on hue alone fails WCAG 1.4.1 (Use of Colour, Level A) and
  leaves anyone who cannot tell the hues apart unable to read the board.
- **The glyph-and-word rule.** Every state carries a glyph and a word as well as its hue, and
  the glyph and the word each separate all five states on their own:

  | State | Glyph | Word |
  |---|---|---|
  | `OK` | ● | OK |
  | `STALE` | ◐ | Stale |
  | `UNAVAILABLE / NOT_DEFINABLE` | ⊘ | n/a |
  | `UNAVAILABLE / PAYWALLED` | ◇ | Requires paid tier |
  | `ERROR / FETCH_FAILED` | ✕ | Unavailable |
  | `UNAVAILABLE / NOT_FETCHED` (no row) | ! | Not fetched |

  Greyscale is the test. If two states look the same with colour removed, the fix is a
  different glyph or a different word, not a stronger hue. Every status colour also meets
  WCAG AA contrast (4.5:1 for text) in both themes, checked with axe-core in a real browser.
- **No decoration that could be mistaken for data**: no sparkline flourishes on values that
  have no history, no gauges implying precision the source does not have.
- Dark and light both first-class; the viewer's system setting decides.
- **The matrix stays a native `<table>`.** Never `display: grid` on the table or its rows and
  cells, which strips row and column semantics from assistive technology. On a narrow screen
  the matrix scrolls inside its own container; the page body never scrolls sideways.

**Implementation note:** every design skill listed above is Claude-only, so the design-led
stories of PRD-005 (US-507, US-512) set `agent: claude` in front-matter. Codex then verifies,
preserving the different-vendor rule. `scripts/capture-board.mjs` photographs the board in
headless Chromium and checks its table semantics and axe-core contrast.

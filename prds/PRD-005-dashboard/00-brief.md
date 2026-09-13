# PRD-005 · The dashboard

**In one to three sentences:** Put the 45 persisted cells on one screen, organised so that
**data completeness is the first thing visible** and any individual number is a drill-down.
Apple-grade: restrained, dense, legible.

**Depends on:** PRD-004.

**Roughly:** 7–8 stories.

---

## The organising principle, in the owner's words

> *"I should always be able to see data completeness."*

That sentence changes what the page **is**. Most dashboards show numbers and let absence hide in
a blank cell. This one inverts it: the first thing on screen is **how much of the board is real
right now**, and the values are what you drill into. Full treatment in
`project-documents/20_Design_System.md`.

The top line answers one question before anything else:

```
44 of 45 indicators OK · 0 stale · 1 error
```

Then a matrix — assets across, indicators down — where **no cell is ever blank**.

## What the data actually looks like now

Real, persisted, as of 2026-09-13:

| | BTC | ETH | SOL | BNB |
|---|---|---|---|---|
| rsi | 55.08 | 63.83 | 57.22 | 58.84 |
| ema_20 / 50 / 200 | ✓ | ✓ | ✓ | ✓ |
| bollinger upper/mid/lower | ✓ | ✓ | ✓ | ✓ |
| atr, macd, stochrsi, obv | ✓ | ✓ | ✓ | ✓ |
| daily_close | ✓ | — | — | — |

`daily_close` is BTC-only by declaration, so the matrix already has a genuine `NOT_DEFINABLE`
cell on day one — the state that must read as *settled*, not alarming.

## The distinction the design lives or dies on

| State | Reads as | Feels |
|---|---|---|
| `OK` | the value | normal |
| `STALE` | value + age, dimmed | uneasy |
| `UNAVAILABLE / NOT_DEFINABLE` | `n/a for this chain` | **settled** |
| `UNAVAILABLE / PAYWALLED` | `requires paid tier` | actionable |
| `ERROR / FETCH_FAILED` | `unavailable` + reason | **alarming** |

**`NOT_DEFINABLE` is not a gap.** SOL has no MVRV because Solana is account-based — a fact about
the chain, not a failure of ours. `FETCH_FAILED` in the same cell means something broke. Render
both as an empty cell and the only information the owner needs is destroyed.

## Implementation constraint that is easy to miss

**Every design skill is Claude-only** — `open-design:apple-hig` (Apple HIG as 14 skills),
`taste-skill`, `color-expert`, `design-review`, `wise-ui-skill`. Codex cannot invoke any of
them. **Stories in this PRD must set `agent: claude` in front-matter**; Codex then verifies, so
the different-vendor rule holds with the roles swapped.

A design story routed the default way gets none of those skills and produces a competent,
generic page.

## Explicitly NOT in this PRD

- No deployment — that is PRD-011. Localhost is the target.
- No new indicators, no new sources.
- No charts or history — PRD-009.
- No composite, score, signal or ranking. Permanent.
- No "last known good" fallback, no averaging of corroborated venues, no blank cells.

## The adversarial case

**Force a mixed board — `OK`, `STALE`, `NOT_DEFINABLE`, `FETCH_FAILED` simultaneously — and
read completeness at a glance.** If the four states are not instantly distinguishable, the page
has failed at the only thing it exists to do.

## Phase checklist

- [x] `00-brief.md`
- [ ] `10-research.md`
- [ ] `20-decisions.yaml` — **GATE G1**
- [ ] `30-spec.md`
- [ ] `40-stories/*.md` — every one with `agent: claude`
- [ ] `uf compile PRD-005-dashboard`
- [ ] `uf run`
- [ ] merge to `main`
- [ ] `uf learn`

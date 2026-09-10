# PRD-003 · Cross-source corroboration

**In one to three sentences:** Fetch the same quantity from two independent venues, compare
them, and treat disagreement as a **finding** rather than something to resolve. This is the
only defence in the roadmap that catches a wrong number nobody predicted — every other check
enforces a failure mode someone thought of in advance.

**Depends on:** PRD-002.

**Roughly:** 6–7 stories.

---

## The case for it, measured on this project

US-006 passed **6/6 criteria, verified independently by a different vendor**, and was still
storing the wrong number: **78,834.1** instead of **79,111.8**. OKX's default `bar=1D` is
aligned to UTC+8, so we had a Hong Kong day close labelled as a UTC one. No gate caught it. A
human read a timestamp.

**Corroboration would have caught it automatically, on the first run.** Measured 2026-09-10,
OKX `BTC-USDT` 1Dutc against Coinbase `BTC-USD`, 59 overlapping UTC days:

| | basis points |
|---|---|
| median divergence | **7.1** |
| p90 | **10.8** |
| **max over 59 days** | **13.8** |
| **the `bar=1D` bug** | **35.2** |

The defect is **2.5× the worst honest disagreement**. There is a wide, empty gap between normal
venue basis and a real error, and a threshold lives in it.

Note what the 7.1 bps median is made of: it is **not** pure venue disagreement. `BTC-USDT` and
`BTC-USD` are different instruments, so the USDT peg basis is inside that number. That is an
argument for a per-pair threshold, not a global one.

## What "corroboration" must not become

The tempting implementation is to **resolve** the disagreement — average the two, or prefer the
primary venue. That discards the only signal that something is wrong and emits a confident
number, which is precisely the failure this product exists to eliminate.

**Disagreement is the output.** It reaches the stored row and the page.

## Scope

- A second venue for the indicators where one genuinely exists (spot close first).
- A per-indicator tolerance in the registry, **set from observed spreads**, never guessed.
- Divergence beyond tolerance is visible in the data and on the page.
- Metrics with no second source (Coin Metrics MVRV) are marked **uncorroborated**, and that
  absence is itself visible rather than implied.

## Explicitly NOT in this PRD

- No averaging, no "primary wins", no silent reconciliation of any kind.
- No new indicator families — corroborating what exists, not adding breadth.
- No third venue. Two is enough to detect disagreement; three is a voting scheme, and voting
  is how you end up resolving instead of reporting.
- No automatic threshold tuning. A tolerance changes only by a committed edit with the
  measurement that justifies it.
- No UI redesign — PRD-005 owns the dashboard.

## The adversarial case this PRD must pass

Per `25_PRD_Acceptance_Protocol.md`: **feed two venues that disagree beyond tolerance and show
the divergence reaching the page** — not averaged, not hidden, not silently preferring one.

## Phase checklist

- [x] `00-brief.md`
- [ ] `10-research.md`
- [ ] `20-decisions.yaml` — **GATE G1**
- [ ] `30-spec.md`
- [ ] `40-stories/*.md`
- [ ] `uf compile PRD-003-corroboration`
- [ ] `uf run`
- [ ] merge to `main` (standing instruction)
- [ ] `uf learn`

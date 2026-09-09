# PRD-002 · Determinism and contract harness

**In one to three sentences:** Build the test machinery that every later indicator inherits,
before there are twenty of them to retrofit. Three guarantees: an indicator computed from the
same bars always produces the same number; a vendor that silently reshapes its response fails
loudly instead of corrupting data; and a fetch that dies part-way through pagination is an
error rather than a shorter-but-plausible series.

**Depends on:** PRD-001.

**Roughly:** 6–8 stories.

---

## Why this exists, before more indicators

Every defect found in PRD-001 came from **a check nobody had written**, not from an agent
ignoring one. Four of six rejections were gaps in the spec. And the worst one got through
entirely: US-006 passed **6/6**, verified by a different vendor, while storing a Hong Kong day
close as a UTC one — caught only because a human read a timestamp.

Retrofitting this harness onto twenty indicators costs twenty times what building it now does,
and the ones added in between would go in unprotected.

## The three guarantees

**1. Determinism.** The prior system's ATR modifier, Bollinger squeeze quantile and OBV
normaliser were computed over "whatever `ohlcv_cache` currently holds, which grows forever from
a 500-bar seed". Its own post-mortem: *"Same market, different score."* An indicator must be a
pure function of `(bars, window)`, pinned by golden files, so a value cannot depend on how long
a process has been running.

**2. Vendor contract.** Four sources broke or gated in nine months on the prior system
(Reddit, LunarCrush, CryptoPanic, CryptoCompare), and CCData retired its free tier outright in
May 2026. Vendor churn is a design assumption here, not an emergency. Recorded-cassette tests
must fail loudly when a response shape changes, rather than letting a `KeyError` become a
`0.0`.

**3. Partial-failure integrity.** From `research/R9`, learned from `ai-hedge-fund`'s
`test_mid_walk_*` cases: a paginated fetch that fails on page 3 of 5 returns a **shorter but
structurally valid** series, which then produces a wrong indicator over an incomplete window.
Nothing errors. This is a hazard we would not have thought of unaided.

## What this PRD explicitly does NOT do

- No new indicators, no new assets, no new vendors. It hardens what exists.
- No cross-source corroboration — that is PRD-003, and it is a different mechanism
  (disagreement between vendors, not correctness of one).
- No UI work.
- No changes to the `datapoints` schema unless a guarantee genuinely requires one.

## Phase checklist

- [x] `00-brief.md`
- [ ] `10-research.md`
- [ ] `20-decisions.yaml` — **GATE G1** for this PRD
- [ ] `30-spec.md`
- [ ] `40-stories/*.md`
- [ ] `uf compile PRD-002-harness`
- [ ] **GATE G2** — approve the estimate
- [ ] `uf run`
- [ ] merge to `main` (standing instruction; blast-radius review first if the diff warrants it)
- [ ] `uf learn`

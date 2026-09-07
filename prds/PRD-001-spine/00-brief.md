# PRD-001 · Spine — reachability, registry, provenance schema, one live indicator

**In one to three sentences:** Prove the entire data path end to end with a *single* indicator
— fetch, explicit status, full provenance, Postgres, a deployed page behind Cloudflare Access,
freshness visible on the value itself, and a dead-man's-switch that alerts on pipeline
silence. Before any of that, settle the one genuinely open architectural question by
measurement: which venue endpoints are reachable from the target compute, since Binance
returns HTTP 451 to US IPs and that single fact is what forced the prior system onto a
self-hosted runner that later died silently.

**Depends on:** nothing.

**Roughly:** 7–9 stories.

---

## Why this PRD is shaped this way

It is deliberately **narrow and vertical**, not broad and horizontal. One indicator, all the
way through. The prior system had 25 indicators and no way to tell a right number from a
wrong one; breadth was never the missing thing.

Three things must be true at the end, and nothing else matters:

1. **The compute location is decided by evidence.** A recorded table of HTTP statuses per
   venue per endpoint, observed from the real target runner — not from Lebanon, where
   everything currently responds, and not from a vendor's documentation.
2. **A wrong number cannot look like a right one.** `UNAVAILABLE` is not `0`. A value carries
   its source, its endpoint *and field*, when we fetched it, and when the source says it is
   as-of. The `asset_match` CHECK constraint makes displaying one asset's data as another's a
   database error rather than a silent proxy.
3. **Silence is loud.** If the pipeline stops, something that is not the pipeline says so.

## What this PRD explicitly does NOT do

- No second indicator. No panels. No charts. No technical indicators, no TA-Lib.
- No backfill or history — one current value is enough to prove the path.
- No layout or visual design work beyond what is needed to render one value honestly.
- No frozen-value detection, no nightly assertion suite (PRD-002 and PRD-009).

## Phase checklist

- [x] `00-brief.md`
- [ ] `10-research.md` — `uf research PRD-001-spine`
- [ ] `20-decisions.yaml` — **GATE G1** for this PRD
- [ ] `30-spec.md`
- [ ] `40-stories/*.md`
- [ ] `uf compile PRD-001-spine`
- [ ] **GATE G2** — approve the estimate
- [ ] `uf run`
- [ ] **GATE G4** — the diff will touch `**/migrations/**` and `.github/workflows/**`
- [ ] `uf learn`

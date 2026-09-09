---
title: Spine — reachability, registry, provenance schema, one live indicator
branch: feat/prd-001-spine
assumptions:
  - claim: GitHub-hosted runners can reach OKX, Coinbase and Coin Metrics without geo-blocking.
    tripwire: The reachability spike returns 451 or 403 for any required venue — reopens G1 and switches compute to a stateless Fly.io fra machine, never a resident self-hosted runner.
    acceptedBy: default
  - claim: Supabase free tier is sufficient and daily writes prevent the 7-day inactivity pause.
    tripwire: Database exceeds 400 MB, any egress warning, or the project pauses once.
    acceptedBy: default
  - claim: Cloudflare Access free tier covers a single user.
    tripwire: Access requires a paid plan at signup — UNVERIFIED, confirm in a browser during setup.
    acceptedBy: default
  - claim: OKX confirm="1" reliably marks a final candle.
    tripwire: Any candle with confirm="1" is later observed to change value.
    acceptedBy: default
---

# Spine — reachability, registry, provenance schema, one live indicator

## What this delivers

One indicator — **BTC daily close from OKX** — travelling the complete path: fetch → explicit
status → full provenance → Postgres → a page deployed behind Cloudflare Access → freshness
visible on the value itself → an alert when the pipeline goes silent.

Plus the answer to the one open architectural question, obtained by measurement rather than
assumption: **which venues are reachable from the compute that will actually run ingestion.**

## Why (from research)

See `10-research.md`. Three findings drive this spec:

1. **§1 / R7 §C1** — the prior system's 24h silent outage traces to `Binance → 451 from US
   IPs → self-hosted runner → a supervised process that exited 0`. The compute location
   therefore cannot be assumed; US-001 measures it before anything is built on the answer.
2. **§2.1** — measured live: OKX is the only venue that flags a closed candle (`confirm`), and
   the newest daily candle genuinely returns `"0"`. Coinbase and Kraken return the forming
   bucket unmarked.
3. **§3 / R5** — `UNAVAILABLE` must not be representable as a number, and
   `measured_on != asset` must be a database error rather than a discipline problem.

## Approach

Thin vertical slice: one indicator, full depth. Rejected — building the schema first (a
schema with no value flowing through it is unfalsifiable, which is exactly how the prior
system's `NULL`-ambiguity survived for months), and starting with four assets (multiplies
surface before anything is proven). See `20-decisions.yaml`.

## Data model changes

**Blast radius — needs gate G4 before merge.**

```sql
CREATE TYPE datapoint_status AS ENUM ('OK','STALE','UNAVAILABLE','ERROR');
CREATE TYPE unavailable_reason AS ENUM ('NOT_DEFINABLE','PAYWALLED','FETCH_FAILED','NOT_FETCHED');

CREATE TABLE datapoints (
  id               bigserial PRIMARY KEY,
  indicator_key    text NOT NULL,
  asset            text NOT NULL,          -- what we DISPLAY it as
  measured_on      text NOT NULL,          -- what it was ACTUALLY measured on
  value            double precision,       -- NULL unless status IN ('OK','STALE')
  status           datapoint_status NOT NULL,
  reason           unavailable_reason,
  source_vendor    text NOT NULL,
  endpoint         text NOT NULL,
  source_field     text NOT NULL,          -- F11: WHICH FIELD produced the value
  fetched_at       timestamptz NOT NULL,
  source_timestamp timestamptz,
  CONSTRAINT asset_match     CHECK (status <> 'OK' OR measured_on = asset),
  CONSTRAINT value_iff_ok    CHECK ((status IN ('OK','STALE')) = (value IS NOT NULL)),
  CONSTRAINT reason_required CHECK ((status IN ('UNAVAILABLE','ERROR')) = (reason IS NOT NULL))
);
```

`source_field` exists because F11 (funding read from `premiumIndex.lastFundingRate` rather
than the settled series) is invisible if only the endpoint is recorded.

## Out of scope

Carried from `20-decisions.yaml`: no second indicator; no TA-Lib or technical indicators; no
backfill or charts; no frozen-value detection or nightly assertions; no golden-file/cassette
harness (PRD-002); no layout work beyond rendering one value honestly; **no composite, score,
signal or ranking, permanently**; no alerts of market content.

## The reachability spike — done, and deliberately not a tracked story

The spike ran and answered its question. Evidence: GitHub Actions run `34199227365`,
`ubuntu-latest`, egress Moses Lake US, committed at
`prds/PRD-001-spine/50-evidence/US-011/reachability-ci.json` alongside the Beirut-run
`reachability-local.json`. Result: OKX, Coinbase, Kraken, Coin Metrics and alternative.me all
`200`; **Binance spot and futures `451`, Bybit `403`.** The compute decision is recorded in
`project-documents/10_Technical_Architecture.md`.

It is not in the story table below, and that is deliberate rather than tidied away. It ran as
US-001, which burned its three attempts on things that were not the story: two on Codex
returning 404 for an unavailable model (implementer never executed, $0, 0 tokens) and one on a
criterion of mine that regenerated the evidence locally and destroyed the artifact it existed
to prove. Re-identifying it as US-011 gave the corrected criteria a fresh counter but not a
fresh diff — **the implementation was already committed, so the story changed no files and the
tripwire fired, correctly.** A story whose work predates its identity cannot pass this
framework, and forcing a green tick would have meant reverting working code purely for
ceremony.

The deliverable exists, is CI-verified, and is written into the architecture. The tick does
not add to it.

## Stories

| Story | Title | Depends on |
|---|---|---|
| US-002 | Ingestion package scaffold and typed configuration | — |
| US-003 | Status types — make a missing value unrepresentable as a number | US-002 |
| US-004 | Indicator registry — one declarative source of truth | US-003 |
| US-012 | Database schema and migration with the integrity constraints, applied via psycopg (replaces US-005) | — |
| US-006 | OKX fetcher for BTC daily close, closed candles only | US-003, US-004 |
| US-007 | Persist a datapoint with full provenance | US-005, US-006 |
| US-008 | Scheduled run with a dead-man's-switch on silence | US-007 |
| US-009 | The page — render one value, or its honest absence | US-007 |
| US-010 | Deploy behind Cloudflare Access | US-009 |

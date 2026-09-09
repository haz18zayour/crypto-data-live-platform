---
id: US-009
title: The page — render one value, or its honest absence
priority: 9
touches:
  - web/**
context:
  - AGENTS.md
  - project-documents/10_Technical_Architecture.md
  - project-documents/11_Data_Model.md
---

As the owner, I want to open a page and see the BTC daily close together with its source, its
age, and whether it is stale, so that I can tell a trustworthy number from an untrustworthy
one without opening a database.

This is the product's entire thesis rendered once: **a wrong number must look different from
a right one.**

## Acceptance criteria

- [cmd: npm --prefix web run typecheck] TypeScript compiles with no errors
- [cmd: npm --prefix web run build] The production bundle builds
- [test: an UNAVAILABLE datapoint renders an em dash and its reason, never a zero] The three reasons render distinguishably — not definable for this chain, requires a paid tier, and fetch failed are three different messages
- [test: a STALE datapoint renders the value with its age and a visible stale treatment] A stale number is shown, but never shown as if it were current
- [test: adding a status to the union without handling it is a compile error] The exhaustive switch has a `never` fallthrough, so an unhandled case fails the build rather than falling through to a default render
- [test: the value displays its source vendor, endpoint and source timestamp] Provenance is on the face of the value, not behind a click
- [test: a value whose reference period differs from its publication date shows both] Measured on the live FRED API: M2 is 69 days behind, so rendering it as a current figure is false twice over — wrong period, and silent about the delay
- [cmd: python -c "import pathlib,sys,os; keys=set(v for k,v in (l.split(chr(61),1) for l in pathlib.Path('.env.local').read_text().splitlines() if chr(61) in l and not l.startswith(chr(35))) if k.strip()=='SUPABASE_SERVICE_ROLE_KEY' and v.strip()); blob=chr(10).join(f.read_text(errors='ignore') for f in pathlib.Path('web/dist').rglob('*') if f.is_file()); bad=any(k.strip() in blob for k in keys if k.strip()); print('service-role key present in bundle:', bad); sys.exit(1 if bad else 0)"] The built bundle contains no service-role key — carried from the deferred deploy story, because this is the one mistake here that is hard to walk back
- [browser: prds/PRD-001-spine/50-evidence/US-009/page.png] The rendered page shows the value with its provenance and freshness

## Notes for the implementer

- Vite + React + TypeScript + Tailwind. Read via the Supabase **anon** key against the
  read-only view from US-005. The service-role key must never appear in the web bundle or in
  any `VITE_`-prefixed variable.
- Polling, not WebSockets: TanStack Query with a 30–60s interval. The underlying indicator is
  daily-close; a push layer would deliver nothing and has already been built and reverted once
  in the prior system for starving the scheduled jobs.
- Freshness is computed against the registry's thresholds, not hardcoded in the component.
- Deliberately no layout, theming or design work beyond what these criteria require. One value
  rendered honestly is the deliverable; PRD-007 designs the actual page.
- Do not add a "last known good" fallback that silently shows an older value as current. If it
  is stale, it says so.
- Freshness is measured against **publication**, not the reference period. Otherwise every
  monthly series (M2, CPI) is permanently `STALE` by construction. See `11_Data_Model.md` §4b.

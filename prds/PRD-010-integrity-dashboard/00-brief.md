# PRD-010 · Integrity dashboard

**In one to three sentences:** A self-audit surface for the board itself — frozen-value
detection (a cell that keeps reporting OK with a value that never actually changes, which
looks identical to a healthy quiet market unless something checks), a per-source freshness
SLA rollup across all registered vendors, and registry-generated coverage so an indicator
added without a corresponding UI/test/coverage wire-up fails the build instead of silently
shipping unaudited.

**Depends on:** PRD-005 (the single page — completeness matrix must exist to add an
integrity layer on top of it)

**Roughly:** 6 stories

---

## Phase checklist

- [x] `00-brief.md` — this file. You write it.
- [ ] `10-research.md` — fire `/pre-prd-research`. It will interrogate you. Let it.
- [ ] `20-decisions.yaml` — **GATE G1.** Your answers, plus assumptions with tripwires.
- [ ] `30-spec.md` — fire `/prd`, working from the research file.
- [ ] `40-stories/*.md` — fire `/plan`. One story per file, every criterion with a method.
- [ ] `uf compile PRD-010-integrity-dashboard` — must pass before anything runs.
- [ ] **GATE G2** — approve the estimate.
- [ ] `uf run` — implement + verify, story by story, unattended.
- [ ] **GATE G4** if the diff touched blast-radius paths, then merge.
- [ ] `uf learn` — record anything that cost you real time.

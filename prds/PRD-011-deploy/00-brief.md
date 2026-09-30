# PRD-011 · Deploy behind Cloudflare Access

**In one to three sentences:** Deploy the existing web app to Cloudflare Pages, gated by
Cloudflare Access (Zero Trust) so only the owner can open it. The data path is already live
in production via GitHub Actions; this is purely "make the page reachable from a URL the
owner can open daily," with auth staying entirely at the edge — no login form, no
service-role key ever reaching the browser.

**Depends on:** PRD-005 (the single page — already shipped; this deploys what exists today,
including PRD-009's sparklines/backfill and PRD-010's integrity dashboard)

**Roughly:** 4-5 stories

---

## Phase checklist

- [x] `00-brief.md` — this file. You write it.
- [ ] `10-research.md` — fire `/pre-prd-research`. It will interrogate you. Let it.
- [ ] `20-decisions.yaml` — **GATE G1.** Your answers, plus assumptions with tripwires.
- [ ] `30-spec.md` — fire `/prd`, working from the research file.
- [ ] `40-stories/*.md` — fire `/plan`. One story per file, every criterion with a method.
- [ ] `uf compile PRD-011-deploy` — must pass before anything runs.
- [ ] **GATE G2** — approve the estimate.
- [ ] `uf run` — implement + verify, story by story, unattended.
- [ ] **GATE G4** if the diff touched blast-radius paths, then merge.
- [ ] `uf learn` — record anything that cost you real time.

# PRD-000 · <title>

<!--
COPY THIS WHOLE DIRECTORY to start a PRD:

    cp -r prds/PRD-000-template prds/PRD-001-photo-capture

Then work down the numbered files in order. Each phase writes one file; the next phase
reads it. That directory is the handoff — nothing is carried in a chat window.
-->

**In one to three sentences:** what this PRD delivers, for whom.

**Depends on:** PRD-___ (or nothing)

**Roughly:** ___ stories

---

## Phase checklist

- [ ] `00-brief.md` — this file. You write it.
- [ ] `10-research.md` — fire `/pre-prd-research`. It will interrogate you. Let it.
- [ ] `20-decisions.yaml` — **GATE G1.** Your answers, plus assumptions with tripwires.
- [ ] `30-spec.md` — fire `/prd`, working from the research file.
- [ ] `40-stories/*.md` — fire `/plan`. One story per file, every criterion with a method.
- [ ] `uf compile PRD-000-template` — must pass before anything runs.
- [ ] **GATE G2** — approve the estimate.
- [ ] `uf run` — implement + verify, story by story, unattended.
- [ ] **GATE G4** if the diff touched blast-radius paths, then merge.
- [ ] `uf learn` — record anything that cost you real time.

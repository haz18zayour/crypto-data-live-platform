---
title: <PRD title>
branch: feat/prd-000-template
assumptions:
  - claim: <copied from 20-decisions.yaml>
    tripwire: <the condition that reopens scope>
    acceptedBy: default
---

# <PRD title>

<!--
Fire `/prd` (or agent-skills:spec-driven-development) to write this, working FROM
`10-research.md` — not from memory. The front-matter above is read by `uf compile`;
`branch:` is the branch every story in this PRD commits to.
-->

## What this delivers

## Why (from research)
<!-- Reference 10-research.md rather than restating it. -->

## Approach
<!-- The option chosen in 20-decisions.yaml, and in one line, why. -->

## Data model changes
<!-- Any schema change is blast-radius: it needs gate G4 before merge. -->

## Out of scope
<!-- Carried from 20-decisions.yaml. -->

## Stories

| Story | Title | Depends on |
|---|---|---|
| US-001 | | — |
| US-002 | | US-001 |

<!-- Then write one file per story in 40-stories/. Sizing rule: one story must fit one
     fresh agent context comfortably. `uf compile` rejects a story whose prompt would
     exceed ~60KB, because an oversized story is the most common cause of a loop that
     thrashes and burns three attempts without converging. -->

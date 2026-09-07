# The cycle

Two loops. The outer one runs once per product. The inner one runs once per PRD, and you
walk PRDs in roadmap order — the same way you already work, with the handoffs mechanised
and the done-signal made honest.

Legend: **YOU** = a human decision · **AGENT** = an agent you fire · **UF** = automatic.

---

## Loop 1 — the product (once)

```
  ┌─ 1. IDEA ────────────────── YOU     one or two sentences
  │
  ├─ 2. DISCOVERY ───────────── AGENT   superpowers:brainstorming, agent-skills:interview-me
  │                                     → project-documents/01,02,03
  │
  ├─ 3. STACK ───────────────── AGENT   reads KNOWLEDGE.md → pins hosting, DB, auth, cost
  │                                     → project-documents/10_Technical_Architecture.md
  │
  ├─ 4. ROADMAP ────────────── AGENT   splits the product into PRDs, ordered, with deps
  │                                     → project-documents/05_Product_Roadmap.md
  │
  └─ 5. GATE G1 ───────────── ★YOU★    approve the roadmap and the OUT-OF-SCOPE list
                                        ── the single cheapest gate in the system ──
```

Then: `uf new <product>` scaffolds this, you fill 01–05, and you walk the roadmap.

---

## Loop 2 — one PRD (repeats, in roadmap order)

Every file below lives in `prds/PRD-00N-<slug>/`. Each phase writes exactly one artifact,
and the next phase reads it. **That directory is the handoff.** Nothing is carried in a chat
window, which is why you stop being the message bus.

```
 00-brief.md        YOU    ─ 1-3 sentences. What this PRD is.
        │
        ▼
 10-research.md     AGENT  ─ uf research <PRD>   (or /pre-prd-research)
        │                    ONLINE. Read-only + web. Must cite >= 3 real sources it
        │                    fetched, or compile refuses the PRD. Produces options,
        │                    not a plan, and HARD-STOPS here by design.
        ▼
 20-decisions.yaml  ★YOU★  ─ GATE G1 (scope lock)
        │                    Answer the questions. Anything you don't answer becomes an
        │                    explicit ASSUMPTION row with a tripwire — never a silent guess.
        ▼
 30-spec.md         AGENT  ─ /prd  (or agent-skills:spec-driven-development)
        │                    The PRD proper. Written FROM the research, not from memory.
        ▼
 40-stories/*.md    AGENT  ─ /plan + /ralph sizing
        │                    One story per file. Each acceptance criterion must declare
        │                    HOW it will be proven: [cmd:] [test:] [integration:]
        │                    [browser:] [ci:] [human]. At least one [integration:]
        │                    per PRD — unit-scoped criteria cannot see missing wiring.
        ▼
 spec.lock.json      UF    ─ uf compile
        │                    Refuses to build on: a criterion with no method, a dangling
        │                    skill/doc reference, a duplicate id, a story too big for one
        │                    context, mojibake, a BOM. This is the step that did not exist
        │                    before, and its absence is what killed the last pipeline.
        ▼
 ┌──── GATE G2 ─────★YOU★  ─ "9 stories, est. $14, est. 3h." One tap. Cost is the only
 │                           failure the system cannot detect after the fact.
 │      ▼
 │  ╔═ per story, one at a time ═══════════════════════════════════════╗
 │  ║                                                                   ║
 │  ║   implement      UF → codex    fresh context, workspace-write,    ║
 │  ║       │                        story + inlined skills + past      ║
 │  ║       │                        failures. Cannot write `passes`.   ║
 │  ║       ▼                                                           ║
 │  ║   commit         UF            feat(US-00N): title                ║
 │  ║       ▼                                                           ║
 │  ║   VERIFY         UF → claude   DIFFERENT VENDOR. read-only        ║
 │  ║       │                        sandbox. fresh context. never      ║
 │  ║       │                        shown the implementer's reasoning. ║
 │  ║       │                        4 layers: tripwires → gates → CI   ║
 │  ║       │                        → per-criterion judgement with     ║
 │  ║       │                        cited file:line or test name.      ║
 │  ║       ▼                                                           ║
 │  ║   50-evidence/   UF            verdict.json, gates.json, diffstat ║
 │  ║       │                                                           ║
 │  ║    pass? ── no ──▶ retry (max 3) with the rejection fed back      ║
 │  ║       │            3rd failure ──▶ ★GATE G5★ the spec is wrong    ║
 │  ║      yes                                                          ║
 │  ╚═══════│═══════════════════════════════════════════════════════════╝
 │          ▼
 │      ALL_GREEN
 │          ▼
 └──── GATE G4 ─────★YOU★  ─ merge, IF the diff touched auth / RLS / payments /
            │                migrations / workflows. Otherwise automatic.
            ▼
        GATE G3 ─────★YOU★  ─ deploy to production. Always yours.
            ▼
        uf learn           ─ anything that cost you an afternoon goes to
                             ~/.uf/packs/failures.ndjson and is injected into
                             every relevant story on EVERY future product.
            ▼
        next PRD
```

---

## Where you actually intervene

Five points per PRD, and only two of them are usually slow:

| Gate | When | Typically costs you |
|---|---|---|
| **G1** scope lock | after research | 5–10 min — the one worth spending |
| **G2** budget | before the run starts | one tap |
| **G5** third failure | only when a story fails 3× | a few minutes, rare |
| **G4** blast radius | merging auth/payments/migrations | a real review |
| **G3** production deploy | shipping | one tap |

Everything else — which story is next, library choice, file layout, naming, writing tests,
lint fixes, retries 1 and 2, branch and commit mechanics, "should I continue?" — is decided
by the system and logged. You can read every one of those decisions later; you are never
asked about them live.

---

## How you watch it

| Surface | Question it answers | Command |
|---|---|---|
| Terminal | "where is everything right now" | `uf status` · `uf status --all` |
| Terminal | "why was that story rejected" | `uf why US-004` |
| Mission Control | "is anything waiting on me" — from your phone | `uf export`, then publish |
| Orca | "watch the agents work, live" | its own app |
| Git | "what actually changed" | the branch, per story |

The default state of Mission Control is the sentence **"Nothing needs you."** If you are
seeing it more often than that, a gate is mis-tuned.

# Knowledge — what we already know, and where it is

The knowledge base is `hz-skills-universal/website-dev-deploy/` — 41 categories covering
every decision a web product forces. It is not vendored into products; reference it by path
in a story's `context:` block and `uf compile` will inline the file's text into the prompt.
A path that does not resolve fails the build.

```yaml
# in a story's front-matter
context:
  - kb:10-storage-cdn-media/README.md
  - project-documents/10_Technical_Architecture.md
```

---

## The 41 categories

| # | Category | Reach for it when |
|---|---|---|
| 01 | domains-dns | buying a domain, DNS, subdomains |
| 02 | hosting-and-deployment | choosing where it runs |
| 03 | frameworks-and-cms | picking the frontend/CMS |
| 04 | databases | schema, Postgres/Supabase, migrations |
| 05 | ai-services | LLM providers, embeddings, cost |
| 06 | email-and-messaging | transactional email, SMS, push |
| 07 | automation-and-workflows | cron, queues, background jobs |
| 08 | auth-and-identity | login, OAuth, sessions, RLS |
| 09 | payments-and-billing | Stripe, subscriptions, tax |
| 10 | storage-cdn-media | file upload, images, signed URLs |
| 11 | analytics-and-observability | product analytics, logs, traces |
| 12 | security-and-compliance | hardening, secrets, threat model |
| 13 | cicd-and-devops | pipelines, environments |
| 14 | ai-website-builders | when a builder beats building |
| 15 | claude-skills-and-agents | agent tooling |
| 16 | search | full-text, vector, hybrid |
| 17 | reference-stacks-and-cost | **start here** — proven stacks with real cost |
| 18 | rag-chatbot-integration | retrieval over your own data |
| 19 | very-useful-gits | libraries worth knowing |
| 20 | testing-and-qa | test strategy, E2E |
| 21 | seo-aeo-geo | discoverability |
| 22 | accessibility | a11y requirements |
| 23 | i18n | multi-language |
| 24 | legal-and-privacy | ToS, privacy policy, GDPR |
| 25 | design-and-discovery | research, wireframes |
| 26 | ai-ops-and-governance | evals, guardrails |
| 27 | performance-and-web-vitals | LCP/INP/CLS |
| 28 | reliability-dr-incident | backups, incidents |
| 29 | api-design-and-delivery | REST/GraphQL, versioning |
| 30 | realtime-and-collaboration | websockets, presence |
| 31 | mobile-and-pwa | installable apps |
| 32 | crm-support-cdp | support tooling |
| 33 | experimentation-ab-testing | flags, experiments |
| 34 | content-brand-assets | brand, copy, assets |
| 35 | migration-replatforming | moving off something |
| 36 | developer-environment | local setup |
| 37 | project-process-and-docs | how work is run |
| 38 | cloud-finops | keeping the bill down |
| 39 | data-engineering-and-bi | pipelines, warehouses |
| 40 | trust-safety-and-privacy-engineering | abuse, PII |
| 41 | growth-onboarding-and-lifecycle | activation, retention |

## Which to read at which phase

- **Stack decision (product phase 3):** 17 first, then 02, 03, 04, 08 — and 05 if there is AI in it.
- **Filling `15_Services_and_Credentials.md`:** 01, 02, 04, 05, 06, 08, 09, 10, 11 — every
  one of those categories implies an account and usually a key.
- **Before shipping:** 12, 13, 21, 22, 24, 27, 28.
- **After launch:** 11, 33, 38, 41.

## Cross-product failures

`~/.uf/packs/failures.ndjson` — things that cost real time, once, on a real product.
Add one with `uf learn`:

```bash
uf learn --sig "pnpm 11 blocks esbuild postinstall in CI" \
         --symptom "ERR_PNPM_… build script blocked" \
         --fix "pin pnpm to 9 in the setup-node action" \
         --cost "6 commits, ~50m"
```

The top 6 relevant entries are injected into every story prompt automatically. Successes
generalise badly; failures generalise brilliantly.

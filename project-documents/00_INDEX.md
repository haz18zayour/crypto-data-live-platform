# Project documents

Filled during the product phase, before the first PRD. Each one is short on purpose — a
document nobody reads is worse than no document, and the previous framework's 27-file set
was ~70% empty on the one real product that used it.

**Write these four before anything else:**

| Doc | Answers | Blocks |
|---|---|---|
| [01_Problem_Statement](01_Problem_Statement.md) | why this is worth building | everything |
| [05_Product_Roadmap](05_Product_Roadmap.md) | which PRDs, in what order | every PRD |
| [10_Technical_Architecture](10_Technical_Architecture.md) | what it is built on | every story |
| [15_Services_and_Credentials](15_Services_and_Credentials.md) | which accounts and keys to open | the first run |

**Write these when the product needs them, not before:**

| Doc | Write it when |
|---|---|
| [02_Jobs_To_Be_Done](02_Jobs_To_Be_Done.md) | there is more than one kind of user |
| [03_Product_Vision](03_Product_Vision.md) | you need to say no to things |
| [11_Data_Model](11_Data_Model.md) | the first schema story |
| [14_API_Design](14_API_Design.md) | something else will call this |
| [20_Design_System](20_Design_System.md) | the first UI story |
| [24_Testing_Strategy](24_Testing_Strategy.md) | tests get inconsistent |
| [26_Operational_Runbook](26_Operational_Runbook.md) | it is live and can page you |

Every one of these can be referenced from a story's `context:` block, and `uf compile`
inlines the text into the prompt. A story that says "follow the design system" without
referencing `20_Design_System.md` is a story whose agent never saw it.

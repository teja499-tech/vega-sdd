# Create a Vega-ready PRD with ChatGPT, Claude, or another assistant

You do not need a finished PRD before you start thinking about a product. Use a general chat assistant for discovery, then give the resulting `PRD.md` to Vega SDD. The assistant helps you express intent; Vega turns approved intent into durable requirements, architecture decisions, tasks, checks, and evidence.

## Recommended workflow

```mermaid
flowchart LR
    A[Idea or problem] --> B[Discovery interview]
    B --> C[PRD draft]
    C --> D[PRD critique]
    D --> E[Final PRD.md]
    E --> F[sdd init]
```

Use ChatGPT, Claude, or another assistant for stages B–D. Do not ask it to implement code yet. Keep product decisions, assumptions, and unknowns visibly separate.

## Option A: guided discovery interview

Paste this prompt into ChatGPT or Claude, followed by your idea.

```text
Act as a product discovery lead helping me prepare a PRD for Vega SDD, a
spec-driven software development framework.

Interview me in small rounds. Ask no more than five questions at a time and
wait for my answers before continuing. Focus only on decisions that materially
affect product behavior, scope, users, workflows, data, privacy, security,
compliance, accessibility, integrations, operations, deployment, or success
metrics. Do not force technology choices unless I already have a constraint.

During the interview:
- distinguish facts, decisions, assumptions, suggestions, and open questions;
- identify conflicts or missing edge cases;
- do not invent requirements when I do not know the answer;
- recommend sensible options, but leave consequential decisions to me;
- keep a running decision log;
- explicitly identify what is out of scope for the first release.

When discovery is sufficient, produce a complete Markdown PRD with these
sections:
1. Executive summary
2. Problem and desired outcome
3. Goals and measurable success metrics
4. Non-goals
5. Users, roles, and permissions
6. Primary user journeys
7. Functional requirements
8. Business rules and invariants
9. Data and retention requirements
10. Security, privacy, compliance, and accessibility
11. Integrations and external dependencies
12. Reliability, performance, observability, and operational requirements
13. Compatibility, migration, and rollout constraints
14. Acceptance scenarios, including negative and failure paths
15. Assumptions
16. Open questions
17. Decision log

Use stable labels such as BR-01 for business rules only when useful. Do not
create implementation tasks, source filenames, class names, database tables,
or an architecture unless those are explicit constraints. The result must be
self-contained and suitable to save as PRD.md.

My idea:
[PASTE YOUR IDEA HERE]
```

This option is best when the idea is early or complex. Continue until the unresolved questions are either answered or intentionally recorded.

## Option B: turn existing notes into a PRD

Use this when you already have meeting notes, a proposal, customer feedback, or a rough requirements list.

```text
Convert the source material below into a rigorous Markdown PRD for Vega SDD.

Rules:
- preserve the author's meaning and do not silently invent product behavior;
- separate explicit requirements from assumptions and recommendations;
- identify contradictions and put unresolved ones under Open Questions;
- express observable outcomes rather than code-level implementation steps;
- include users/roles, primary workflows, business rules, negative paths,
  data/privacy/security needs, integrations, operational needs, measurable
  success criteria, non-goals, migration/compatibility constraints, and rollout;
- if the source specifies a technology or platform, record it as a constraint
  and explain why it is binding if the source says why;
- do not fabricate research, legal conclusions, SLAs, performance numbers,
  budgets, owners, or dates;
- finish with a traceable decision log and a concise list of questions that
  materially affect scope or architecture.

Return only the final PRD in Markdown, ready to save as PRD.md.

Source material:
[PASTE NOTES HERE]
```

## Option C: brownfield enhancement PRD

For an existing repository, describe the change and the compatibility boundary. The assistant does not need the entire source tree; Vega will inspect a bounded source view during initialization.

```text
Help me write a brownfield enhancement PRD for an existing software system.
The PRD will be used by Vega SDD with `--project-kind existing`.

Create a Markdown PRD that clearly separates:
- observed current behavior and its evidence;
- desired behavior;
- behavior that must remain backward compatible;
- data/schema/API/UI changes;
- migration, rollout, feature-flag, and rollback needs;
- affected users and permissions;
- acceptance scenarios and regression scenarios;
- known unknowns that require repository or runtime investigation.

Do not pretend that filenames or my summary prove current runtime behavior.
Mark uncertain statements as assumptions or investigation questions. Do not
redesign unrelated parts of the system.

Current system summary:
[PASTE SUMMARY]

Requested change:
[PASTE CHANGE]

Known constraints and compatibility promises:
[PASTE CONSTRAINTS]
```

## Critique the draft before using it

Start a new assistant conversation if possible so the critic does not simply defend its earlier draft.

```text
Review the PRD below as an independent product, architecture, security,
operations, and test-readiness reviewer.

Find only material issues. For each issue provide:
- severity: blocker, high, medium, or low;
- exact PRD section;
- what is ambiguous, contradictory, untestable, unsafe, or missing;
- why it matters;
- a concrete proposed clarification, clearly labelled as a proposal.

Specifically check:
- whether users, permissions, and tenant/data boundaries are clear;
- whether the main workflow includes empty, error, retry, cancellation, and
  partial-failure behavior;
- whether success metrics are measurable rather than aspirational;
- whether privacy, retention, accessibility, compatibility, migration,
  observability, and rollback are addressed when relevant;
- whether requirements accidentally prescribe implementation;
- whether assumptions have been disguised as facts;
- whether the first-release non-goals are explicit.

Do not rewrite the PRD yet. Ask me to decide every blocker or high-severity
product question. After I answer, return a corrected complete Markdown PRD.

PRD:
[PASTE PRD]
```

## Save the result

Create a repository and paste the final Markdown into `PRD.md`:

```bash
mkdir my-product
cd my-product
git init
${EDITOR:-vi} PRD.md
```

Clipboard options:

```bash
# macOS: copy the PRD in the chat UI, then
pbpaste > PRD.md

# Linux with xclip: copy the PRD, then
xclip -selection clipboard -o > PRD.md
```

Review the saved file before using it:

```bash
sed -n '1,240p' PRD.md
git status --short
```

## Initialize Vega from the PRD

New application:

```bash
sdd doctor
sdd init --prd PRD.md --agent cursor --project-kind new
```

Existing application:

```bash
sdd doctor
sdd init --prd PRD.md --agent cursor --project-kind existing
```

You may choose `codex`, `claude`, `gemini`, or `copilot` instead. Initialization performs its own material-question interview and architecture workshop. The external assistant's PRD is a source, not unquestionable truth.

## What belongs in the PRD versus Vega's architecture workshop

| Put in the PRD | Let the workshop decide |
| --- | --- |
| Users and permissions | Framework/library choice when not constrained |
| Required user-visible behavior | Database choice when multiple options fit |
| Business rules and invariants | Deployment topology alternatives |
| Security/compliance obligations | Queue/cache choice when requirements justify one |
| Existing platform or mandated cloud | Implementation patterns within approved constraints |
| Compatibility and migration promises | Tradeoffs among credible current technologies |
| Performance or availability targets backed by need | Exact module/class/file organization |
| Budget, location, or vendor constraints | Low-level implementation details |

If a technology is already a real organizational constraint, put it in the PRD. If it is only a preference, label it as a preference and explain the reason.

## Privacy and source-handling checklist

Before sharing material with any chat assistant:

- remove secrets, tokens, private keys, and credentials;
- remove or anonymize production/customer records;
- follow your organization's approved AI/data policy;
- use enterprise/private assistant settings when required;
- do not rely on a general assistant for legal or regulatory approval;
- record research sources and dates when current external facts affect a decision.

Vega's isolated initialization view omits common secret and agent-instruction surfaces, but that is not a substitute for repository hygiene or least-privilege provider configuration.

## PRD readiness checklist

A PRD is ready enough for `sdd init` when:

- the problem, users, and desired outcome are clear;
- the first release has explicit goals and non-goals;
- primary workflows and important failure paths are described;
- permissions and data boundaries are not implicit;
- non-negotiable constraints are labelled as constraints;
- success criteria can be observed or measured;
- unknown consequential decisions remain visible as open questions;
- it avoids unnecessary file/class/schema prescriptions;
- it contains no secrets or sensitive raw data.

It does not need to contain final architecture decisions. That is the purpose of Vega's interactive architecture workshop.

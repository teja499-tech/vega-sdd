# Vega SDD user guide

This guide takes a project from an idea or PRD through initialization, implementation, review, change handling, and delivery. Every command is intended to be run from a terminal in the project repository unless `--root` points elsewhere.

For scenario-only recipes, see [use-case journeys](USE_CASES.md). For every CLI command, see [command reference](COMMAND_REFERENCE.md).

## 1. Understand the operating model

Vega separates four kinds of authority:

| Concern | Owner |
| --- | --- |
| Product intent and consequential decisions | You and the approved PRD/ADRs |
| Task selection, state transitions, evidence, and approvals | Vega controller |
| Application code and tests | Selected coding-agent CLI |
| Verification | Deterministic project checks plus an isolated review pass |

The repository—not an old chat—is the durable memory. A new terminal or a different coding agent can continue from `.sdd/`, `.agents/`, Git, and the working tree.

## 2. Prerequisites

- Python 3.11 or later.
- Git for real development and source-bound evidence.
- One authenticated coding-agent CLI for real implementation: Cursor, Codex, Claude Code, Gemini CLI, or GitHub Copilot CLI.
- Real non-interactive test/check commands for the project.

Install Vega and inspect the environment:

```bash
python -m pip install vega-sdd
sdd doctor
```

Typical doctor usage is diagnostic, not an installation wizard. Install and authenticate the vendor CLI using that vendor's instructions, then run `sdd doctor` again.

Optional local retrieval/compression tools:

```bash
python -m pip install graphifyy headroom-ai
sdd doctor
```

## 3. Prepare the PRD

Vega accepts a normal Markdown or text PRD. If you only have an idea, use the reusable prompts in [PRD discovery with ChatGPT or Claude](PRD_DISCOVERY.md).

A useful PRD states:

- problem and desired outcome;
- target users and roles;
- primary workflows;
- business rules and non-negotiable constraints;
- data, privacy, security, compliance, accessibility, and operational needs;
- integrations and compatibility boundaries;
- success measures;
- out-of-scope behavior;
- known open questions.

Create the repository and PRD:

```bash
mkdir my-product
cd my-product
git init
${EDITOR:-vi} PRD.md
```

Do not put credentials, production records, private keys, or unnecessary personal data in the PRD.

## 4. Choose the project path

### New application

```bash
sdd init --prd PRD.md --agent cursor --project-kind new
```

### Existing application

Run from the existing repository root:

```bash
sdd init --prd PRD.md --agent cursor --project-kind existing
```

Brownfield initialization gives the agent an isolated, bounded copy of relevant source files. Known provider instructions, settings, context filters, common key/certificate files, and environment files are omitted before capability approval. The prompt also includes a bounded repository inventory and evidence excerpts. Review generated specifications against runtime behavior and tests; filenames alone are not proof.

### Deterministic workflow trial

```bash
sdd init --prd PRD.md --agent mock --project-kind new --yes
sdd verify
sdd start
```

The mock adapter produces deterministic fixture output and exercises state transitions. It does not build production code.

## 5. Complete interactive initialization

Initialization has four stages.

### Product discovery

The selected agent extracts users, capabilities, workflows, constraints, assumptions, and material questions. Answer only questions that change product behavior, scope, data, security, architecture, deployment, or operations.

Good answer:

```text
Each family profile has its own language preference. Changing one profile must not change another profile.
```

Unhelpful implementation micromanagement:

```text
Create a Boolean column and use a switch statement in service.py.
```

### Architecture workshop

For each material decision, Vega shows options, fit, tradeoffs, and a recommendation. At the prompt:

- enter a number to select an option;
- enter `a` to ask the architect a follow-up;
- enter `o` to supply an alternative;
- enter `d` to defer.

Example:

```text
Choose option number, 'a' ask architect, 'o' other, or 'd' defer [1]: a
Question for architect: Which option has the simplest local development path?
```

Avoid deferring decisions that block security, data ownership, compatibility, or deployment. `--yes` automatically accepts recommendations and is best reserved for demos or a PRD that already fixes all material decisions.

### Specification generation

The agent proposes stable requirements, acceptance criteria, features, tasks, verification, and applicable design documents. Vega validates the structure and traceability before saving it.

### Readiness review

Tested mock output looks like:

```text
4/4 Readiness review
✓ Requirements: 1
✓ Features: 1
✓ Architecture decisions: 1
✓ Traceability: valid (0 warning(s))
Project is ready for implementation.
```

If material questions remain, initialization succeeds but development stays blocked until they are answered or an explicit existing default is accepted.

## 6. Review generated intent

Do this before allowing a real agent to edit application code:

```bash
sdd status
sdd requirements
sdd architecture
sdd roadmap
sdd feature F001
sdd verify
sdd clarify
```

Typical status output:

```text
SDD Status · my-product
Run status             ready
Overall                0.0%
Specification          100.0%
Implementation         0.0%
Verification           0.0%
Requirements verified  0/1
Tasks verified         0/1
Current                - / -
```

Review for:

- missing or invented product rules;
- ambiguous acceptance criteria;
- incorrect architecture selections;
- oversized tasks;
- absent negative, security, migration, compatibility, or failure-path tests;
- conflicts with existing behavior.

Use `sdd change` for approved-intent corrections rather than editing generated state casually.

## 7. Resolve clarifications

List unresolved questions:

```bash
sdd clarify
```

Answer one explicitly:

```bash
sdd clarify Q1 --answer "Workspace owners may export only their own workspace."
sdd clarify ARCH-002 --answer "PostgreSQL"
sdd verify
```

To accept only defaults already recorded in the spec/ADR:

```bash
sdd start --accept-deferred --max-tasks 1
```

Placeholder answers such as `Deferred` do not resolve architecture. Vega validates all defaults before writing any of them.

## 8. Configure deterministic checks and approve capabilities

Real-agent entry points require `.sdd/workspace.yaml` plus an approval digest covering the policy and provider-visible instruction/capability files.

Start interactively:

```bash
sdd project profiles
sdd project inspect
sdd project setup
sdd project check
sdd project readiness
```

For repeatable configuration, save and review a policy file:

```yaml
schema_version: 1
components:
  - id: api
    path: .
    kind: service
    checks:
      test:
        argv: [python, -m, pytest, -q]
        timeout: 900
      contract:
        argv: [python, -m, pytest, -q, tests/contract]
        timeout: 300
    build:
      argv: [python, -m, build]
      timeout: 600
    artifact: dist/my_product-1.0.0-py3-none-any.whl
repo:
  provider: local
  base_branch: main
  protected_branches: [main, master, develop, "release/*"]
  branch_prefix: sdd
  allow_push: false
  allow_merge: false
  auto_commit: false
agent_timeout: 1800
max_tasks_per_run: 25
protected_paths: []
```

Apply it:

```bash
sdd project configure --file workspace-policy.yaml
sdd project check
sdd project readiness
```

The policy uses argv arrays, not shell strings. Put secret *names* in `env_names`, never secret values in YAML. Every project kind has required checks; provide a real command or a substantive waiver. See [project lifecycle](PROJECT_LIFECYCLE.md) for web, library, CLI, data, ML, infrastructure, mobile, desktop, embedded, docs, custom, and monorepo examples.

On a new repository that does not yet contain runnable code, configure any meaningful baseline command that already exists and use a substantive, temporary waiver for checks that cannot exist before the first implementation task. Replace those waivers with real commands as soon as the relevant component is created. `sdd project check` records current full-check evidence; `sdd project readiness` then confirms that evidence and the policy have no remaining gaps.

Changes to approved agent instructions, skills, roles, Copilot/Gemini configuration, or other protected capability surfaces invalidate approval. Review the change, then reapply the policy:

```bash
git diff -- AGENTS.md .agents .cursor .claude .codex .gemini .github
sdd project configure --file .sdd/workspace.yaml
```

## 9. Commit the baseline and create an execution branch

```bash
git status --short
git add -A
git status --short
git commit -m "Initialize Vega SDD project"
sdd repo branch first-scope
```

Review both status outputs and unstage credentials, local caches, or unrelated work before committing. Initialization creates several root documents and provider-specific instruction surfaces in addition to `.sdd/` and `.agents/`; leaving any of them untracked makes the source tree dirty, so `sdd repo branch` will stop rather than hide the omission.

The default branch name is `sdd/first-scope`. Vega refuses implementation on protected, detached, or unborn branches. It also supports an isolated worktree:

```bash
sdd repo branch first-scope --worktree ../my-product-first-scope
cd ../my-product-first-scope
```

Linked worktrees share the controller lock so two Vega writers cannot mutate one repository state concurrently.

## 10. Run one bounded task first

```bash
sdd start --max-tasks 1
```

Then inspect the result:

```bash
git status --short
git diff --stat
sdd status
sdd log --limit 30
sdd changelog
sdd project check
```

If implementation, tests, and evidence look correct:

```bash
sdd resume
```

Without `--max-tasks`, Vega continues through dependency-ready tasks until completion, a blocker, a failed task, a pause, or an execution-policy limit.

## 11. Monitor and pause

One-time status:

```bash
sdd status
```

Continuous status in another terminal:

```bash
sdd watch
```

Request a safe stop:

```bash
sdd pause
```

Ctrl+C in the foreground also requests a safe pause. Vega stops at a task boundary instead of killing an agent during an unknown write.

## 12. Ask questions without changing the plan

```bash
sdd ask "Which requirement authorizes administrators to export data?"
sdd ask "Where is task creation persisted?"
sdd ask "Which ADR selected PostgreSQL and why?"
```

`sdd ask` uses approved specs, ADRs, repository context, and Graphify when available. It is read-only and cannot approve a change or mark work complete.

For a longer conversation:

```bash
sdd intervene
```

Example:

```text
architect> Why is this setting stored on the account instead of the profile?
architect> Which requirement allowed this endpoint to be public?
architect> change: every profile needs an independent language preference
architect> exit
```

Each intervention answer is serialized with other controller writes.

## 13. Handle defects and changed intent

### Implementation defect

```bash
sdd change "Creating a note returns 500 when the optional title is absent"
```

If approved intent is already correct, Vega creates a repair task without rewriting the requirement.

### Requirement or architecture change

Preview the classification and invalidation set:

```bash
sdd change "Every profile needs an independent language preference"
```

After reviewing the printed impact, approve explicitly:

```bash
sdd change "Every profile needs an independent language preference" --approve
sdd verify
sdd status
sdd resume
```

Stable unaffected task IDs retain state. Affected work is invalidated conservatively and loses stale verification evidence.

## 14. Retry failed work

Keep current application changes and re-run verification/repair:

```bash
sdd task retry TASK-F001-003 --keep-code
sdd resume
```

Discard only the task's lifecycle status and requeue it as pending:

```bash
sdd task retry TASK-F001-003 --wipe-status
sdd resume
```

Vega does not run a failed task again until you request a retry.

## 15. Switch coding agents

At a clean task boundary:

```bash
sdd pause
sdd agent list
sdd agent use claude
sdd doctor
sdd resume
```

The PRD, requirements, ADRs, task IDs, and evidence do not move with the vendor. Changing provider-visible capability files may require workspace reapproval.

For high-risk work, configure a distinct `review_agent` in `.sdd/config.yaml`:

```yaml
primary_agent: cursor
review_agent: claude
require_distinct_review_agent: true
```

Then:

```bash
sdd doctor
sdd start --max-tasks 1
```

The default reviewer is a fresh subprocess of the selected adapter; it is isolated self-review, not a different model/provider.

## 16. Use Graphify and Headroom

```bash
python -m pip install graphifyy headroom-ai
sdd graph refresh
sdd graph query "request authentication database path"
```

Graphify builds a local code graph and Vega adds deterministic requirement/task/ADR corpus hits. Headroom compresses context and check logs only when useful; originals remain under `.sdd/runtime/originals/`. Missing optional tools do not block a run.

## 17. Maintain human documentation

```bash
sdd docs refresh
sdd docs check
```

Ask the selected agent to inspect code read-only and enrich approved design documentation:

```bash
sdd docs refresh --enrich
sdd docs check
```

Generated documents live under `.sdd/docs/` and include system overview, HLD, LLD, database, API, security, operations, test plan, existing-system analysis, contribution, release, and traceability views where applicable. Structural completeness does not certify factual correctness; review the content.

## 18. Recover after interruption

```bash
git status --short
sdd status
sdd log --limit 50
sdd verify
sdd resume
```

Create an explicit checkpoint:

```bash
sdd recovery checkpoint
```

Restore canonical state from a checkpoint while preserving application code:

```bash
sdd recovery restore CHECKPOINT-ID
sdd status
sdd verify
```

See [recovery](RECOVERY.md) for crash boundaries, projection recovery, Git behavior, and large-repository snapshot settings.

## 19. Prepare a pull request and CI

Generate non-overwriting repository starters:

```bash
sdd repo scaffold --owner @your-org/your-team
sdd pipeline export --provider github
git status --short
git add -A
git status --short
git commit -m "Add project checks and CI"
```

For a configured GitHub provider:

```bash
sdd project check
sdd repo audit-host
sdd repo pr --title "Implement first scope" --body-file .github/pull_request_template.md
sdd repo pr-status 123
sdd repo merge 123
```

Push and merge remain disabled unless the approved repository policy permits them. Vega does not bypass host reviews, required checks, protected branches, or expected-head checks.

## 20. Build and deploy immutable releases

After workspace build/artifact and environment hooks are configured:

```bash
sdd project check
sdd release build 1.2.3
sdd release deploy 1.2.3 staging
sdd release deploy 1.2.3 production --approve
```

If external state is uncertain after a timeout:

```bash
sdd release reconcile production --outcome failed \
  --note "Operator confirmed the previous version remained active"
```

See [project lifecycle](PROJECT_LIFECYCLE.md) before enabling hosted PR or deployment actions.

## 21. Know the safety boundary

Vega protects controller state, approval-bound capability files, read-only source snapshots, file modes, and Git HEAD/refs/index/config/hooks. It fails closed on corrupt projection recovery evidence and serializes controller writers.

It is not an OS sandbox. An agent process with network access or broad credentials may read or transmit data before a controller can restore files. Use provider sandboxes, least privilege, isolated workstations/containers, secret managers, protected branches, and human review appropriate to the project.

Large repositories can raise read-only snapshot bounds deliberately:

```bash
export SDD_GUARD_MAX_FILES=50000
export SDD_GUARD_MAX_BYTES=1073741824
export SDD_GUARD_MAX_FILE_BYTES=268435456
sdd start --max-tasks 1
```

These values are bytes/counts and must be positive integers. Raising them increases memory use; do so only after evaluating the host.

## Recommended operating pattern

1. Use a PRD for product intent, not code-level instructions.
2. Make security, data, compatibility, language, accessibility, and operational constraints explicit.
3. Review requirements, ADRs, and the first feature before coding.
4. Configure real deterministic checks before real-agent execution.
5. Commit an approved baseline and work on an execution branch.
6. Run one task first; inspect implementation and evidence.
7. Use `ask` for questions, `intervene` for diagnosis, and `change` for mutations.
8. Keep tasks bounded and split work that exceeds review limits.
9. Pause or switch agents at clean task boundaries.
10. Keep `.sdd/`, `.agents/`, PRD, policies, and evidence in version control.

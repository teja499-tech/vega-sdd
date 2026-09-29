# Vega SDD use-case journeys

These recipes are designed to be copied into a terminal and adapted. Run commands from the repository root unless a command changes directory. Replace example agent names, test commands, IDs, versions, owners, and repositories with real values.

## Before any real-agent journey

```bash
python -m pip install vega-sdd
sdd doctor
```

At least one supported agent CLI must be installed and authenticated. Start with [PRD discovery](PRD_DISCOVERY.md) if you do not yet have `PRD.md`.

Whenever a recipe stages files, review both `git status` outputs and unstage credentials, local caches, or unrelated work before committing.

## 1. Build a new application from a PRD

Use this for a new API, web application, mobile app, library, CLI, data pipeline, ML project, infrastructure repository, or custom system.

```bash
mkdir my-product
cd my-product
git init
${EDITOR:-vi} PRD.md

sdd init --prd PRD.md --agent cursor --project-kind new
sdd requirements
sdd architecture
sdd roadmap
sdd verify
sdd clarify

sdd project inspect
sdd project setup
sdd project check
sdd project readiness

git status --short
git add -A
git status --short
git commit -m "Initialize Vega SDD project"
sdd repo branch first-scope

sdd start --max-tasks 1
git diff --stat
sdd status
sdd log --limit 30
sdd resume
```

Best practice: inspect the first completed task and its tests before allowing a long run. Use `sdd pause` from another terminal when you want the current run to stop at the next safe boundary.

If the greenfield repository has no runnable code yet, use substantive temporary waivers for checks that cannot exist before the first task, then replace them with real commands as soon as the component is created. Readiness follows the full check because it requires current check evidence.

## 2. Add a feature to an existing application

Create a PRD that describes current behavior, desired behavior, compatibility constraints, migration/rollout, and regression expectations.

```bash
cd path/to/existing-repository
git status --short
${EDITOR:-vi} PRD.md

sdd init --prd PRD.md --agent claude --project-kind existing
sdd requirements
sdd architecture
sdd feature F001
sdd verify

sdd project inspect
sdd project setup
sdd project check
sdd docs refresh --enrich
sdd docs check

git status --short
git add -A
git status --short
git commit -m "Adopt Vega SDD for feature delivery"
sdd repo branch requested-feature
sdd start --max-tasks 1
```

After the first task:

```bash
git diff --stat
sdd ask "Which existing behavior must remain backward compatible?"
sdd status
sdd project check
sdd resume
```

Do not use `sdd init --force` as an upgrade command. It is for intentional reinitialization and backs up/removes the current `.sdd` state.

## 3. Fix a defect without changing approved intent

Use this when the implementation violates an existing requirement or acceptance criterion.

```bash
cd path/to/project
sdd status
sdd ask "Which acceptance criterion covers an omitted note title?"
sdd change "Creating a note returns 500 when the optional title is absent"
```

If Vega classifies it as an implementation defect, it creates a repair task. Then:

```bash
sdd status
sdd resume
sdd project check
```

If the task previously failed and you want to keep the current code:

```bash
sdd task retry TASK-F001-R001 --keep-code
sdd resume
```

Do not weaken the requirement or test simply to match incorrect code.

## 4. Change an approved requirement

Preview impact first:

```bash
sdd pause
sdd change "Each family profile must have an independent language preference"
```

Vega prints the classification, affected requirements/features/tasks, and proposed changes. After reviewing it:

```bash
sdd change --approve-id CR-2A81FC
sdd requirements
sdd architecture
sdd roadmap
sdd verify
sdd status
sdd resume
```

Approval is never delegated through MCP or an IDE shortcut. A human copies the emitted ID into `--approve-id` after reviewing invalidation. The second command loads the stored proposal and does not re-run analysis, so approval cannot silently broaden its scope.

The approved reconcile reads staged specs, returns only the affected slices, and removes its temporary input afterward. Vega rejects updates outside the previewed requirement/feature/task scope, agent-supplied execution status, empty policy rewrites, and responses that make no canonical change. If you launched the command from inside Cursor, repeat it in a host terminal; use `SDD_BLOCK_NESTED_CURSOR=1` when you prefer a hard failure for nested sessions.

Expected completion:

```text
Reconciling approved change (slice merge, 300s timeout)…
CR-2A81FC applied.
Review `sdd status`, then `sdd resume` when ready.
```

## 5. Resume or recover work

### New terminal or cleared chat

```bash
cd path/to/project
sdd status
sdd log --limit 30
sdd resume
```

No old agent conversation is required.

### Process or machine interruption

```bash
git status --short
sdd status
sdd log --limit 50
sdd verify
sdd intervene
sdd resume
```

If a task reached implementation but not review, Vega can continue from verification rather than blindly implementing it again.

### Explicit checkpoint and restore

```bash
sdd recovery checkpoint
# Record the printed checkpoint ID.
sdd recovery restore CHECKPOINT-ID
sdd status
sdd verify
```

Checkpoint restore changes canonical SDD state, not Git history, application code, deployments, or external data.

## 6. Switch agents without losing project context

```bash
sdd pause
sdd agent list
sdd agent use codex
sdd doctor
sdd status
sdd resume
```

Supported names are `cursor`, `codex`, `claude`, `gemini`, `copilot`, and `mock`. Switch at a task boundary when practical.

For an intentionally different reviewer:

```bash
${EDITOR:-vi} .sdd/config.yaml
```

Add or update:

```yaml
primary_agent: cursor
review_agent: claude
require_distinct_review_agent: true
```

Then verify both are available:

```bash
sdd doctor
sdd start --max-tasks 1
```

## 7. Work in a monorepo

Initialize once at the repository root and describe each component in the workspace policy.

```bash
cd path/to/monorepo
sdd init --prd PRD.md --agent cursor --project-kind existing
sdd project inspect
${EDITOR:-vi} workspace-policy.yaml
```

Example:

```yaml
schema_version: 1
components:
  - id: api
    path: services/api
    kind: service
    checks:
      test:
        argv: [python, -m, pytest, -q]
      contract:
        argv: [python, -m, pytest, -q, tests/contract]
  - id: web
    path: apps/web
    kind: web
    depends_on: [api]
    checks:
      test:
        argv: [npm, test, --, --run]
      accessibility:
        argv: [npm, run, test:a11y]
repo:
  provider: local
  base_branch: main
  branch_prefix: sdd
agent_timeout: 1800
max_tasks_per_run: 20
```

Apply and run:

```bash
sdd project configure --file workspace-policy.yaml
sdd project check
sdd project readiness
git status --short
git add -A
git status --short
git commit -m "Configure monorepo SDD checks"
sdd repo branch cross-component-feature
sdd start --max-tasks 1
```

Components execute in dependency order. Vega remains a single writer even when a branch uses a linked worktree.

## 8. Adopt and document a mature application

Use this when the first goal is traceability and human documentation rather than a new feature.

```bash
cd path/to/application
${EDITOR:-vi} PRD.md
sdd init --prd PRD.md --agent copilot --project-kind existing
sdd project inspect
sdd project setup
sdd project check
sdd docs refresh --enrich
sdd docs check
sdd requirements
sdd architecture
sdd roadmap
sdd verify
```

Inspect:

```bash
sed -n '1,220p' SDD_PROJECT.md
sed -n '1,220p' .sdd/docs/README.md
git status --short
```

Resolve factual gaps through evidence, not invented prose. If code conflicts with approved intent, use `sdd change`. If the application is intentionally complete, you do not need to run `sdd start` merely to generate documentation.

## 9. Add a project-specific skill

Create a narrowly triggered runbook:

```bash
mkdir -p .agents/skills/healthcare-privacy
${EDITOR:-vi} .agents/skills/healthcare-privacy/SKILL.md
```

Example frontmatter:

```markdown
---
name: healthcare-privacy
description: Review patient-data boundaries, minimum necessary access, audit, and retention for healthcare features.
routing:
  phases: [implement, repair, review]
  any: [patient, phi, clinical, healthcare, medical record]
---

# Healthcare privacy

## Scope
Review only the bounded feature and approved security/privacy requirements.

## Procedure
1. Identify data classes and actors.
2. Verify minimum-necessary access and tenant/profile boundaries.
3. Map logging, audit, retention, and deletion behavior to tests.
4. Record uncertainty as a finding; do not invent a legal conclusion.

## Failure modes
- Logging sensitive values.
- Treating a role name as proof of authorization.
- Claiming regulatory compliance from code inspection alone.
```

Review and reapprove capabilities:

```bash
git diff -- .agents/skills/healthcare-privacy/SKILL.md
sdd project configure --file .sdd/workspace.yaml
sdd start --max-tasks 1
```

Tasks may explicitly name up to eight non-lifecycle skills. Missing or unsafe skills fail closed.

## 10. Prepare CI and a reviewed pull request

```bash
sdd project check
sdd docs check
sdd repo scaffold --owner @your-org/your-team
sdd pipeline export --provider github
git status --short
git add -A
git status --short
git commit -m "Add SDD CI and repository policy"
```

Configure the workspace repository section for GitHub before using hosted actions:

```yaml
repo:
  provider: github
  repository: your-org/your-repo
  base_branch: main
  protected_branches: [main, "release/*"]
  branch_prefix: sdd
  required_checks: [SDD checks]
  require_review: true
  allow_push: false
  allow_merge: false
  auto_commit: false
```

Reapprove and inspect host state:

```bash
sdd project configure --file .sdd/workspace.yaml
sdd project check
sdd repo audit-host
sdd repo pr --title "Implement requested feature" --body-file .github/pull_request_template.md
sdd repo pr-status 123
```

Only enable automated merge after the organization is comfortable with the host controls:

```bash
# Set allow_merge: true in the reviewed policy, then reapprove it.
sdd project configure --file .sdd/workspace.yaml
sdd repo merge 123
```

## 11. Build, deploy, and roll back an immutable release

The workspace policy must pair each build command with one artifact and define environment deploy/smoke/rollback hooks.

```bash
sdd project check
sdd release build 1.2.3
sdd release deploy 1.2.3 staging
sdd release deploy 1.2.3 production --approve
```

Rollback to a previously recorded successful version:

```bash
sdd release rollback 1.2.2 production --approve
```

If a timeout makes external state unknown:

```bash
sdd release reconcile production --outcome failed \
  --note "Operator verified that version 1.2.2 is still active"
```

Vega records receipts and digests; it does not provision clouds or make an unsafe universal deploy command.

## 12. Validate a portfolio of repositories

Create `portfolio.yaml`:

```yaml
repositories:
  - id: shared-library
    path: ../shared-library
    depends_on: []
  - id: api
    path: ../api
    depends_on: [shared-library]
  - id: web
    path: ../web
    depends_on: [api]
```

Run checks in dependency order:

```bash
sdd project portfolio-check --file portfolio.yaml
```

This aggregates local project checks. It is not an atomic multi-repository deployment transaction.

## Common decision guide

| Situation | Use |
| --- | --- |
| Need an answer, no mutation | `sdd ask` |
| Need a conversational diagnosis | `sdd intervene` |
| Found incorrect implementation | `sdd change "..."` |
| Want different approved behavior | Preview with `sdd change "..."`, then use the emitted `sdd change --approve-id CR-...` command |
| Run should stop safely | `sdd pause` |
| Task failed but code is useful | `sdd task retry ID --keep-code` |
| Old chat is gone | `sdd resume` |
| Provider should change | `sdd agent use NAME` |
| Human docs are stale | `sdd docs refresh --enrich` |
| Source graph is stale | `sdd graph refresh` |
| Canonical state needs a recovery point | `sdd recovery checkpoint` |

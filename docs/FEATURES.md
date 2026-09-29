# Vega SDD feature reference

This reference describes the capabilities available in Vega SDD 0.4.1. For an executable walkthrough, use the [user guide](USER_GUIDE.md) or [use-case journeys](USE_CASES.md).

## Product discovery and specification

### PRD-first initialization

`sdd init` accepts a normal Markdown/text PRD and performs product discovery, an architecture workshop, specification generation, and traceability validation. Users do not need to author a proprietary schema.

### Material clarification interview

Initialization records questions that can materially change behavior, scope, data, security, architecture, deployment, or operations. Answers survive agent sessions under `.sdd/product/`.

### Interactive architecture decisions

For every relevant decision, Vega presents context, credible options, tradeoffs, fit, and a recommendation. The user can select, ask a follow-up, provide another option, or defer. Selected decisions become ADRs and structured state.

### Stable requirements and acceptance criteria

Requirements have stable IDs, priority, source, and observable acceptance criteria. Features and tasks trace back to those IDs. `sdd verify` rejects missing or broken references.

### Feature and task dependency graph

Features and tasks declare dependencies. The scheduler selects only dependency-ready work and carries stable unaffected IDs through approved changes.

### New and existing systems

`--project-kind new` creates a greenfield plan. `--project-kind existing` adds a bounded, isolated source view and repository evidence so planning can account for current code without pre-approving repository agent instructions.

## Agent orchestration

### Supported primary adapters

- Cursor
- Codex
- Claude Code
- Gemini CLI
- GitHub Copilot CLI
- deterministic mock adapter

The primary agent can be changed without moving canonical state:

```bash
sdd agent use claude
```

### Bounded implementation

Each agent call receives one task, applicable acceptance criteria, a working set, recent findings, Graphify context when available, and the selected roles/skills. The controller, not the agent, chooses and advances lifecycle state.

### Isolated or distinct review and repair

After deterministic checks, a fresh review pass maps the implementation to acceptance criteria. By default this is isolated self-review in a new subprocess of the selected provider. Blocking findings enter a bounded repair loop. Low/warning findings that do not violate acceptance criteria are recorded without blocking.

Set a distinct provider when required:

```yaml
primary_agent: cursor
review_agent: claude
require_distinct_review_agent: true
```

### Single-writer control

Only one Vega controller writer runs for a repository/common Git directory at a time. Read-only questions and intervention calls are serialized around state-sensitive work. Linked worktrees share the lock.

### Foreground execution

`sdd start` remains in the foreground for visible events and predictable interruption. `sdd pause` and Ctrl+C request a stop at a task boundary. `sdd resume` reconstructs work from repository state.

## Skills and roles

### Progressive skill disclosure

Runbooks live under `.agents/skills/`. Prompts carry compact metadata and exact paths; the agent loads only selected skill bodies. This avoids injecting the full catalog into every task.

### Risk routing

Packaged runbooks cover:

- implementation and review;
- architecture and feature specification;
- API, data model, and UX design;
- security review and threat modeling;
- reliability and performance review;
- migration safety and E2E testing;
- AI/agent-system review;
- documentation, reconciliation, drift, and feature verification.

Routing metadata selects specialist skills by phase and bounded task text. Common auth/OAuth/OIDC/JWT/password, PII, encryption/KMS, payment, retry, timeout, migration, performance, E2E, and agent terminology is recognized.

### Project-specific skills

Tasks may name up to eight safe non-lifecycle skills. A missing, unsafe, oversized, or symlinked skill fails before execution. Project-local skill bodies remain outside initialization prompts until capability approval.

### Specialist roles

Planner, architect, developer, QA, security, spec, integration, reliability, performance, E2E, and agent-system perspectives are separate from permissions. Roles guide judgment; they do not grant tools or approve state changes.

## Verification and evidence

### Typed workspace policy

`.sdd/workspace.yaml` describes components, project kinds, dependency order, commands, waivers, builds, artifacts, repository policy, environments, timeouts, and protected paths.

Supported component kinds:

- web
- service
- library
- CLI
- data pipeline
- ML
- infrastructure
- mobile
- desktop
- embedded
- docs
- custom

Each kind requires appropriate named checks or substantive waivers.

### Deterministic checks

Commands execute as argv with timeouts and declared environment-variable names. Failures block task/release evidence before an AI reviewer can claim success. Full checks bind evidence to a source, policy, and capability fingerprint.

### Traceability

Vega validates requirement → acceptance criterion → feature → task → evidence links. Status separates specification, implementation, and verification progress.

### Evidence-aware review policy

Critical/high findings and security, data-loss, or integrity failures block. Medium findings block when they violate acceptance criteria. Reviewer confidence alone cannot override deterministic failures.

### Human and machine views

Markdown supports people and agent inspection. YAML/JSON supports validated state transitions. Generated views do not become canonical merely because someone edits the Markdown.

## Project intelligence

### Read-only project copilot

`sdd ask` answers from approved specs, ADRs, project state, and Graphify context. It cannot mutate the plan.

### Interactive architect

`sdd intervene` supports longer read-only diagnosis. Prefixing a prompt with `change:` previews classification/impact.

### Graphify retrieval

`sdd graph refresh` writes a deterministic SDD traceability corpus and builds/updates a local code graph when Graphify is installed. Queries merge corpus and code-graph results. `.sdd/state/` remains canonical.

### Headroom compression

Headroom optionally compresses context excerpts and check logs. Originals stay under `.sdd/runtime/originals/`; missing or ineffective compression never blocks work and does not create a token-stop policy.

## Change management

### Defect versus intent classification

`sdd change` separates implementation defects from spec defects, requirement changes, and architecture changes. Incorrect code becomes repair work instead of silently weakening the spec.

### Explicit intent approval

Requirement/architecture mutations show affected IDs and require `--approve-id CR-...` for the exact stored proposal. MCP change requests are preview-only.

### Conservative invalidation

Approved reconciliation preserves stable unaffected state, invalidates affected tasks/dependents, clears stale evidence, refreshes projections, and revalidates traceability.

Reconciliation uses bounded slice updates instead of returning the full spec bundle. The controller enforces the approved requirement/feature/task scope, rejects agent-authored runtime status and evidence, supports explicit scoped deletion, validates changed slices and global policies, rejects no-op application, includes staged input in fallback token estimates, and cleans up staged files after the call. A 300-second adapter timeout bounds the reconcile invocation.

### Clarifications and retry

`sdd clarify` resolves material questions. `sdd task retry --keep-code` requeues failed work without discarding the working tree.

## Human documentation and history

### Generated design pack

Applicable documents include system overview, HLD, LLD, database design, API design, security, operations, test plan, existing-system analysis, contributing, release plan, and traceability.

### Read-only enrichment

`sdd docs refresh --enrich` asks the selected agent to inspect code and approved intent without changing requirements/ADRs/task state. Structured output is validated before replacing design-document data.

### Human changelog and spec diffs

`.sdd/CHANGELOG.md` projects lifecycle events into readable history. Content-addressed snapshots and exact spec transitions live under `.sdd/history/specs/`.

### Commit attribution

Vega can link commits through exact `SDD-Task:` trailers or explicit `sdd link-commit`. It never treats an unrelated latest commit as task evidence.

## Delivery lifecycle

### Protected execution branches

`sdd repo branch` creates policy-named work branches and supports linked worktrees. Protected, detached, unborn, or dirty unsafe starts are rejected.

### Repository scaffolding

`sdd repo scaffold` adds missing CODEOWNERS/PR/issue/security/support/contribution starters without overwriting owner files.

### Hosted PR policy

GitHub and trusted command-provider hooks support PR creation, status, and merge. Merge checks expected head/base, draft state, review, mergeability, and required checks. Push/merge/auto-commit default off.

### Non-overwriting CI export

`sdd pipeline export` writes a frozen standalone checker and provider templates for GitHub, GitLab, or Azure. Existing files are preserved; `--update-generated` replaces only unchanged generated copies.

### Immutable releases and environment receipts

Builds hash configured artifacts and bind them to source/policy/check evidence. Deployment hooks receive a release manifest; they must deploy the recorded digest instead of rebuilding mutable source.

### Rollback and reconciliation

Deploy/smoke timeouts become unknown external state and block blind retry. `release reconcile` records an operator-confirmed outcome. Rollback targets a recorded prior successful version through an explicit project hook.

### Portfolio checks

`sdd project portfolio-check` runs dependency-ordered local checks across repositories. It does not claim atomic multi-repository deployment.

## Recovery and safety

### Durable pause/resume

Task/feature state, event journal, evidence, baselines, and recovery checkpoints let a new process or provider resume without an old conversation.

### Projection transactions

Canonical multi-file projections use rollback snapshots. Corrupt or incomplete transaction evidence fails closed and remains available for inspection.

### Read-only restoration

Read-only agent calls restore accidental source content/mode changes and Git HEAD, refs, index, config, and hooks, including linked-worktree common metadata.

### Capability approval

Real-agent execution binds approval to workspace policy and provider-visible instructions/settings/skills/context filters. Changes invalidate approval until reviewed and reconfigured.

### Bounded snapshots/catalogs

Repository snapshots, source views, and skill/capability catalogs have explicit count/byte limits to prevent unbounded memory use. Snapshot limits can be deliberately raised with `SDD_GUARD_MAX_FILES`, `SDD_GUARD_MAX_BYTES`, and `SDD_GUARD_MAX_FILE_BYTES`.

### Honest boundary

The guard detects/restores repository mutations; it is not an OS sandbox. Provider sandboxing, credentials, network policy, secret handling, host branch protection, and application-specific controls remain required.

## Tested examples

The 0.4.1 suite covers 228 tests, Python 3.11/3.12 CI, wheel/sdist builds, an incident-service lifecycle benchmark, and Python library, CLI, SQLite pipeline, and Node web cross-project benchmarks. See [verification evidence](VERIFICATION_0.4.1.md).

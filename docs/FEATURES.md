> **Vega SDD 0.3.0:** This guide describes the framework behavior; see [project lifecycle](PROJECT_LIFECYCLE.md) for current delivery policies and [verification](VERIFICATION_0.2.0.md) for the original 0.2.0 test baseline. Version-specific notes below are historical.

# v0.1.2 update

Human HLD/LLD/database/API/operations documentation, human changelog, spec revision diffs and Git attribution are now available. See [full documentation and commands](HUMAN_DOCUMENTATION.md).

> **0.1.1 audit status:** Experimental controller. See the [verification report](VERIFICATION_REPORT.md) for tested behavior, defects repaired, missing features, and live-provider limitations. Earlier broad descriptions below are not certification.

# Vega SDD Feature Reference

This document is a feature reference inherited from the 0.1.0 release; consult the project lifecycle guide for newer capabilities. It explains what each capability does, why it exists, and how to use it effectively.

## 1. PRD-first initialization

**Command:** `sdd init`

A project may begin with only a normal Markdown/text PRD. No proprietary YAML authoring format is required from the user.

Initialization performs four stages:

1. product discovery,
2. architecture workshop,
3. specification generation,
4. readiness/traceability validation.

**Best use:** Make the PRD clear about users, major workflows, business rules, non-negotiables, and out-of-scope behavior. It does not need technology choices unless those are already constraints.

**Existing projects:** use `--project-kind existing`. The initializer samples repository structure and Git state so generated specs do not pretend the PRD is the only source of current reality.

## 2. Material clarification interview

During product discovery the selected agent returns only questions that can materially affect product behavior, data model, security, architecture, deployment, or scope. SDD records answers in `.sdd/product/clarifications.md` and feeds them into subsequent design.

**Best use:** answer behavior/scope questions during init. Engineering details that can be safely delegated should remain autonomous.

## 3. Interactive architecture workshop

Architecture decisions are generated specifically for the project. The system should not ask about Kafka, a vector database, GPU infrastructure, etc. unless requirements make them relevant.

For each decision SDD presents:

- decision context,
- 2–5 credible options,
- fit,
- summary/tradeoffs,
- an architect recommendation and rationale,
- choices to accept, ask the architect, select another option, or defer.

Approved selections are written as ADR-style files in `.sdd/decisions/` and structured state in `.sdd/state/architecture-decisions.yaml`.

**Best use:** treat recommendations as decision support, not automatic truth. The user remains the final authority for consequential technology choices.

## 4. Current-option architecture research boundary

Architecture prompts direct capable coding agents to compare current, production-grade options. The SDD core does not hard-code "FastAPI is always best" or an eternal cloud matrix.

**Best use:** use an agent with web/research access during initialization when current market comparison matters. Record explicit organizational constraints in the PRD or clarifications.

## 5. Stable structured requirements

Generated requirements have stable IDs, type, priority, source, and testable acceptance criteria. They are persisted in both human-readable Markdown and machine-readable YAML.

**Best use:** avoid manually renumbering IDs. Changes should go through `sdd change` so impact and stale evidence can be handled deliberately.

## 6. Feature decomposition and dependency DAG

Features contain requirements, dependencies, bounded tasks, and verification criteria. The development scheduler selects only work whose feature/task dependencies are verified.

**Best use:** tasks should be small enough for a bounded coding-agent run. If a generated task is broad, refine it before implementation rather than relying on one huge session.

## 7. Project-owned Agent Skills

`/.agents/skills/` is canonical. Core runbooks cover implementation, review, feature specs, architecture, API, UX, data model, threat model, docs, and security review. Each file has a routing description, a directory map, a procedure, a checklist, and failure modes.

The controller injects the skill name and description. The agent loads the matching `SKILL.md` on demand.

**Best use:** add project/domain-specific skills here (for example `database-migration`, `fastapi-api`, `terraform-module`, or `hipaa-data-handling`) rather than bloating `AGENTS.md`. Run `sdd scaffold` to install missing framework skills.

## 8. Project-owned specialist roles

`/.agents/roles/` defines architect, developer, QA, security, spec, and integration reviewer responsibilities. Thin copies/adapters are materialized for supported coding-agent conventions.

**Best use:** keep role definitions narrow. Review roles should not inherit a long developer conversation as authority; they should inspect spec, diff, tests, and evidence.

## 9. Vendor-neutral primary agent

The configured agent lives in `.sdd/config.yaml` and can be changed with:

```bash
sdd agent use cursor
sdd agent use codex
sdd agent use claude
sdd agent use gemini
sdd agent use copilot
```

Specs and state do not move.

**Best use:** switch agents at a clean task boundary when practical. Run `sdd doctor` after moving to a new workstation/toolchain.

## 10. Capability doctor

**Command:** `sdd doctor`

Detects supported CLIs and reports key adapter capabilities such as structured output, streaming, resume, and interruption support. It also reports whether the `graphify` CLI and the Headroom Python package are installed.

**Best use:** run before first initialization and whenever an agent CLI is upgraded substantially.

## 11. Autonomous task execution

**Command:** `sdd start`

The controller:

1. validates traceability,
2. selects the next ready task,
3. persists current state,
4. invokes the primary coding agent with a bounded task prompt,
5. records implementation completion,
6. runs configured deterministic checks,
7. invokes independent review,
8. auto-repairs failed reviews up to the configured limit,
9. records verification evidence,
10. publishes progress,
11. advances to the next ready task.

**Best use:** configure real test/lint/typecheck commands before long autonomous runs.

## 12. Independent review and bounded auto-repair

The implementation pass is not trusted to self-certify. A separate review prompt compares current diff/implementation against the task specification. Failures enter an auto-repair loop capped by `max_repair_attempts`.

**Best use:** keep repair caps modest (default 3). Repeated failure usually indicates ambiguity, architectural mismatch, or a defect needing human intervention—not a reason to loop forever.

## 13. Deterministic verification hooks

Configuration fields:

```yaml
test_command: null
lint_command: null
typecheck_command: null
```

When set, these execute after implementation. Failures block the task before an LLM reviewer can call it complete.

**Best use:** make commands deterministic, non-interactive, scoped to the repository, and suitable for repeated execution.

## 14. Requirement traceability validation

**Command:** `sdd verify`

Checks that:

- MUST requirements belong to a feature,
- MUST requirements map to implementation tasks,
- referenced requirement/feature/task IDs exist,
- dependency links point to real items,
- tasks expose verification criteria,
- requirements have acceptance criteria (error if missing).

**Best use:** run after any manual edit under `.sdd/`, and in CI for repositories that adopt the framework deeply.

## 15. Durable progress status

**Commands:** `sdd status`, `sdd watch`

Progress is derived from canonical state, not from an agent's narrative. Separate specification, implementation, and verification progress are shown.

`STATUS.md` is also published into `.sdd/` for easy inspection and versioning.

## 16. Safe pause and resume

**Commands:** `sdd pause`, `sdd resume`

`pause` requests a safe task-boundary stop. Ctrl+C during a foreground run also transitions canonical state to paused. `resume` reconstructs work from `.sdd/state/` and does not require the prior chat.

**Best use:** deliberately start fresh agent contexts on long projects. Durable state is designed to make clearing conversational context healthy rather than dangerous.

## 17. Recovery of implemented-but-not-reviewed work

If a process ends after a task is marked `implemented` but before review, the scheduler can select the task again and resume at verification rather than blindly reimplementing it.

**Best use:** do not manually flip task statuses. Let recovery semantics preserve evidence and avoid duplicate work.

## 18. Architect intervention shell

**Command:** `sdd intervene`

Starts a read-only architecture conversation grounded in current product, architecture, roadmap, status, and specs. It is intended for questions such as:

- Why is Redis here?
- Is this implementation following the approved auth flow?
- Which spec defines this behavior?
- What would be affected if we changed X?

Prefix an intervention with `change:` to classify a concern without applying it.

## 19. Problem/change classification

**Command:** `sdd change "description"`

The architect classifies the concern as implementation defect, spec defect, requirement change, architecture change, or unknown and returns affected IDs plus proposed action.

This prevents a common failure mode: changing the specification to match incorrect code.

## 20. Auto-repair for implementation defects

If the existing spec is correct, the controller creates a repair task under the affected feature. No product/spec approval is required because intent is unchanged.

**Best use:** report observed behavior precisely. The classifier can then compare it against acceptance criteria instead of guessing the desired result.

## 21. Explicit approval for intent mutation

Spec, requirement, and architecture changes require approval. Use an interactive confirmation or `--approve` for an already reviewed change.

The reconciliation step requests a structured revised bundle, preserves stable IDs/status for unaffected work, invalidates affected task evidence, rewrites generated views, and reruns traceability.

**Best use:** review the printed impact before approval. The framework deliberately does not hide consequential changes inside autonomous implementation.

## 22. Append-only event journal

**Command:** `sdd log`

`.sdd/journal/events.jsonl` records initialization, run starts, task transitions, checks, review failure/repair, pause, changes, and completion.

**Best use:** use the journal for debugging/recovery and future analytics. Do not rewrite history to make a run look cleaner.

## 23. Human-readable and machine-readable dual artifacts

Humans get Markdown ADRs/specs/status. The scheduler gets structured YAML. This avoids forcing people to read machine state while also avoiding fragile Markdown parsing for core orchestration.

## 24. Thin vendor adapters

The repo creates compatibility surfaces for Cursor/Claude/Codex while keeping canonical methodology under `.sdd/` and `.agents/`.

**Best use:** do not hand-maintain different product rules in `.cursor`, `.claude`, and `.codex`. Tool-specific files should point back to the shared contract.

## 25. Foreground execution in V1

V1 intentionally runs `sdd start` in the foreground. This makes interrupts and terminal visibility predictable. `sdd watch` is useful when another process/terminal is performing updates, but a durable daemon is not yet part of V1.

A later release can add detached execution without changing project-state semantics.

## 26. One primary writer in V1

V1 does not allow multiple concurrent implementation agents to edit the repo. That is intentional: it avoids merge/worktree/dependency races while still allowing independent review passes through the selected agent.

The task DAG is designed so parallel workers can be added later behind explicit worktree/merge coordination.

## 27. Graphify retrieval

**Commands:** `sdd graph refresh`, `sdd graph query`

Graphify is an external local knowledge graph. `sdd graph refresh` writes `graphify-corpus/sdd-traceability.md`, then runs `graphify extract --code-only --no-cluster` or `graphify update` when `graphify-out/graph.json` already exists. Context packs and `sdd ask` query that graph before agents grep the tree.

`.sdd/state/` stays the execution record. If `graphify` is missing, the controller uses the task working-set file list.

## 28. Headroom compression

Headroom compresses context-pack excerpts, spec slices, and check logs before they enter implement, review, repair, and ask prompts. Originals remain under `.sdd/runtime/originals/`. `sdd status` shows raw versus compressed size. Compression never fails a task, and there is no token cap that pauses a run.

## 29. Project copilot and classified changes

**Commands:** `sdd ask`, `sdd change`, `sdd clarify`, `sdd task retry`

`sdd ask` answers from specs, ADRs, and Graphify without mutating the plan. `sdd change` classifies a request. Implementation defects can become repair tasks. Requirement and architecture changes print the invalidated tasks and wait for approval (`--approve` or the confirmation prompt). `sdd clarify` records answers that unblock `sdd start`. `sdd task retry --keep-code` puts a failed task back on the scheduler without discarding the working tree.

Review fails a task only for critical, high, or medium findings that violate acceptance criteria. Low and warning findings are recorded and do not block. Task checks prefer the task's own paths; the full suite runs at feature end.

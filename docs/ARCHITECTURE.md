> **Vega SDD 0.3.0:** This guide describes the framework behavior; see [project lifecycle](PROJECT_LIFECYCLE.md) for current delivery policies and [verification](VERIFICATION_0.2.0.md) for the original 0.2.0 test baseline. Version-specific notes below are historical.

> **0.1.1 audit status:** Experimental controller. See the [verification report](VERIFICATION_REPORT.md) for tested behavior, defects repaired, missing features, and live-provider limitations. Earlier broad descriptions below are not certification.

# Vega SDD Architecture

## System shape

```text
User
  │
  ▼
SDD CLI / Control Plane
  ├── Product discovery
  ├── Architecture decision workflow
  ├── Spec generator
  ├── State engine
  ├── Dependency scheduler
  ├── Verification/review loop
  ├── Change classifier/reconciler
  └── Event journal
        │
        ▼
AgentAdapter
  ├── CursorAdapter
  ├── CodexAdapter
  ├── ClaudeAdapter
  └── MockAdapter
        │
        ▼
Repository
  ├── Product/spec/ADR artifacts
  ├── Application code/tests
  └── Durable execution evidence
```

## Ownership boundaries

The controller owns canonical state transitions. An agent may edit application code during writable tasks, but it is instructed not to mark `.sdd/state` complete. This protects recovery from agent self-reporting.

Architecture/spec generation is returned as structured JSON and validated with Pydantic before the controller writes canonical artifacts. Approved change reconciliation uses the same pattern.

## State model

`ProjectState` tracks run state, active run, current feature/task, pause/stop requests, and initialization status.

Each `Feature` contains task state. Each `Task` has stable identity, dependency links, requirement mappings, verification criteria, attempt count, and evidence IDs.

The event journal is append-only and supplements (but does not replace) current-state YAML.

## Scheduler

A feature is runnable only after all feature dependencies are verified. A task is runnable only after all task dependencies are verified. The scheduler scans the ordered feature list and selects the first ready task.

V1 deliberately uses a single writer. This avoids concurrent edit conflicts and lets the repo/task DAG mature before parallel worktree orchestration is added.

## Verification flow

```text
implementation
  ↓
configured test/lint/typecheck
  ↓
independent reviewer
  ↓ fail
repair agent ──┐
  └────────────┘ (bounded retries)
  ↓ pass
verified task + evidence
```

Deterministic checks have priority over LLM confidence. A failing configured command blocks review completion.

## Change safety

The classifier separates implementation defects from intent changes. Implementation defects become new repair tasks. Intent changes require explicit approval and structured reconciliation.

During reconciliation, stable unaffected task IDs carry forward their execution status. Explicitly invalidated tasks lose evidence and return to incomplete state. Traceability is validated before development resumes.

## Security model

Vega SDD executes local coding-agent CLIs with the permissions configured for those tools. It does not store provider API keys itself. Secrets remain under the coding agent/vendor's authentication mechanism and local environment.

The framework cannot make a permissive coding-agent configuration safe. Use each provider's sandbox/approval controls and least-privilege credentials appropriate for the repository.

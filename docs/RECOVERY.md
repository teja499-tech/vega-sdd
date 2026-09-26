> **Vega SDD 0.3.0:** This guide describes the framework behavior; see [project lifecycle](PROJECT_LIFECYCLE.md) for current delivery policies and [verification](VERIFICATION_0.2.0.md) for the original 0.2.0 test baseline. Version-specific notes below are historical.

> **0.1.1 audit status:** Experimental controller. See the [verification report](VERIFICATION_REPORT.md) for tested behavior, defects repaired, missing features, and live-provider limitations. Earlier broad descriptions below are not certification.

# Recovery and Context Hygiene

## Context is disposable; repository state is not

A core design goal is that a coding-agent conversation can be cleared or replaced without losing project position.

The minimum recovery inputs are:

- `AGENTS.md`,
- `.sdd/config.yaml`,
- current product/architecture/spec artifacts,
- `.sdd/state/*`,
- `.sdd/journal/events.jsonl`,
- current Git working tree/diff.

## Clean resume

```bash
sdd status
sdd log --limit 30
sdd resume
```

The orchestrator will select the next dependency-ready task. If a task was implemented but review did not finish, it is eligible for verification recovery rather than automatic duplicate implementation.

## After a machine/process failure

1. Inspect Git status.
2. Run `sdd status`.
3. Inspect `sdd log` for the last task transition.
4. Run `sdd verify`.
5. If the current code/spec relationship is unclear, run `sdd intervene` before resuming.

## Do not repair state by hiding evidence

Avoid manually marking a task verified just because its code appears present. Verification state should correspond to deterministic checks/reviewer evidence.

## Switching tools

At a task boundary:

```bash
sdd agent use <new-agent>
sdd doctor
sdd resume
```

The new agent does not need access to the old agent's conversation.

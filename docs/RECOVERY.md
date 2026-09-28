# Recovery and Context Hygiene

This guide covers Vega SDD 0.4.0 recovery. See [use-case journeys](USE_CASES.md#5-resume-or-recover-work) for copy/paste recipes and [architecture](ARCHITECTURE.md) for integrity boundaries.

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

Copy/paste sequence:

```bash
git status --short
sdd status
sdd log --limit 50
sdd verify
sdd resume
```

## Checkpoints

Verified tasks create checkpoints automatically. Create one manually before a risky owner-operated change:

```bash
sdd recovery checkpoint
```

Restore by the printed identifier:

```bash
sdd recovery restore CHECKPOINT-ID
sdd status
sdd verify
```

Restore preserves application code. It restores canonical SDD state, pauses execution, invalidates stale task/check evidence, and removes stale lifecycle progress. It does not undo Git history, deployments, databases, queues, object storage, or any other external side effect.

## Projection recovery

Multi-file generated projections use a durable rollback snapshot under `.sdd/runtime/projection-tx/`. If a prior write stopped halfway, the next serialized mutation restores the snapshot before continuing.

If the marker or snapshot is corrupt/incomplete, Vega fails closed and preserves the transaction evidence. Do not delete it reflexively. Back up the repository, inspect `.sdd/runtime/projection-tx/`, compare canonical files with Git and `.sdd/history/`, then repair or remove the transaction only after deciding which state is authoritative.

## Read-only mutation recovery

Read-only agent calls snapshot and restore source content/file modes plus Git HEAD, refs, index, config, and hooks. Linked worktrees include common Git metadata. A detected Git or protected-controller mutation fails the call after restoration.

This is an integrity backstop, not secret or network containment. A privileged process may read/transmit data before a file can be restored.

## Large repositories

Default read-only snapshot limits fail before agent launch rather than risk unbounded memory. Operators may raise them deliberately for a sufficiently provisioned host:

```bash
export SDD_GUARD_MAX_FILES=50000
export SDD_GUARD_MAX_BYTES=1073741824
export SDD_GUARD_MAX_FILE_BYTES=268435456
sdd start --max-tasks 1
```

Values are positive integers. `SDD_GUARD_MAX_BYTES` and `SDD_GUARD_MAX_FILE_BYTES` are byte counts.

## Do not repair state by hiding evidence

Avoid manually marking a task verified just because its code appears present. Verification state should correspond to deterministic checks/reviewer evidence.

## Switching tools

At a task boundary:

```bash
sdd agent use claude
sdd doctor
sdd resume
```

The new agent does not need access to the old agent's conversation.

## Recovery checklist

- Preserve the working tree and `.sdd/` before manual repair.
- Read the last journal events rather than inferring state from filenames.
- Do not manually mark tasks verified.
- Re-run `sdd verify` after any canonical-state intervention.
- Re-run `sdd project check` before PR or release operations.
- Reconcile unknown external deployment state before retrying.
- Keep independent repository, artifact, database, and environment backups.

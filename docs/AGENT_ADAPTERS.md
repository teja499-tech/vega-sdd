> **Vega SDD 0.3.0:** This guide describes the framework behavior; see [project lifecycle](PROJECT_LIFECYCLE.md) for current delivery policies and [verification](VERIFICATION_0.2.0.md) for the original 0.2.0 test baseline. Version-specific notes below are historical.

> **0.1.1 audit status:** Experimental controller. See the [verification report](VERIFICATION_REPORT.md) for tested behavior, defects repaired, missing features, and live-provider limitations. Earlier broad descriptions below are not certification.

# Agent Adapters

Adapters isolate vendor-specific command syntax from SDD lifecycle semantics.

## Contract

An adapter reports capabilities and implements a bounded `run` operation plus interruption. Core orchestration supplies:

- prompt/role intent,
- whether the operation may write,
- requested mode,
- repository working directory,
- event callback.

The adapter returns normalized `AgentResult`/`AgentEvent` objects.

## Cursor

The adapter targets Cursor CLI's `agent` command, print mode, structured JSON output, explicit workspace, and Ask/Plan modes for read-only operations.

Writable tasks rely on Cursor's configured sandbox/approval behavior. Run `sdd doctor` after major CLI updates.

## Codex

The adapter uses bounded `codex exec --json` jobs. Writable implementation explicitly uses `--sandbox workspace-write`; read-only/review uses `--sandbox read-only`. Provider approvals still apply.

A future deeper integration can replace the CLI adapter with Codex SDK/app-server while leaving the SDD controller/state contract unchanged.

## Claude Code

The adapter uses non-interactive print mode with stream JSON. Plan permission mode is used for read-only work and accept-edits for writable tasks.

Because vendor flags can evolve, the adapter is intentionally small and covered by command-shape tests.

## Mock

The mock adapter returns deterministic structured responses and powers the repository's end-to-end tests. It should never be chosen for real application development.

## Adding another coding agent

Implement `AgentAdapter`, map capability detection and bounded read/write command construction, then register it in `get_adapter`. Do not add vendor-specific project state fields unless the core contract truly requires them.

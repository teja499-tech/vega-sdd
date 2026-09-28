> **Vega SDD 0.4.0:** Gemini CLI and GitHub Copilot CLI are primary adapters. `python -m universal_sdd.mcp_server` exposes `sdd_ask`, `sdd_status`, and `sdd_change`. Prompts include skill metadata only; runbooks stay in `.agents/skills/`.

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

The adapter targets Cursor CLI's `agent` command, print mode, structured JSON output, explicit workspace, `--trust` (required for non-interactive workspace confirmation), `--model auto`, and Ask/Plan modes for read-only operations.

`--trust` confirms the workspace. Writable runs add `--force` only when the project owner sets `allow_unrestricted_agent: true` in `.sdd/config.yaml` or passes `sdd start --allow-unrestricted`. That is an isolation opt-in, not the default. Run `sdd doctor` after major CLI updates.

## Codex

The adapter uses bounded `codex exec --json` jobs. Writable implementation explicitly uses `--sandbox workspace-write`; read-only/review uses `--sandbox read-only`. Provider approvals still apply.

A future deeper integration can replace the CLI adapter with Codex SDK/app-server while leaving the SDD controller/state contract unchanged.

## Claude Code

The adapter uses non-interactive print mode with stream JSON. Plan permission mode is used for read-only work and accept-edits for writable tasks.

Because vendor flags can evolve, the adapter is intentionally small and covered by command-shape tests.

## Gemini CLI

The adapter targets the `gemini` CLI one-shot `-p` prompt. Restricted writable implement/repair uses `--sandbox --approval-mode auto_edit` so file edits inside the workspace can proceed without granting shell/network auto-approval. `--yolo` is added only after the unrestricted-agent opt-in. Read-only review/ask adds `--sandbox`.

## GitHub Copilot CLI

The adapter targets `copilot -p` with `--silent --no-ask-user`. Restricted writable runs pass `--allow-tool write` plus scoped `--allow-tool shell(<command>:*)` prefixes taken from the approved test/lint/typecheck and workspace check commands. Bare interpreters (`python`, `node`, `bash`) and generic `shell` are not granted. `--allow-all` is added only after the unrestricted-agent opt-in; review/ask omit write approvals. The controller still re-runs deterministic checks.

Set `review_agent` in `.sdd/config.yaml` to use a different installed adapter for independent review. When unset, review is isolated self-review: a fresh subprocess of the primary agent, not an independent model. `require_distinct_review_agent: true` blocks start until a different reviewer is configured.

## IDE copilot (optional MCP)

`python -m universal_sdd.mcp_server` exposes `sdd_ask`, `sdd_status`, and `sdd_change` over stdio JSON-RPC. `sdd_change` is preview-only; an IDE model cannot approve or apply a specification mutation. A human runs `sdd change --approve` after reviewing the invalidated-task list. Scaffolded Cursor commands live in `.cursor/commands/sdd-ask.md` and `sdd-change.md`.

## Mock

The mock adapter returns deterministic structured responses and powers the repository's end-to-end tests. It should never be chosen for real application development.

## Adding another coding agent

Implement `AgentAdapter`, map capability detection and bounded read/write command construction, then register it in `get_adapter`. Do not add vendor-specific project state fields unless the core contract truly requires them.

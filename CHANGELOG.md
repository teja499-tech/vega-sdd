# Changelog

This file summarizes human-visible changes. Individual project specifications and commit links are recorded in the managed project's own change history.

## [Unreleased]

- Keep failed `sdd init` unmarked as initialized and allow a non-destructive rerun without `--force`.
- Execute owner test commands as argv (`shell=False`) and reject model `check_paths` that leave the repo or include shell metacharacters.
- Gate Cursor `--force`, Gemini `--yolo`, and Copilot `--allow-all` behind `allow_unrestricted_agent` or `sdd start --allow-unrestricted`.
- Make the MCP `sdd_change` tool preview-only so an IDE model cannot mint approval.
- Generate README and developer-guide text without assuming Ollama or OpenRouter.

## [0.4.0] - 2026-09-27

- Removed per-task and per-run token caps. A run records raw versus compressed size in `.sdd/state/compression-ledger.yaml` and does not pause because an estimate crossed a budget.
- Added Graphify retrieval. `sdd graph refresh` writes `graphify-corpus/sdd-traceability.md` and runs `graphify extract --code-only --no-cluster`, then `graphify update` on later refreshes. Context packs and `sdd ask` call `graphify query`. Missing Graphify falls back to the task working set.
- Added optional Headroom compression for context packs, spec slices, and check logs. Originals stay under `.sdd/runtime/originals/`. Missing Headroom keeps the compact text and does not block.
- Rewrote core skills into on-disk runbooks with routing frontmatter, directory maps, procedures, and failure modes. Prompts carry the skill name and description; the agent loads `.agents/skills/<name>/SKILL.md`.
- Review fails only on critical, high, or medium findings that violate acceptance criteria. Task checks prefer `check_paths` and run the full suite at feature end.
- Added `sdd ask`, `sdd change`, `sdd clarify`, `sdd task retry`, and `sdd scaffold`. Unresolved material clarifications block `sdd start` unless `--accept-deferred`. Failed tasks stay out of the scheduler until retry.
- Added Gemini and GitHub Copilot adapters, and an optional MCP server (`python -m universal_sdd.mcp_server`) with `sdd_ask`, `sdd_status`, and `sdd_change`.
- Spec generation rejects title-only features: summaries, invariants, test matrices, and API or UX contracts are required when the feature touches those surfaces.
- Taskline AI stress check: `graphify extract --code-only` built `graphify-out/graph.json` (3,667 nodes, 16,606 edges). A query for task creation returned `create_task()` in `app/planning/service.py`. Headroom left a 20,001-character passing pytest log unchanged and saved 20 characters on a 7,677-character context pack; the controller keeps the original when the on-disk pointer would erase that saving. `sdd ask` named `create_task()` and `tests/test_task_lifecycle.py`. `sdd change` previewed a requirement change and stayed unapproved. `sdd doctor` reported Graphify and Headroom installed and Cursor 2026.09.26 available. Change analysis uses ask mode and retries once when the agent returns prose.
- Restore source files after a read-only review/ask agent mutates the tree, instead of aborting the run with `Read-only agent changed source`.
- Pass `--model auto` on every Cursor print-mode invocation so SDD uses Cursor Auto rather than a pinned vendor model.
- Restore generated `.sdd/docs/` and changelog/status projections without failing the run; still fail closed on canonical `.sdd/state` and spec mutations.
- Set `CURSOR_RECORD_SESSION=1` on Cursor adapter runs so login zsh from `agent shell-integration` does not `exec agent record` and deadlock implement/repair.
- Prefer the JSON object that matches the expected schema when Cursor embeds an inner product object before the full spec bundle (`parse_structured`).
- Parse Cursor init JSON in ask mode (plan mode was returning analysis prose), unwrap double-encoded `result` strings, persist failed agent output under `.sdd/runtime/`, and retry structured init calls once.
- Pass `--trust` on every Cursor print-mode invocation and `--force` on writable implement/repair so non-interactive SDD runs do not die on workspace-trust or command-approval prompts.
- Fixed Cursor real-run failures found during Taskline AI acceptance: unwrap object-shaped `result` envelopes in `CursorAdapter.final_text`, redact the prompt correctly in `AgentResult.raw` (it was leaking for Cursor), and return a structured launch failure instead of crashing on OS argv limits.
- Narrowed the controller guard to `.cursor/agents/` and `.cursor/rules/` so normal Cursor CLI cache/transcript writes under `.cursor/` no longer fail runs; scaffold-managed rules remain protected.
- Stopped telling the implement agent to create commits/`SDD-Task` trailers; the controller owns Git attribution and the guard rejects HEAD/index mutation.
- Changed `sdd init --yes` and the interactive prompt default from codex to cursor, and corrected USER_GUIDE to require `sdd project setup`, a committed baseline, and `sdd repo branch` before `sdd start` for real agents.

## [0.3.1] - 2026-09-26

- Fixed the project links in the PyPI long description so docs and repository policies open on GitHub.
- Rebuilt and retested the distribution through GitHub Actions.

## [0.3.0] - 2026-09-26

- Adopted **Vega SDD** as the public name and `vega-sdd` as the distribution; kept the `sdd` CLI and the compatible `universal_sdd` Python import.
- Reworked the public README, contributing guide, security policy, issue and PR templates, CI matrix, and release instructions.
- Carried forward 0.2.0 project kinds, human design documents, task/commit history, repository delivery gates, and release evidence.
- The package is still an alpha; live agent and hosted deployment qualification is pending.

## [0.2.0] - 2026-09-26

- Added typed project and check policies for 12 project kinds, Git and PR delivery gates, generated CI templates, immutable builds and environment receipts, state checkpoints and a resumable lifecycle.
- Continued human design documents and commit-linked history from 0.1.2.
- See [0.2.0 verification](docs/VERIFICATION_0.2.0.md) for the original rebuilt-package test evidence.

## [0.1.2] - 2026-09-26

- Added indexed human design documents and task/commit-linked change history.

## [0.1.1] - 2026-09-25

- Added test and recovery hardening, including the deterministic subprocess lifecycle benchmark.

## [0.1.0] - 2026-09-25

- Added PRD-first initialization, requirements, architecture workshop, agent adapters, traceability, bounded tasks, checks, review, repair and durable state.

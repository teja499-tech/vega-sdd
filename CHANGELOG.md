# Changelog

This file summarizes human-visible changes. Individual project specifications and commit links are recorded in the managed project's own change history.

## [0.4.0] - 2026-09-27

- Reorganize documentation around executable user journeys: add ChatGPT/Claude-assisted PRD discovery, greenfield/brownfield/defect/change/recovery/monorepo/delivery recipes, an exact CLI command reference, current sample output, a documentation index, and 0.4.0 verification evidence.
- Add a discoverable capability registry: tasks can name up to eight safe project/domain skills, routing metadata selects risk-specific runbooks, and context packs include developer/QA plus specialist role contracts through progressive disclosure.
- Add reliability, performance, E2E, migration-safety, and agent-system runbooks inspired by ECC's strongest composable-skill patterns; keep lifecycle authority and permissions in the controller.
- Bind real-agent workspace approval to `AGENTS.md`, roles, and skill contents so changed project-local instructions cannot execute under an old approval.
- Keep project-local skill bodies out of initialization prompts before approval; only safe names are visible unless the skill is packaged with Vega.
- Run initialization agents in an isolated, framework-owned workspace so unapproved repository instructions cannot be auto-loaded; require current capability approval for every later real-agent entry point.
- Give brownfield initialization a bounded source copy with instruction and secret files removed; fail closed on corrupt projection journals, serialize intervention calls, and restore file modes, Git refs, config, and hooks after read-only agents.
- Cover Copilot/Gemini repository capability directories and context filters, plus linked-worktree common Git metadata; make read-only snapshot bounds operator-configurable with explicit environment limits.
- Protect `.sdd/runtime` task baselines and projection journals from agent mutation; reject unsafe/symlinked recovery paths.
- Restore the original Git ref before resetting its commit so a read-only agent branch switch cannot rewrite the visited branch; replace the captured index atomically.
- Serialize scaffold, graph refresh, clarification, ask, and change-analysis operations through the project lock while preserving the out-of-band pause signal.
- Make successful real-agent initialization print the complete next path: inspect specs, configure project checks, commit the baseline, create an execution branch, then run one task.

- Keep failed `sdd init` unmarked as initialized and allow a non-destructive rerun without `--force`.
- Execute owner test commands as argv (`shell=False`) and reject model `check_paths` that leave the repo or include shell metacharacters.
- Gate Cursor `--force`, Gemini `--yolo`, and Copilot `--allow-all` behind `allow_unrestricted_agent` or `sdd start --allow-unrestricted`. Restricted writable Gemini uses `--sandbox --approval-mode auto_edit`; Copilot allows the write tool only.
- Make the MCP `sdd_change` tool preview-only so an IDE model cannot mint approval.
- Generate README and developer-guide text without assuming Ollama or OpenRouter.
- `--accept-deferred` now writes a real architecture default/option onto the decision and ADR, and rejects items with no default. Spec-phase open questions are merged into the clarification gate before init is ready.
- Critical/high and security/data-loss/integrity findings always block; `violates_ac=false` cannot waive them.
- Review packs are rebuilt from tracked and untracked files that actually changed. Lifecycle skills are selected by phase. Optional `review_agent` selects a separate reviewer.
- Every agent call, including `sdd ask`, change analysis, init, and docs enrichment, goes through the mutation guard.
- Graphify queries always merge a deterministic search of `graphify-corpus/sdd-traceability.md` with the code graph.
- Headroom runs in a timed subprocess, trips a circuit after repeated failures, and can be disabled with `enable_headroom: false` or `SDD_DISABLE_HEADROOM=1`.
- `write_spec_bundle` is an artifact projection and no longer resets lifecycle state.
- Architecture answers reject placeholders; `--accept-deferred` validates every default before committing decisions and clarifications together.
- Canonical artifact writes use a rollback journal so a failed `apply_change` cannot leave a half-written spec.
- Successful init saves ready state before publishing `STATUS.md`.
- Read-only guards restore protected files, source, and Git metadata before raising.
- Pre-task file baselines persist across crash recovery so review sees files created before `task_implemented`.
- Repair prompts load the repair/implementation skill; `verify-feature` is a controller contract, not an agent invocation.
- Graphify reserves a corpus budget so a large code-graph response cannot drop REQ/TASK/ADR hits.
- Copilot restricted runs add `--no-ask-user` and scoped `shell(<approved-check>)` tools; generic shell stays off.
- Brownfield init sends size-capped evidence excerpts, hashes, a pre-init Graphify query, and an omitted-file note.
- Review fails closed when the actual change set exceeds `max_review_files` instead of silently dropping files.
- Read-only Git restore now snapshots the index file, so staged owner work is not reset to `HEAD`.
- Task baselines are cleared only after verified task state is saved.
- Canonical projection writes persist a rollback snapshot first and recover it after a crash or `BaseException`.
- Copilot shell grants are command prefixes (`shell(pytest:*)`); bare interpreters are refused.
- Feature verification maps each requirement to passing evidence IDs before the suite result can certify the feature.
- `require_distinct_review_agent` blocks start unless review uses a different adapter; the default is isolated self-review.
- Graphify extract stays `--code-only`. Vega searches `graphify-corpus/sdd-traceability.md` itself and keeps query output within the caller limit.


- Removed per-task and per-run token caps. A run records raw versus compressed size in `.sdd/state/compression-ledger.yaml` and does not pause because an estimate crossed a budget.
- Added Graphify retrieval. `sdd graph refresh` writes `graphify-corpus/sdd-traceability.md` and runs `graphify extract --code-only --no-cluster`, then `graphify update` on later refreshes. Every query merges that corpus with the code graph so requirement/task/ADR IDs remain findable.
- Added optional Headroom compression for context packs, spec slices, and check logs. Compression runs in a timed subprocess. Originals stay under `.sdd/runtime/originals/`. Missing, hung, or opted-out Headroom keeps the compact text and does not block.
- Rewrote core skills into on-disk runbooks with routing frontmatter, directory maps, procedures, and failure modes. Prompts carry the skill name and description; the agent loads `.agents/skills/<name>/SKILL.md`.
- Review fails on critical/high findings and on security/data-loss/integrity issues even when `violates_ac` is false. Medium findings still require an AC break. Task checks prefer `check_paths` and run the full suite at feature end.
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
- Pass `--trust` on every Cursor print-mode invocation. Writable Cursor `--force` is opt-in via `allow_unrestricted_agent` or `sdd start --allow-unrestricted`.
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

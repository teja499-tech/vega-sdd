# Universal SDD — implementation audit and end-to-end verification

Date: 2026-09-26 UTC (2026-09-25 Pacific)
Original package: 0.1.0. Hardened audit release: 0.1.1.

**Verdict: the original implementation does not satisfy the entire agreed product contract.**
The controller is now substantially better tested and several serious defects have
been repaired. This is an experimental release, not certification of a complete,
production-ready autonomous development framework.

## Evidence and test boundaries

| Evidence | Result | What it establishes |
|---|---|---|
| Original supplied suite | 13 passed; 72% statement coverage | Reproduced the previous claim |
| Initial added regression suite | 15 failures, 1 pass against 0.1.0 | Original tests missed important failure paths |
| Hardened framework suite | 75 passed; approximately 90% statement coverage | Controller, CLI, state, failure, and subprocess behavior |
| Incident Desk lifecycle | 16 successful CLI subprocess invocations | Initialization through pause, resume, repair, change, and completion |
| Incident Desk final acceptance suite | 12 passed | Storage, real local HTTP requests, negative cases, restart, and changed title limit |
| Authenticated Codex / Cursor / Claude runs | Not executed: CLIs absent | No provider integration certification |
| Production deployment / load / independent security assessment | Not executed | No production-readiness claim |

Coverage is a statement-execution measurement. It is not a feature-completeness
percentage or evidence of LLM reasoning quality. Some provider parser tests use
synthetic output records; they do not establish compatibility with current live
provider versions. Framework suite and application suite are separate.

The benchmark uses a **scripted subprocess adapter**, not an AI model. It returns
predetermined product/spec/review responses and copies reference implementation
files. Application verification executes real Python code, SQLite transactions,
HTTP requests over local sockets, and service restart tests. Reviewer judgments
are scripted passes; this exercise cannot prove independent model review quality,
PRD interpretation, research, or autonomous code generation.

## Benchmark product and observed journey

`examples/incident-service/PRD.md` specifies an internal single-tenant incident API:
6 requirements, 3 dependent features, and 3 initial tasks. It requires runtime API
key authentication, persisted incidents, validation, pagination, status updates,
health checks, operational guidance, and repeatable acceptance tests. Its target
is a small production use case; the included WSGI reference server is for local
acceptance and is not itself a production deployment.

The driver performed these actions in separate CLI processes:

1. Interactive init: answer a product question, ask the architect about SQLite,
   approve the database choice, and generate requirements/ADRs/specs/tasks.
2. Configure an executable acceptance-test command.
3. Start one storage task and stop at the configured task boundary.
4. Read status, then resume with no prior in-memory agent session.
5. Encounter an intentionally seeded authentication defect (401 replaced by 200).
   Real HTTP acceptance tests fail. The controller invokes repair, reruns the
   checks, reviews, and continues through operations work.
6. Inspect verify, roadmap, requirements, architecture, doctor, log, feature,
   and architect intervention commands.
7. Decline a title-limit requirement change; canonical feature state stays intact.
8. Approve the same change from 120 to 80 characters. API and downstream operations
   tasks become invalidated; storage remains verified.
9. Resume and run updated acceptance tests. An 81-character new title is rejected,
   80 characters succeeds, and existing longer titles remain readable.

The journal records the failed deterministic check, repair attempt, completion,
approved change, and subsequent verification. The complete run and command logs
are retained under `audit/benchmark/` in the source ZIP.

## Feature-by-feature assessment

“Tested” below refers to controller behavior with fixtures unless explicitly stated.

| Agreed capability | Assessment | Evidence or remaining limitation |
|---|---|---|
| Python package and CLI | Tested | Full 75-test suite and 16-command benchmark rerun against installed wheel; Python 3.12 on Linux |
| Start with only a PRD | Tested mechanics | Real model interpretation remains untested |
| Select initial coding agent | Tested routing | Real authentication handshake absent |
| Product clarification questions | Tested | Fixed questions returned by fixture; not a full conversation engine |
| Architecture options, ask, other, defer | Tested | CLI surface exercised |
| Current market research with official sources | Missing enforcement | Prompt requests plausible options; no retrieval/provenance pipeline |
| Later architecture choices adapt to earlier selections | Missing | All options generated before selection loop |
| ADRs, specs, requirements, features, tasks | Tested generation | No guarantee that every PRD requirement was extracted |
| DAG scheduling and traceability | Hardened and tested | Missing IDs, duplicates, feature/task/mixed cycles rejected |
| Requirement → AC → code → test → evidence links | Partial | Requirements/task links exist; ACs are strings and code/test identities are not first-class links |
| One primary coding controller | Hardened and tested | OS lease prevents concurrent run/change/init/agent switch; POSIX tested |
| Implementation/check/review/repair loop | Hardened and tested | Real checks rerun after each repair; attempts bounded |
| Independent reviewer | Partial | Separate bounded invocation, same selected provider; no distinct model/role scheduler |
| Specialized security/architecture/integration reviews | Partial | Role files exist; not distinct enforced review stages |
| Deterministic checks | Hardened and tested | Real adapters require test_command; user must configure it manually |
| sdd verify | Tested, narrower than name suggests | Validates graph/traceability only; does not execute application checks |
| Status and watch | Tested | Requirement-based progress; watch interruption exercised |
| Objective release readiness | Missing | Release criteria are prose; no evaluated release checklist/percentage |
| Pause at task boundary | Tested | Durable request survives controller state saves |
| Ctrl+C and process cleanup | Tested | Keyboard interruption and POSIX subprocess termination |
| Resume implemented work | Fixed and tested | Implemented tasks proceed to checks rather than reimplementation |
| Crash recovery from YAML state | Partial, tested | OS lease released on crash; resume reconstructs state |
| Journal replay / named checkpoints | Missing | Journal is diagnostic; last_checkpoint remains unset; no replay algorithm |
| Switch coding agents | Tested routing only | Real cross-provider handoff untested |
| Architect intervention | Partial, tested CLI | Each question is a fresh invocation; no maintained conversation history or automatic pause |
| Defect/change classification | Tested routing | Classification quality depends on provider; approval no longer trusts provider boolean |
| Approved change reconciliation | Hardened and tested | Prevalidates graph; conservative transitive invalidation; not a multi-file transaction |
| Automatic implementation-defect repair tasks | Tested | Repeat application idempotent; multi-feature defect planning still limited |
| Existing AGENTS.md preservation | Tested | Existing instructions retained |
| Force reinitialization | Hardened and tested | PRD validated first; prior .sdd backed up; not automatic rollback after every init failure |
| Repository-owned vendor-neutral state | Tested | YAML and journal; provider session is not authoritative |
| Provider capabilities and permissions | Partial/unverified | Mostly declared flags; no robust runtime capability/auth probing |
| Native sessions, provider approvals, persistent streams | Missing/full support unverified | One-shot subprocess invocation; not SDK/ACP/app-server supervision |
| Interactive root sdd shell | Missing | Subcommands exist; bare sdd displays help |
| Foreground execution | Implemented/tested | Detached daemon intentionally deferred |
| Separately versioned harness | Partial | Python package versioned; schema migration/upgrade command absent |
| Comprehensive documentation | Updated | Audit overrides broader claims in original documents |

## Defects repaired in 0.1.1

The original regression failures and fixes are reproducible in
`tests/test_hardening.py` and `audit/regressions-before.txt`.

- Reject empty specifications, duplicate IDs, missing acceptance criteria, and
  cyclic dependency graphs (including combined task/feature deadlocks).
- Require **all mapped tasks** for a requirement to count as implemented/verified.
  Main implementation/verification percentages now use requirements, not task counts.
- Resume implemented tasks at verification instead of rerunning implementation.
- Repair deterministic test failures within the bounded loop; rerun checks after
  every repair so stale pre-repair results cannot approve broken code.
- Convert malformed review responses into bounded failures rather than leaving
  the project incorrectly marked running.
- Require a deterministic test command for non-mock adapters and return nonzero
  CLI status for blocked/failed runs.
- Validate PRD existence/content before force reinitialization and retain a backup.
- Make reapplying an already-applied change idempotent.
- Compute approval requirements in the controller; a model cannot bypass approval
  by setting requires_approval=false on an architecture/requirement change.
- Validate proposed graph changes before writing approved state; invalidate
  affected requirements/tasks and transitive dependents even if an agent omits them.
- Use atomic replacement for YAML/JSON files and an OS-held single-writer lease.
- Keep pause requests separate from controller snapshot writes to avoid lost pauses.
- Drain subprocess stderr concurrently to prevent full-pipe deadlocks; terminate
  POSIX process groups on interruption; record unexpected run failures.
- Treat error events with successful process exit as failed adapter results.
- Reject unsafe artifact identifiers and sanitize generated feature directory names.
- Remove a Python-3.12-only f-string expression inconsistent with declared 3.11 support;
  actual runtime testing remains Python 3.12 only.
- Do not classify a PRD-only directory as an existing application.

## Remaining material risks

1. **Writable agents can access controller files and tests.** Instructions prohibit
   tampering, but there is no enforced filesystem isolation protecting approved
   specs, evidence, or independent acceptance tests. A buggy agent could edit them.
2. **Evidence is not tied to source hashes or Git revisions.** Manual code edits
   after verification can leave stale green status. There is no complete drift detector.
3. **Change publication spans multiple files.** Prevalidation and atomic individual
   writes help, but a crash partway through publication can leave inconsistent views.
   Journal replay and transactional recovery are not implemented.
4. **Readiness is structural, not semantic.** Deferred questions/decisions warn but
   do not consistently gate affected work. “100% specification” only reflects mapped
   known requirements with ACs; it does not prove complete PRD coverage.
5. **Provider behavior is unverified.** Streaming, cancellation, permissions, auth,
   session continuity, real code generation, model review, and cost/timeout behavior
   need live tests. The framework cannot make an unavailable CLI authenticated.
6. **Operational bounds are incomplete.** Checks have a fixed five-minute timeout;
   agent calls have no configurable total timeout/budget, and output memory is unbounded.
7. **Canonical and rendered views can diverge.** Runtime task updates do not rebuild
   every Markdown task/roadmap view; renamed/removed features can leave old directories.
8. **Cross-platform behavior remains unproven.** macOS and Windows have not been run;
   Windows child-process-tree termination is weaker than POSIX process-group cleanup.

These are reasons not to call this the fully implemented product originally described.
They are not solved by increasing test coverage alone.

## Reproduce and run the remaining live test

From the extracted source:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest --cov=universal_sdd
python examples/incident-service/run_benchmark.py /tmp/sdd-incident-fixture-run
```

The benchmark refuses an existing destination so earlier evidence is not overwritten.
It is explicitly a scripted-adapter test.

For the missing real-provider test, on a workstation with a supported installed and
already authenticated agent, create a fresh Git repository containing the sample
PRD, then run:

```bash
sdd doctor
sdd init --agent codex --project-kind new
```

Review the generated product/architecture interpretation. Configure test_command in
`.sdd/config.yaml` to the actual application test command generated for that project
(the scripted fixture's test command is not automatically correct for a live build).
Then run `sdd start --max-tasks 1`, `sdd status`, `sdd resume`, and exercise
pause/intervene/change with the benchmark acceptance cases. Keep provider version,
command logs, test results, state snapshots, and Git revisions. Do not use the fixture
adapter for this certification. Repeat for each provider before declaring portability.

No production deployment or external account action was performed during this audit.

## Source identity

Original ZIP SHA-256: `e7da47b367070ba16237355d9c583bbcc2384c031fbdf175171041a2d4b614ad`. This matches the previously delivered package. The original archive was preserved. v0.1.1 is a separate hardened release.

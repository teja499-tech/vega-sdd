---
name: implement-task
description: Implement exactly one SDD task from the controller context pack. Use for a bounded implementation pass. Do not use for review, spec authoring, or ad-hoc product changes.
---

# Implement Task

## When this skill loads
The controller has selected one task whose dependencies are verified. The prompt contains `TASK_IMPLEMENTATION`, a context pack, and acceptance criteria. Load this file from `.agents/skills/implement-task/SKILL.md`. Do not load every skill in the catalog.

## Goal
Satisfy the task verification and the acceptance criteria it implements. Leave a recoverable working tree. Do not certify the task; the controller writes `.sdd/state`.

## Directory map
| Path | What it is | May you edit it? |
|---|---|---|
| `.sdd/specs/<feature>/spec.md` | Approved feature contract | No |
| `.sdd/specs/<feature>/tasks.md` | Task boundary and verification | No |
| `.sdd/state/` | Canonical status, requirements, features | No |
| `.sdd/decisions/` | Approved ADRs | No |
| `graphify-corpus/sdd-traceability.md` | Corpus Graphify indexes | No |
| `graphify-out/graph.json` | Knowledge graph | No; refresh with `sdd graph refresh` after code changes |
| `.agents/skills/` | These runbooks | No |
| `AGENTS.md` | Repository rules | No |
| Application source and tests named in the working set | The change | Yes |
| New files required by the task and listed in the spec `target_files` | The change | Yes, and add them to the working set in your summary |

## Graphify before grep
If `graphify-out/graph.json` exists:

1. `graphify query "<task id> <acceptance criterion>"` for the scoped subgraph.
2. `graphify path "<symbol you will change>" "<caller or test>"` when you need a dependency.
3. `graphify explain "<module>"` when the pack names a concept and not a file.

Only then open files. Read or Grep is for a line you are about to change, not for orientation. If Graphify is not built, use the working-set paths in the pack and stop if a required file is absent. Do not walk the repository.

## Inputs the pack already contains
- Task id, title, description, requirement ids
- Acceptance criteria and feature contracts (invariants, non-goals, API, UX, test matrix)
- Working-set paths (target about 5–15 files)
- Related tests and the narrow check command
- Last blocking findings, if this is a retry
- Skill name and description, not this whole file

## Procedure
1. Read this skill, then the working-set files. Confirm the change fits the task description.
2. If an invariant, API contract, or UX contract is missing and the task cannot be implemented without inventing product behavior, stop. Report the gap. Do not guess and do not edit the spec.
3. Edit application code only. Match existing module layout, error types, and test style.
4. Add or update the tests named by verification. Cover the happy path and the negative case the acceptance criterion names.
5. Run the narrowest check in the pack (`check_paths` or the task test file). Do not start the full workspace suite unless the pack says this is the feature-closing task.
6. If the check fails, fix the defect. Do not delete or weaken the assertion.
7. Stop. Leave changes uncommitted. Do not create branches, tags, or `SDD-Task` trailers. Do not write `.sdd/`.

## Contracts you must not invent
- Route shapes, status codes, and error catalogs belong to `api-design` and the feature `api_contract`.
- Page states and user-facing copy belong to `ux-design` and the feature `ux_contract`.
- Columns, indexes, and migrations belong to `data-model`.
- If the feature spec already has that section, implement it. If it does not, escalate.

## Checklist
- [ ] Every acceptance criterion in the pack maps to a test or an explicit runtime check you ran
- [ ] Diff is limited to the working set plus new files the task names
- [ ] `.sdd/`, `.agents/`, and `AGENTS.md` are untouched
- [ ] Git HEAD and the index are untouched
- [ ] Failing tests were fixed in code, not by skipping them
- [ ] Graphify was queried before a repository-wide search, when `graphify-out/graph.json` exists

## Failure modes
- Treating a low-severity review nit from a previous attempt as a new product requirement.
- Reading the whole test log into the next edit instead of the failure snippet and the original file under `.sdd/runtime/originals/`.
- Implementing a neighboring task because its file was open.
- Updating the spec so the new code looks compliant.
- Running `pytest` on the entire repository for a single module task.

## Example
Task `TASK-F001-004` says: add `POST /notes` that rejects an empty title with 400 and persists a valid title.

Working set: `app/notes.py`, `tests/test_notes.py`.
Contract: `POST /notes {title} -> 201 {id,title}`; empty title -> 400 `title_required`.

You add the handler and two tests. You run `pytest -q tests/test_notes.py`. You do not also add search, auth, or a README unless those are this task.

## How the controller calls you
This is a new subprocess. You do not remember the previous task. The pack is the memory: acceptance criteria, working set, contracts, Graphify excerpt, and last blocking findings. Do not rebuild that memory by crawling the repo.

After you exit, the controller:

1. Runs the narrow check, not the full suite, unless this task closes the feature.
2. Sends a separate read-only review pass. You are not that reviewer.
3. If review returns medium or higher that breaks acceptance criteria, it calls you again with those findings only.
4. Writes `.sdd/state` itself. A sentence in your reply that says "task complete" changes nothing.

## Pack fields
| Field | How to use it |
|---|---|
| Acceptance criteria | The only behavior you must prove |
| Working set | Open these files first |
| Related tests | The files your check command should target |
| Feature contracts | Invariants, non-goals, API, UX. Implement them. Do not extend them |
| Graphify subgraph | Cross-file callers. Query again if it is empty and `graphify-out/graph.json` exists |
| Last findings | Repair only these. Ignore low or warning nits |
| Skill catalog | Names and one-line descriptions. Open a second skill file only when the task matches that description |

## Choosing the check
Use `check_paths` when the task lists them. Otherwise run the test file that covers the acceptance criterion, for example `pytest -q tests/test_notes.py`. Do not run `pytest -q` on the whole tree for a single handler. The controller runs that suite once, when every task in the feature is verified.

If the check log is long, read the failure snippet in the pack. The full log, when the controller compressed it, is under `.sdd/runtime/originals/`. Do not paste the green run back into the repository.

## Repair versus first implementation
A repair prompt lists blocking findings. Change only the lines those findings name. Do not refactor neighbors. Re-run the same narrow check. If a finding contradicts the feature contract, stop and say so. Do not "fix" the spec.

## Escalation versus local decisions
Escalate, and do not code, when the acceptance criterion conflicts with the API or UX contract, when a required file is outside the working set and not named by the task, or when an architecture decision is still deferred.

Decide locally when the task leaves a name, private helper, or test fixture unspecified and the existing module already has a pattern. Match that pattern.

## File budget
Stay within the working set plus files the task explicitly creates. If a real compile error forces one extra file, keep it in the same package and mention it. Do not open a second feature's package because Graphify showed a distant caller. Note the caller in your summary if you did not need to change it.

## Done
The verification list is satisfied and the working tree is recoverable. The controller runs review and records status.

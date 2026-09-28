---
name: create-feature-spec
description: Author a feature spec and tasks a coding agent can execute without inventing product behavior. Use during spec bundle creation or sdd change reconciliation, not during implementation.
---

# Create Feature Spec

## Goal
Produce a feature whose tasks contain contracts, not titles. A later implement agent must not have to guess routes, states, or tables.

## Directory map
- Facts: `.sdd/product/vision.md`, `requirements.md`, `clarifications.md`
- Decisions: `.sdd/decisions/*.md` and `.sdd/architecture/decisions.md`
- Output: `.sdd/specs/<id>-<slug>/spec.md`, `tasks.md`, and the feature object in the spec bundle
- Traceability corpus Vega searches deterministically: `graphify-corpus/sdd-traceability.md` (the controller regenerates this and merges hits with Graphify code-graph results; Graphify extract is `--code-only`; do not hand-edit)
- Open questions that block start: `.sdd/product/clarifications.yaml`

## Feature contract
Every feature object needs:

- `summary` — problem, user, outcome. At least two sentences.
- `invariants` — conditions that remain true after the feature ships.
- `non_goals` — behavior this feature will not implement.
- `requirements` — ids of MUST requirements it covers.
- `test_matrix` — happy path, negative or auth, empty, regression.
- `api_contract` or `ux_contract` or both when the feature has an interface. Use the api-design or ux-design skill for the shape.
- `target_files` — existing paths when the repository already has them.
- `tasks` — one bounded agent run each.

## Task contract
Each task needs an id `TASK-<feature>-NNN`, a description that names files, behavior, and tests, `implements` requirement ids, `verification` a reviewer can check, and `check_paths` when a narrow test file exists.

Reject:

- Descriptions that restate the title.
- Verification that says "works" or "looks good".
- A feature with no invariants and no test matrix and no API or UX contract.

## Procedure
1. Read the PRD, clarifications, and selected ADRs. Do not resolve an open question inside the spec.
2. List MUST requirements. Each one appears in at least one task.
3. Write invariants and non-goals before tasks.
4. If the feature exposes HTTP or RPC, fill `api_contract` using the api-design skill.
5. If it has a screen, fill `ux_contract` using the ux-design skill.
6. If it persists data, name entities using the data-model skill.
7. Split work so each task's diff is reviewable in one pass.
8. Keep dependencies a DAG. Foundation before behavior. Behavior before release docs.

## Checklist
- [ ] No title-only feature or task
- [ ] Every MUST requirement has a task and a testable acceptance criterion
- [ ] Open questions are listed, not silently answered
- [ ] Non-goals would stop a reviewer from inventing scope
- [ ] `check_paths` point at real or planned test files

## Failure modes
- Copying the PRD headings into tasks without behavior.
- Marking work verified inside the bundle. New tasks stay pending.
- Encoding a deferred architecture decision as if it were selected.

## Example
Feature `F003` summary explains who creates a note and what list returns. Invariant: a created note appears in the list. Non-goal: sharing. API contract names `POST /notes` and `GET /notes`. Task `TASK-F003-001` description names the handler module and the test file, verification names the 201 and 400 cases.

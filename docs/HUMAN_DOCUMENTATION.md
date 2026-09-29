# Human documentation and repository support

Vega SDD 0.4.1 generates an indexed Markdown documentation pack and human-readable engineering history. The pack is based on the canonical specification bundle and approved ADRs. It is not a certification that a repository is enterprise-ready.

## Documents generated

The entry point is `SDD_PROJECT.md` at repository root, linking to `.sdd/docs/README.md`.

| File under `.sdd/docs/` | Required content |
|---|---|
| SYSTEM_OVERVIEW.md | Purpose, scope, users, workflows, system boundaries |
| HLD.md | Components, responsibilities, interactions, deployment, quality attributes and tradeoffs |
| LLD.md | Modules, interfaces, execution flows, validation, failure handling, concurrency, idempotency |
| DATABASE_DESIGN.md | Entities, relationships, fields, constraints, indexes, migrations, retention |
| API_DESIGN.md | Authentication, contracts, requests, responses, errors, compatibility |
| SECURITY.md | Trust boundaries, threats, access controls, secrets, privacy, audit |
| OPERATIONS.md | Configuration, deployment, monitoring, alerts, backup, restore, incidents, rollback |
| TEST_PLAN.md | Acceptance, integration, performance, security, data and environments |
| EXISTING_SYSTEM.md | Observed behavior, evidence, unknowns, target changes, compatibility, migration |
| CONTRIBUTING.md | Setup, review process, ownership and escalation |
| RELEASE_PLAN.md | Criteria, release notes, rollout and rollback |
| TRACEABILITY.md | Requirement → feature → task → execution status → evidence |

ADRs remain in `.sdd/decisions/`. The test strategy, requirements, feature specifications and roadmap remain in their existing locations. The agent is instructed to provide tables and Mermaid source where useful; Markdown rendering requires a compatible reader. Diagram syntax/semantics are not automatically certified.

For new repositories, SDD also adds root entry points `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md` and `.github/pull_request_template.md` **only when absent**. Existing enterprise files are preserved byte-for-byte. The generated security entry point explicitly identifies the missing private reporting contact; it is not a finished disclosure policy. SDD does not invent a license, CODEOWNERS team, SLA, deployment environment or approval authority.

## New, existing and completed applications

```bash
sdd init --project-kind new
sdd init --project-kind existing
```

Both use the supplied PRD. A completed application uses `existing`; that selects the adoption path, not a claim that SDD has independently certified the app. The documentation agent must distinguish observed current behavior, approved target design and unknowns. Filename inventory alone is not proof of behavior. The agent can inspect code read-only. Existing source, README and policy files are preserved during initialization.

Older v0.1.0/v0.1.1 projects load without schema conversion. They have no detailed design content, so regeneration produces clearly labelled incomplete documents. To populate them through the selected coding agent:

```bash
sdd docs refresh --enrich
sdd docs check
```

`--enrich` requests detailed read-only documentation from the selected provider. It validates the returned document schema and replaces only `design_documents` in the canonical bundle, retaining a specification snapshot. It does not change task state, requirements, ADRs or grant approvals. Malformed responses leave canonical documentation unchanged. Conflicts with intent must be recorded as gaps and handled with `sdd change`. Provider adherence and factual prose accuracy still need review.

## Keeping documents current

```bash
sdd docs refresh          # Local regeneration; no model call
sdd docs refresh --enrich # Read-only code/design inspection by selected agent
sdd docs check            # Exit 2 for missing, stale, incomplete or manually altered docs
```

Initialization and approved specification reconciliation generate the pack. Task verification and repair creation refresh traceability and history. This does not imply that narrative as-built documentation automatically reflects arbitrary code edits: run enrichment after meaningful implementation changes and review its results.

The source fingerprint covers the canonical bundle and ADRs. It detects **specification** staleness, not arbitrary code drift. Structural checks inspect required sections, source-reference presence, explicit gaps, applicability reasons and generated-file hashes. They do not verify the truth of every citation, prose claim or diagram.

Each design has `draft`, `documented` or `not_applicable` status. Documented means structurally populated, not independently approved or tested. Unsupported topics require a reason; unresolved details remain gaps. These checks are a separate command and do not introduce new automatic development blockers. An enterprise CI can choose to require `sdd docs check` after the team resolves its documentation gaps.

Generated files have recorded hashes. Refresh preserves manually edited files and reports conflicts rather than discarding edits. Move desired edits into canonical `design_documents` (using approved change handling for intent changes) or a companion human-owned document. Then remove the conflicting generated file and refresh. Changes to root enterprise-owned files are never overwritten.

## Human change history

```bash
sdd changelog
```

`.sdd/CHANGELOG.md` contains initialization, task verification, repairs, applied requirement/architecture changes, pauses, failures, documentation enrichment and completion events. Entries show timestamps, task titles, requirement IDs, verification references, change classifications, approval state, invalidated work and available commit links. Task intent is captured at event time so a later title change does not rewrite historical entries.

Canonical specification updates also retain content-addressed JSON snapshots and exact transition diffs under `.sdd/history/specs/`. Links appear in the changelog. Repeated identical snapshots do not create duplicates; A → B → A retains both transitions. Git context is recorded separately from attribution. The journal and projections are local repository artifacts, not a tamper-proof compliance audit store. Historical events from before v0.1.2 lack information that was never captured.

## Commit attribution

Coding agents do not create commits. By default Vega also leaves verified changes uncommitted. The optional `sdd lifecycle` flow may create a controller-owned commit only when the approved repository policy explicitly sets `auto_commit: true`; push remains separately controlled. For a human-created commit, include an exact trailer:

```text
Implement incident status update

SDD-Task: TASK-F002-001
```

After verification, SDD searches commits between the task-start HEAD and current HEAD. Matching trailers are linked automatically. Unrelated commits are excluded. A history rewrite, absent starting HEAD, uncommitted implementation or missing trailer leaves attribution pending. To link a historical or initial commit explicitly:

```bash
sdd link-commit TASK-F002-001 --commit <actual-sha> \
  --summary "Add API-key checks and incident status updates"
```

The command validates the task, hexadecimal SHA, local commit object and reachability from current HEAD. It records full SHA, author, date, subject, changed files, requirement IDs and a human summary. Repeated task/SHA links are idempotent. A SHA's existence and ancestry do not prove semantic relevance: the trailer or explicit link supplies attribution, and review verifies it. The same commit may legitimately cover multiple tasks.

Without a link, history says attribution is pending; it never treats the latest unrelated HEAD as that task's implementation commit. Raw remote URLs are not emitted, avoiding accidental exposure of credentials in remotes. The full SHA is available for local Git inspection or enterprise tooling.

## Project-specific work that remains

Live provider versions and credentials, OS-level isolation, application-specific CI/CD, branch protection, dependency/security scans, SBOM/signing, CODEOWNERS, legal policies, SLOs, accessibility, performance, data migration, and disaster-recovery exercises require real project choices and evidence. Vega supplies contracts and fail-closed controller boundaries where practical; it does not falsely mark these controls implemented or generate one universal pipeline for every stack.

The incident-service example supplies a detailed, clearly labelled scripted documentation fixture and reproducible validation scripts. Production gaps are intentionally visible, and `docs check` correctly fails on them.

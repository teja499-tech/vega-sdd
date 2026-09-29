# Project lifecycle

Vega SDD 0.4.1 stores specifications, human-readable designs, task history, evidence, and change/commit links in `.sdd/`. Approved execution contracts let the same controller supervise an application, library, command-line tool, data pipeline, ML or infrastructure repository, mobile/desktop system, documentation project, or mixed monorepo without pretending they share one build/deploy mechanism. Hosting, toolchain, runtime, and application safety remain project-specific.

## Greenfield and brownfield onboarding

Install the wheel with Python 3.11+ and Git, write `PRD.md`, then:

```bash
sdd init --project-kind new
sdd project inspect
sdd project setup
# Or review one file and import it:
sdd project configure --file workspace-policy.yaml
sdd repo scaffold --owner @your-org/your-team
git status --short
git add -A
git status --short
git commit -m "Approve project baseline"
sdd repo branch feature-scope
sdd start
sdd project check
sdd docs check
sdd changelog
```

For existing code, use `sdd init --project-kind existing`; keep its existing README, CI, security/changelog files and uncommitted work. Inventory the actual build, tests, owners, migrations, dependencies, permissions and release commands first. `repo branch` refuses a dirty source tree and supports `--worktree PATH` for isolation; worktrees share one controller lock. Do not run `init --force` for an ordinary upgrade. Real-agent execution now requires an approved `.sdd/workspace.yaml` and an execution branch; mock demonstrations remain backward compatible.

`project setup` requests component paths, kinds, real commands or explicit waivers, and repository policy. For repeatable setup, review a YAML policy and run `project configure --file`. Approval binds the policy SHA-256 plus the current cross-provider instruction, role, and skill capability digest. Changing any of them invalidates approval and verification. The policy and capability files are trusted execution contracts, so review scripts, command arguments, roles, vendor instructions/configuration, and project-local skills before approving them. Use `project profiles` for the available 12 kinds: web, service, library, cli, data_pipeline, ml, infrastructure, mobile, desktop, embedded, docs and custom. Components declare `depends_on`; builds/checks run in dependency order. A required check needs an actual command or a substantive, visible waiver.

Commands use argument arrays, per-command timeouts and declared required environment-variable names. Never put secrets in policy argv. Declared variable values are redacted from retained command output, though this is not a general-purpose secret scanner. `run_at: release` marks integration checks that cannot run during early greenfield tasks; full `project check`, CI and release qualification include them. Only a fresh full check of the exact current source and approved policy qualifies PR publication or a release. Generated `.sdd/ci` files are part of source evidence when committed; other controller projections are excluded. Configure project-specific checks for compatibility, performance, security, licenses, SBOM, accessibility, replay, evaluation, hardware and migration as appropriate.

Human documentation covers the system overview, HLD/LLD, database/API design, security, operations, test plan, contributing guidance, and release plan. The existing-system report distinguishes observed behavior, desired changes, and unknowns. Inapplicability must be explained rather than filled with fabricated content. `sdd docs check` reports structural gaps, not independent architectural approval. `.sdd/CHANGELOG.md` and spec snapshots/diffs show task/intent changes and explicit commit links; use `sdd link-commit` for accurate attribution.

## Branch strategy, review and CI

Integration defaults to `main`, protected branch patterns include main/master/develop/release/*, and work branches use `sdd/<scope>`. Set base/protected patterns for the organization's trunk or release-branch strategy. Direct task implementation on protected/detached/unborn branches is blocked. Existing conflicts and pre-staged work are preserved.

`repo.allow_push`, `repo.allow_merge` and `repo.auto_commit` default to false. With GitHub, configure an explicit `owner/repo`, install/authenticate `gh`, and set actual required check names. `sdd repo pr --title TITLE --body-file BODY`, `repo pr-status ID`, and `repo merge ID` require clean local source and fresh full evidence. Merge rejects mismatched head/base, drafts, missing/stale reviews, unknown mergeability and failed/missing checks; GitHub merge uses `--match-head-commit`, without a force push or administrator bypass. A queued merge is not marked complete. The generic `command` provider allows other hosts through trusted, tested `open`/`view`/`merge` JSON hooks; these are not native GitLab/Azure PR implementations.

Configure branch protection, required reviewer/code-owner policies, stale-approval dismissal, force-push/bypass restrictions and merge queue/up-to-date behavior on the real host. `sdd repo audit-host` is a read-only audit of classic GitHub branch protection and fails closed when permissions are missing; it does not inspect all rulesets or environments. `repo scaffold --owner @actual-owner` creates non-overwriting CODEOWNERS, PR/issue templates, security/support/contribution starters. Fill the true contacts and owner policies.

```bash
sdd pipeline export --provider github
sdd pipeline export --provider gitlab
sdd pipeline export --provider azure
sdd pipeline export --provider github --wheel /path/vega_sdd-0.4.1-py3-none-any.whl
```

The exporter writes a frozen-policy standalone Python checker and a GitHub checks workflow, GitLab include fragment or Azure steps template. Existing workflows are preserved. `--update-generated` may replace only files still byte-for-byte equal to the last generated copy. GitHub checks target pull requests, base pushes and merge groups with read-only repository permission. Commit the policy, `.sdd/ci/` and relevant workflow; configure toolchains and dependencies through `setup` commands. The optional GitHub delivery workflow checks and builds once on the integration branch, moves the same artifact to downstream environment jobs, and carries promotion receipts between jobs. Configure actual protected host environments, allowed dispatch users and cloud credentials; exported YAML does not provision them. Default runner is Linux. Check action commit pins/host support before enabling, especially the download-artifact pin, which could not be confirmed through the official commit endpoint in this environment.

## Immutable release, promotion and recovery

Each releasable component needs a build command and one regular artifact file; archive directories, sign installers, or use digested manifests as your stack requires. `sdd release build VERSION` requires committed source and fresh full checks, hashes each artifact into `.sdd/artifacts`, records source SHA/policy/check evidence, and refuses to reuse a release version. Deployment hooks consume `SDD_RELEASE_MANIFEST`, `SDD_RELEASE_VERSION`, `SDD_ENVIRONMENT` and `SDD_OPERATION_ID`; they must deploy the manifest's digest, not rebuild unversioned code.

```bash
sdd release build 1.2.3
sdd release deploy 1.2.3 staging
sdd release deploy 1.2.3 production --approve
# Inspect the real target after a timeout or failed smoke test:
sdd release reconcile production --outcome failed --note "Operator confirmed previous version remained active"
```

Promotion requires the same version to have succeeded in its predecessor environment. Approval is release-specific. The controller records an operation intent before external work; a failed/timeout deploy or smoke test leaves an `unknown` state and blocks blind retries until reconciliation. A claimed success requires the original source/policy/artifact and a passing smoke check. Rollback is an explicit project hook and may target only the recorded previous successful version; database downgrades may need forward repair.

`sdd lifecycle` is a resumable invocation that prepares a branch from a clean baseline, runs tasks, verifies, optionally commits/publishes/merges under policy, and builds/delivers a specified version. Return to it after external review/check completion. For a hosted release the provider must report the actual integration commit; SDD fetches that commit, verifies ancestry and re-tests/builds it in a detached release worktree. The original feature branch is preserved. It is not a background scheduler. For a new independent feature, start a new execution context from the latest base.

`recovery checkpoint` saves canonical state snapshots; verified tasks create checkpoints automatically. `recovery restore ID` validates a checkpoint, preserves application code, pauses state, invalidates task/check evidence and removes stale lifecycle progress. Restore does not undo Git or external deployments. Keep independent backups of the actual repository, artifacts and remote runtime. Incomplete or corrupt projection transactions fail closed and retain their rollback evidence for inspection. The controller file guard detects/restores unauthorized agent changes to its state, role/policy instructions and protected paths; read-only runs also restore content/modes and Git HEAD, refs, index, config and hooks, including linked-worktree common metadata. Snapshot size bounds fail before agent launch rather than risking unbounded memory. Large monorepo operators can deliberately raise `SDD_GUARD_MAX_FILES`, `SDD_GUARD_MAX_BYTES`, and `SDD_GUARD_MAX_FILE_BYTES` for the controller process after evaluating host memory. This is an accident-detection guard, not an OS sandbox or hostile-agent containment.

For multi-repo portfolios, pass a YAML list `repositories: [{id: app, path: ../app, depends_on: []}]` to `sdd project portfolio-check --file portfolio.yaml`; failed dependencies block dependents. It aggregates local checks, not atomic cross-repository deployment.

The provider `command` hook receives `SDD_REQUEST` JSON as an environment variable and emits one JSON object on stdout. `open` gets branch/base/head/title/body; `view` gets id; `merge` gets id/expected_head/method and must enforce expected-head comparison atomically. Normalized fields: `id`, `url`, `state`, `draft`, `head`, `base`, `review` (`APPROVED`), `mergeable`, `checks` (`name`, `status`), and after merge the actual 40-character `merge_commit`. Unknown host status fails closed. Test custom hooks against the real host before relying on them.

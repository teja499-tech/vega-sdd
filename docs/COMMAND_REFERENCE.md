# Vega SDD command reference

Run `sdd --help` or `sdd <group> <command> --help` for the installed version's authoritative syntax. This reference covers Vega SDD 0.4.0.

Most commands accept `--root PATH`; when omitted, the current directory is the project root.

## Global workflow

| Command | Purpose | Example |
| --- | --- | --- |
| `sdd init` | Discover product intent, make architecture decisions, and generate specs | `sdd init --prd PRD.md --agent cursor --project-kind new` |
| `sdd doctor` | Inspect agent CLIs, Graphify, and Headroom | `sdd doctor` |
| `sdd scaffold` | Add/refresh framework roles, skills, and IDE adapters | `sdd scaffold` |
| `sdd status` | Show durable progress | `sdd status` |
| `sdd watch` | Continuously refresh status | `sdd watch` |
| `sdd start` | Implement/review/repair dependency-ready tasks | `sdd start --max-tasks 1` |
| `sdd resume` | Continue from repository state | `sdd resume` |
| `sdd pause` | Request a stop at the next task boundary | `sdd pause` |
| `sdd verify` | Validate requirement/feature/task traceability | `sdd verify` |

### `sdd init`

```bash
sdd init \
  --prd PRD.md \
  --agent cursor \
  --project-kind new
```

Options:

- `--prd PATH`: PRD Markdown/text; default `PRD.md`.
- `--agent cursor|codex|claude|gemini|copilot|mock`.
- `--project-kind new|existing`.
- `--yes`, `-y`: accept recommended defaults non-interactively.
- `--force`: intentionally back up and regenerate an initialized `.sdd` directory.

### `sdd start` and `sdd resume`

```bash
sdd start --max-tasks 1
sdd resume --max-tasks 5
sdd start --accept-deferred --max-tasks 1
sdd start --allow-unrestricted --max-tasks 1
```

- `--max-tasks N`: stop after N verified tasks.
- `--accept-deferred`: accept only explicit defaults already present.
- `--allow-unrestricted`: opt into provider auto-approve flags for this process. Use only in an isolated workspace.

## Inspect project intent and state

```bash
sdd requirements
sdd architecture
sdd roadmap
sdd feature F001
sdd status
sdd log --limit 50
sdd changelog
```

These commands render repository-owned state. They do not call an implementation agent.

## Questions, decisions, and changes

| Command | Mutation? | Example |
| --- | --- | --- |
| `sdd ask` | No | `sdd ask "Which ADR selected PostgreSQL?"` |
| `sdd intervene` | Answers are read-only; `change:` previews impact | `sdd intervene` |
| `sdd clarify` | Records an answer | `sdd clarify Q1 --answer "Owners only"` |
| `sdd change` | Preview by default; may mutate after approval | `sdd change "Add per-profile locale"` |

Explicit change approval:

```bash
sdd change "Add per-profile locale" --approve
```

## Agent selection

```bash
sdd agent list
sdd agent use cursor
sdd agent use codex
sdd agent use claude
sdd agent use gemini
sdd agent use copilot
sdd agent use mock
```

Changing the adapter preserves the PRD, requirements, architecture, tasks, and evidence.

## Clarification and task recovery

```bash
sdd clarify
sdd clarify Q1 --answer "Only workspace owners may export"
sdd clarify ARCH-002 --answer "PostgreSQL"

sdd task retry TASK-F001-003 --keep-code
sdd task retry TASK-F001-003 --wipe-status
```

`--keep-code` is the default and requeues verification while preserving the working tree.

## Graph and documentation

```bash
sdd graph refresh
sdd graph query "task persistence"

sdd docs refresh
sdd docs refresh --enrich
sdd docs check
```

- `graph refresh` writes the SDD traceability corpus and runs Graphify extract/update when installed.
- `docs refresh` regenerates from canonical specs without a model call.
- `docs refresh --enrich` invokes the selected agent read-only to inspect code and approved intent.
- `docs check` reports missing, stale, structurally incomplete, or conflicting generated documents.

## Project policy and checks

```bash
sdd project profiles
sdd project inspect
sdd project setup
sdd project configure --file workspace-policy.yaml
sdd project check
sdd project readiness
sdd project portfolio-check --file portfolio.yaml
```

| Command | Purpose |
| --- | --- |
| `profiles` | List project kinds and required check names |
| `inspect` | Inventory stack/CI hints for policy authoring |
| `setup` | Interactively create and approve `.sdd/workspace.yaml` |
| `configure` | Validate, save, and approve a reviewed YAML policy |
| `check` | Run approved checks and save source-bound evidence |
| `readiness` | Report missing checks, waivers, build/artifact pairs, and delivery prerequisites |
| `portfolio-check` | Run checks across dependency-ordered repositories |

## Repository delivery

```bash
sdd repo scaffold --owner @your-org/your-team
sdd repo audit-host
sdd repo branch feature-name
sdd repo branch feature-name --worktree ../feature-name
sdd repo pr --title "Feature title" --body-file PR_BODY.md
sdd repo pr-status 123
sdd repo merge 123
```

These commands follow the approved `repo` policy. Push, merge, and auto-commit default to false. Hosted actions require clean source and current full-check evidence.

## CI export

```bash
sdd pipeline export --provider github
sdd pipeline export --provider gitlab
sdd pipeline export --provider azure
sdd pipeline export --provider github --update-generated
sdd pipeline export --provider github --wheel /path/to/vega_sdd-0.4.0-py3-none-any.whl
```

Export is non-overwriting. `--update-generated` replaces only a file that still matches its last generated copy.

## Releases and environments

```bash
sdd release build 1.2.3
sdd release deploy 1.2.3 staging
sdd release deploy 1.2.3 production --approve
sdd release rollback 1.2.2 production --approve
sdd release reconcile production \
  --outcome failed \
  --note "Operator verified previous version is active"
```

The workspace policy supplies component build/artifact definitions and environment deploy/smoke/rollback commands.

## End-to-end lifecycle helper

```bash
sdd lifecycle
sdd lifecycle --version 1.2.3 --environment staging
sdd lifecycle --version 1.2.3 --environment production --approve
```

`lifecycle` is a resumable foreground coordinator for branch, development, verification, delivery, and release steps permitted by policy. It is not a background scheduler.

## Checkpoints

```bash
sdd recovery checkpoint
sdd recovery restore CHECKPOINT-ID
```

Restore preserves application code but restores canonical SDD state and invalidates stale evidence.

## Commit attribution

```bash
sdd link-commit TASK-F002-001 \
  --commit 0123456789abcdef0123456789abcdef01234567 \
  --summary "Implement API-key validation and status update"
```

The commit must exist locally and be reachable from the current HEAD. Vega never assumes that the latest commit belongs to a task.

## Root selection

Run a command against another repository without changing directory:

```bash
sdd status --root ../my-project
sdd verify --root ../my-project
sdd start --root ../my-project --max-tasks 1
```

## Exit behavior

- Exit `0`: command completed successfully.
- Exit `2`: validation/readiness/check failure or another user-correctable blocked condition for commands that report such failures.
- Other nonzero exits: invocation, provider, policy, or unexpected runtime failure.

Always read the printed error. Vega favors explicit failures over silently skipping required evidence.

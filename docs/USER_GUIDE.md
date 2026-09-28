> **Vega SDD 0.4.0:** This guide describes the framework behavior; see [project lifecycle](PROJECT_LIFECYCLE.md) for current delivery policies and [verification](VERIFICATION_0.2.0.md) for the original 0.2.0 test baseline. Version-specific notes below are historical. Supported primary agents: Cursor, Codex, Claude Code, Gemini CLI, and GitHub Copilot CLI.

# v0.1.2 update

Human HLD/LLD/database/API/operations documentation, human changelog, spec revision diffs and Git attribution are now available. See [full documentation and commands](HUMAN_DOCUMENTATION.md).

> **0.1.1 audit status:** Experimental controller. See the [verification report](VERIFICATION_REPORT.md) for tested behavior, defects repaired, missing features, and live-provider limitations. Earlier broad descriptions below are not certification.

# Vega SDD User Guide

## Installation

Requires Python 3.11+.

```bash
python -m pip install .
```

For development:

```bash
python -m pip install -e '.[dev]'
pytest
```

You also need at least one supported coding-agent CLI installed and authenticated for a real project. Run:

```bash
sdd doctor
```

## Starting from only a PRD

Place a normal PRD in the repository:

```text
my-app/
└── PRD.md
```

Then:

```bash
cd my-app
sdd init
```

You will choose Cursor, Codex, Claude Code, Gemini, or GitHub Copilot. The selected agent is used as the architect/specification engine during initialization and becomes the primary implementation engine until changed. Set `review_agent` in `.sdd/config.yaml` when high-risk work needs a separate reviewer.

### Product discovery

The agent returns a product model and material questions. Answers are stored durably. A good clarification answers product intent; it should not micro-manage implementation.

### Architecture workshop

For each relevant decision you can:

- select a numbered option,
- type `a` to ask the architect a follow-up,
- type `o` to choose an option not in the generated list,
- type `d` to defer.

For mature production work, avoid deferring choices that block data/security/deployment architecture.

### Non-interactive initialization

Useful for demos/CI experiments:

```bash
sdd init --agent cursor --project-kind new --yes
```

`--yes` accepts the agent recommendation (or the first option when there is no recommendation). It is not recommended for consequential architecture on a real product unless constraints are already fully specified.

## Configure deterministic checks and execution policy

For the mock adapter, editing `.sdd/config.yaml` is enough:

```yaml
test_command: "pytest -q"
lint_command: "ruff check ."
typecheck_command: "mypy src"
max_repair_attempts: 3
```

For real agents (cursor/codex/claude), `sdd start` additionally requires an
approved execution policy and an execution branch (see PROJECT_LIFECYCLE.md):

```bash
sdd project inspect
sdd project setup
# or: sdd project configure --file workspace-policy.yaml
git add . && git commit -m "Approve project baseline"
sdd repo branch <scope>
```

Use the commands your application actually relies on. Vega SDD deliberately does not guess one universal test stack.

## Inspect generated intent before coding

```bash
sdd requirements
sdd architecture
sdd roadmap
sdd feature F001
sdd verify
```

For high-risk products, review these before `sdd start`. The framework automates preparation but does not remove human ownership of consequential product/architecture decisions.

## Start development

Real-agent runs require the approved `.sdd/workspace.yaml` and execution
branch above; otherwise `sdd start` fails with
`Approve a project policy before real-agent execution: sdd project setup`
or `Protected branch: create an execution branch`.

```bash
sdd start
```

Use a bounded smoke run first:

```bash
sdd start --max-tasks 1
```

Then inspect:

```bash
sdd status
sdd log --limit 30
```

If the first task's behavior/evidence looks correct, resume:

```bash
sdd resume
```

## Monitor progress

One-time status:

```bash
sdd status
```

Continuous display:

```bash
sdd watch
```

Status intentionally distinguishes "code was written" from "the requirement is verified."

## Pause safely

If `sdd start` is in the foreground, Ctrl+C asks the current process to stop and persists a paused state.

From another controller invocation:

```bash
sdd pause
```

The V1 scheduler honors the request at a task boundary. It does not attempt unsafe mid-write process surgery from a separate terminal.

## Resume after clearing context or changing agents

```bash
sdd resume
```

A previous coding-agent conversation is not needed. The controller uses canonical state, feature/task files, specs, journal, and repository contents.

To switch:

```bash
sdd agent list
sdd agent use claude
sdd resume
```

## Ask a project question

```bash
sdd ask "Which module persists a new task?"
```

`sdd ask` is read-only. It grounds the answer in approved specs, ADRs, and a Graphify query when `graphify-out/graph.json` exists. It does not rewrite requirements or mark tasks complete.

## Refresh the knowledge graph

Install the Graphify CLI (`pip install graphifyy`), then:

```bash
sdd graph refresh
sdd graph query "task creation persistence"
```

The first refresh runs `graphify extract <project> --code-only --no-cluster` (local AST, no model API). Later refreshes run `graphify update`. SDD also writes `graphify-corpus/sdd-traceability.md` so requirement and task identity stays next to the code graph. Canonical execution state remains `.sdd/state/`.

Headroom (`pip install headroom-ai`) compresses context packs and check logs before they enter implement, review, repair, and ask prompts. The uncompressed text stays under `.sdd/runtime/originals/`. `sdd doctor` reports both tools. Missing either one does not block a run, and a run never stops because a token estimate crossed a cap.

## Skills

```bash
sdd scaffold
```

Scaffold writes runbooks under `.agents/skills/`. A later `sdd scaffold` adds missing skills and replaces earlier framework checklists that still use the old frontmatter and lack a failure-mode section. A skill you rewrote without that frontmatter is left in place. `sdd scaffold --force` overwrites scaffold-managed files.

Agent prompts include the skill name and its routing description. The agent reads `.agents/skills/<name>/SKILL.md` when the task matches. The controller does not paste the full runbook into every prompt.

## Clarifications and retries

Unresolved material questions block `sdd start` until they are answered:

```bash
sdd clarify
sdd clarify Q1 --answer "Owners may export their own workspace only."
sdd start --accept-deferred
```

`--accept-deferred` only signs an item that already has an explicit default or option ID. Placeholder answers such as `Deferred` cannot resolve architecture. All defaults are validated first; a missing default rolls nothing back because nothing was written. For architecture, a valid default writes the recommended option onto the decision and ADR.

A failed task stays out of the scheduler until you retry it. `--keep-code` requeues verification without discarding the working tree:

```bash
sdd task retry TASK-F001-003 --keep-code
```

## Intervene when something feels wrong

```bash
sdd pause
sdd intervene
```

Examples:

```text
architect> Why is this preference stored on the account instead of the profile?
architect> Which requirement allowed this endpoint to be public?
architect> What would break if we removed Redis?
```

For a suspected change/defect:

```text
architect> change: every family profile needs an independent language preference
```

This analyzes impact but does not silently rewrite specs.

## Apply a correction/change

```bash
sdd change "Every family profile needs an independent language preference"
```

If it is an implementation defect, a repair task is created automatically.

If it changes approved intent, SDD prints impact and asks for explicit approval. After reconciliation:

```bash
sdd verify
sdd status
sdd resume
```

## Change the primary agent

```bash
sdd agent use cursor
sdd agent use gemini
sdd agent use copilot
```

The adapter change does not rewrite PRD, requirements, architecture, or state.

Run `sdd doctor` if the chosen agent does not start correctly after a vendor CLI upgrade.

## Existing repositories

Use:

```bash
sdd init --project-kind existing
```

Initialization captures lightweight repo/Git context and supplies it to product/architecture/specification prompts. V1 does not attempt a perfect static reverse-engineering of arbitrary legacy code; therefore, on important brownfield systems, review generated specs against tests and current runtime behavior before autonomous implementation.

## Configuration reference

`.sdd/config.yaml` includes:

- `project_name`
- `project_kind`
- `prd_path`
- `primary_agent`
- `autonomous_implementation`
- `require_approval_for_spec_changes`
- `require_approval_for_architecture_changes`
- `max_repair_attempts`
- `test_command`
- `lint_command`
- `typecheck_command`
- `allow_unrestricted_agent` (default false; opt-in for Cursor `--force`, Gemini `--yolo`, Copilot `--allow-all`)
- `max_review_files` (default 15; a larger change set fails closed until the task is split or the owner raises the bound)

The approval flags document project policy. V1's CLI enforces approval for classified spec/requirement/architecture mutation. Unrestricted agent flags stay off unless the owner sets the config field or passes `sdd start --allow-unrestricted` for that process. Isolate that run; the git guard cannot prevent secret reads or network use.

## Effective operating pattern

For best results:

1. Give SDD product intent, not implementation micromanagement.
2. Make non-negotiables explicit before architecture selection.
3. Review the architecture and first generated feature before a long autonomous run.
4. Configure deterministic tests early.
5. Keep tasks bounded; split oversized work.
6. Use fresh agent contexts deliberately instead of carrying huge chats forever.
7. Use `intervene` for diagnosis and `change` for intent mutation.
8. Never repair bad implementation by manually weakening a requirement or test.
9. Switch coding agents at clean boundaries when possible.
10. Keep `.sdd/` and `.agents/` version-controlled.

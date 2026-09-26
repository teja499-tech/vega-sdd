# Vega SDD

**Keep the project in the repo. Put coding agents to work on it.**

Vega SDD is an open source, repository-owned framework for planning, implementing, reviewing, and releasing software with AI coding agents. It connects product intent, human-readable design, tasks, checks, changes, and release evidence so a project can continue across sessions and agent tools.

> **Status:** 0.3.0 alpha. The controller and mock adapter have local test coverage. Real coding-agent CLIs, GitHub hosting controls, deployed environments, and non-Linux platforms still require validation in your own setup. [See verification notes](docs/VERIFICATION_0.2.0.md).

## Start here

Requires Python 3.11 or later. Install the package, then run commands in a project repository:

```bash
python -m pip install vega-sdd
sdd doctor
cd path/to/your-project
sdd init
sdd status
```

For a deterministic trial without a coding-agent login, create a disposable project with a `PRD.md` and run:

```bash
sdd init --agent mock --project-kind new --yes
sdd verify
sdd start
```

The mock adapter exercises the workflow; it does not implement production code. For real work, use `sdd doctor` to inspect installed agent CLIs, choose an adapter during initialization, and configure the project's actual check commands before starting. See the [user guide](docs/USER_GUIDE.md).

## What it manages

| Stage | Repository-owned result |
| --- | --- |
| Discover | Product questions, requirements, acceptance criteria, and a roadmap |
| Design | System overview, architecture decisions, high and low level design, and data design where applicable |
| Build | Dependency-ordered tasks and bounded agent work |
| Verify | Project-specific tests, review and repair evidence |
| Change | Human-readable change history tied to tasks and actual commits |
| Deliver | Branch and PR policies, CI templates, release criteria and environment receipts |

The generated documents describe the approved project state; they are not proof that an agent's proposed design is correct. Humans approve material requirement and architecture changes. Vega SDD does not replace your Git host, CI service, cloud provider, or repository access controls.

## Project fit

The project policy supports new and existing applications, APIs, libraries, CLIs, data pipelines, infrastructure, utilities, frameworks, and monorepos. Each project supplies its own verification and deployment commands. An existing project can be adopted with `sdd init --project-kind existing`; the framework does not assume every project has a database or deployment environment.

The [lifecycle guide](docs/PROJECT_LIFECYCLE.md) documents project-kind policies, branching and PR gates, CI exports, releases, and deployment receipts. The [design documentation guide](docs/HUMAN_DOCUMENTATION.md) covers generated artifacts and commit-linked history.

## Day-to-day commands

```bash
sdd status                 # spec, implementation and verification progress
sdd watch                  # follow durable project state
sdd start                  # work through ready tasks
sdd pause                  # stop at a task boundary
sdd resume                 # continue from repository state
sdd intervene              # discuss a concern with the architecture role
sdd change "Describe it"  # classify and route a defect or approved change
sdd agent use codex        # select the primary coding agent
```

Run `sdd --help` for the full command list. The project state lives under `.sdd/`, with reusable roles and skills under `.agents/`. Vendor-specific files are thin adapters. One primary coding agent writes at a time; separate reviewer roles and deterministic checks inspect the work.

## Documentation

| Guide | Covers |
| --- | --- |
| [Getting started](docs/USER_GUIDE.md) | Project initialization and everyday use |
| [Project lifecycle](docs/PROJECT_LIFECYCLE.md) | Project kinds, checks, branches, PRs, CI and deployment |
| [Design and history](docs/HUMAN_DOCUMENTATION.md) | Human-readable design and commit-linked changelog |
| [Architecture](docs/ARCHITECTURE.md) | Controller, agents and durable state |
| [Specification model](docs/SPEC_MODEL.md) | Requirement, feature and task identity |
| [Agent adapters](docs/AGENT_ADAPTERS.md) | Cursor, Codex, Claude Code and mock boundaries |
| [Verification](docs/VERIFICATION_0.2.0.md) | Local results and remaining qualification |
| [Research and gaps](docs/RESEARCH_AND_GAPS.md) | Cross-project design rationale |

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) for a local setup and review expectations, [SECURITY.md](SECURITY.md) for reporting vulnerabilities, and [CHANGELOG.md](CHANGELOG.md) for releases. The project is licensed under [Apache 2.0](LICENSE).

```bash
python -m pip install -e '.[dev]'
python -m pytest tests
python -m build
```

Report bugs and feature requests through [GitHub Issues](https://github.com/teja499-tech/vega-sdd/issues). Include the CLI version, OS, Python version, project kind, agent adapter, reproduction steps and redacted logs.

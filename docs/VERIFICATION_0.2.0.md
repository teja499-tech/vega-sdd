# Universal SDD 0.2.0 — verification and qualification

This release was rebuilt after a transient workspace interruption from the retained 0.1.2 source archive. The earlier unsaved 0.2.0 tree and its 165-test run were lost; they are **not** evidence for this rebuilt package. The counts below describe only the rebuilt wheel tested again on 2026-09-26.

## Rebuilt package and evidence

Python 3.12.14 and Linux were used. The wheel was built with `python -m build --wheel --no-isolation`, installed into a separate `venv --system-site-packages` environment with `pip --no-deps`, and imported from its site-packages. This confirms the wheel is installable and exercises its installed code; it does not independently resolve runtime dependencies in a clean offline environment.

The full test suite consists of the retained 0.1.2 tests and new project lifecycle regression tests. See `audit-v020/pytest-wheel.txt` and `audit-v020/coverage.json` for the exact final count and coverage. Local fixtures:

- Scripted service lifecycle: actual CLI subprocesses, interactive architecture choice, task pause/resume in a new process, seeded authentication defect and automatic repair, approved specification change, human documentation/changelog and real SQLite/HTTP acceptance tests. The coding agent and reviewer are scripted subprocess fixtures.
- Brownfield extension: original source, README, SECURITY and CHANGELOG preserved; changed HLD/API docs and local Git task attribution. Missing operational facts remain visible.
- Four separate local projects: Python library public API compatibility; CLI Unicode/exit-code behavior; SQLite pipeline upsert/transaction/replay; Node HTTP status and basic HTML label/language checks. Each runs the exported standalone CI runner, builds an immutable ZIP, promotes its digest via local staging and production hooks, confirms repeated delivery is idempotent, detects a seeded regression and verifies again after repair. The HTML assertions are not WCAG certification.
- Repository tests: protected branch/worktree/dirty-source safeguards, policy/source freshness, release-only versus task checks, immutable artifact hash, approval and promotion, uncertain deployment reconciliation, required PR review/check/head gates, subprocess provider with an actual local bare Git remote, and non-overwriting generated workflows.

The research and current gap disposition are in [RESEARCH_AND_GAPS.md](RESEARCH_AND_GAPS.md). Human documentation retained from 0.1.2 is in [HUMAN_DOCUMENTATION.md](HUMAN_DOCUMENTATION.md); current operation is in [PROJECT_LIFECYCLE.md](PROJECT_LIFECYCLE.md).

## Qualification still needed for a specific enterprise repository

No authenticated live Codex, Cursor or Claude CLI was installed here. No live GitHub, GitLab or Azure CI/PR run, cloud deployment, signing identity, package registry, mobile/desktop/embedded target, Terraform backend, ML registry or actual host branch policy was configured or exercised. GitHub is the only native hosted PR provider. GitLab/Azure pipeline files are templates; other PR hosts require a real integration of the trusted JSON provider contract. The downloadable GitHub artifact action SHA could not be independently checked against its official commit endpoint here, so inspect pins and GHES support before enabling the generated delivery workflow.

The controller's protected-file snapshots detect/restores local agent mistakes; they are not an OS sandbox, tamper-proof audit log or protection against an agent's external side effects. Agent adapter command shapes and bounded processes were tested locally, but real provider versions/approval behavior must be qualified. Recovery snapshots pause execution and invalidate quality evidence; they do not roll back code, real deployments or Git history. Provider cost quotas, long-running schedulers and signed provenance are not built in.

The owner must add meaningful tests/waivers for its risk: migrations/backfills, secrets, dependency/SAST/license/SBOM scanning, privacy, load, observability, support escalation, retention, disaster recovery, semantic design review and the correct build/signing/store release process. Design documents and check labels alone cannot certify an application. Avoid claiming an enterprise-ready deploy until host policy, selected agents and the actual runtime are tested.

## Reproduction

```bash
python -m pip install '.[dev]' build
python -m pytest tests -o addopts='' -q --cov=universal_sdd --cov-report=term
python examples/incident-service/run_benchmark.py /tmp/incident-new
python examples/incident-service/verify_documentation.py /tmp/incident-new /tmp/brownfield-new
python examples/cross-projects/run_benchmarks.py /tmp/cross-new
python -m build --wheel --no-isolation
```

All benchmark destinations must be fresh. The web fixture requires Node.js; other fixtures use the Python standard library and local Git. Older `audit/` and `audit-v012/` directories are historical evidence for earlier releases.

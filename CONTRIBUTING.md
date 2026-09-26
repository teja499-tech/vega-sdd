# Contributing to Vega SDD

Thanks for improving the framework. Please open an issue before a large behavior or schema change so the scope and compatibility path can be discussed.

## Local setup

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]' build 'setuptools>=77'
python -m pytest tests
python examples/incident-service/run_benchmark.py /tmp/vega-incident
python examples/cross-projects/run_benchmarks.py /tmp/vega-cross
python -m build --no-isolation
```

The mock adapter makes framework tests deterministic. Real Cursor, Codex and Claude Code adapters also need hands-on checks with installed provider CLIs.

## Branch and pull request process

1. Branch from `main`; use a short descriptive name such as `feat/receipt-links` or `fix/resume-state`.
2. Add a focused test for controller behavior or state changes. Update user-facing docs and the `Unreleased` changelog section when behavior changes.
3. Run the relevant tests and package build. Include the commands and results in the PR description.
4. Link the issue or spec when one exists. Describe affected project kinds, migration and rollback considerations, and any agent-adapter assumptions.
5. Request review. A reviewer should inspect spec compatibility, state recovery and evidence semantics as well as the implementation. Merge after required checks and reviews pass.

Maintainers must configure branch protection and review rules in GitHub. A YAML workflow alone does not enforce a branch policy.

## Design principles

- Keep `.sdd` semantics independent of coding-agent vendors.
- Keep provider adapters small and isolated.
- Never treat an agent's self-report as the only proof of a state transition.
- Use stable IDs when reconciling an approved change.
- Ask humans for material product and architecture decisions; keep ordinary implementation review moving.
- Do not include credentials, real customer data or generated `.sdd/runtime` state in a PR.

## Licensing

By contributing, you agree to license your contribution under the repository's Apache-2.0 license.

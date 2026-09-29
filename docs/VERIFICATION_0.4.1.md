# Vega SDD 0.4.1 verification

This document records the reproducible qualification performed for the 0.4.1 source tree on 2026-09-29. It is evidence for the framework controller and deterministic fixtures, not certification of a live coding provider, cloud deployment, or a user's application.

## Release identity

- Distribution: `vega-sdd`
- CLI: `sdd`
- Python import: `universal_sdd`
- Source and package version: `0.4.1`
- License expression: `Apache-2.0`

## Automated framework suite

```bash
PYTHONPATH=src python -m pytest tests
```

Result:

```text
228 passed in 83.85s
```

The new reconcile coverage includes exact stored-request approval, affected-ID scope enforcement, rejection of controller-owned status, explicit deletion, top-level policy regression checks, no-op rejection, safe change IDs, preservation of manual projection files, pending state for new tasks, staged-input cleanup, and staged-context token estimates.

## Incident lifecycle and documentation

Use fresh destination paths:

```bash
PYTHONPATH=src python examples/incident-service/run_benchmark.py /tmp/vega-incident
PYTHONPATH=src python examples/incident-service/verify_documentation.py \
  /tmp/vega-incident /tmp/vega-brownfield
```

Result: the scripted lifecycle completed initialization, execution, automatic repair, approval-based requirement reconcile, re-execution, final verification, and project checks. The documentation extension linked a real local Git commit, refreshed generated docs, preserved the brownfield repository files, and reported the intentionally unresolved operational gaps with the expected exit code `2`.

The fixture is a deterministic subprocess agent. It does not certify Cursor, Codex, Claude, Gemini, Copilot, or any hosted provider.

## Cross-project contracts

```bash
PYTHONPATH=src python examples/cross-projects/run_benchmarks.py /tmp/vega-cross
```

Result: Python library, CLI utility, SQLite pipeline, and Node web fixtures passed their configured checks and local staging/production file-copy deployment. Each fixture detected its seeded regression and recovered after the fixture restored the source.

## Distribution build and clean install

```bash
python -m build
python -m venv /tmp/vega-install
/tmp/vega-install/bin/pip install dist/vega_sdd-0.4.1-py3-none-any.whl
cd /tmp
/tmp/vega-install/bin/python -c "import universal_sdd; print(universal_sdd.__version__)"
/tmp/vega-install/bin/sdd --help
```

Result:

```text
Successfully built vega_sdd-0.4.1.tar.gz and vega_sdd-0.4.1-py3-none-any.whl
0.4.1
Usage: sdd [OPTIONS] COMMAND [ARGS]...
```

The wheel contained all 18 packaged `SKILL.md` runbooks plus `LICENSE` and `NOTICE`. Archive inspection found no `.git`, `.env`, audit, build, or distribution directories in the sdist. Metadata and the console entry point were inspected after the build.

## Reconcile safety boundary

Approved specification changes remain human-authorized. The reconciliation agent is read-only and can propose only structured slices. The controller:

1. validates update and removal IDs against the approved change scope;
2. binds approval to the exact stored change request identified by `--approve-id`, without re-running analysis;
3. rejects agent-supplied runtime status, evidence, check commands, and working state;
4. validates changed requirements, features, tasks, product fields, design documents, architecture summary, test strategy, security principles, and release criteria;
5. rejects an unchanged result instead of marking the change applied;
6. validates traceability before canonical mutation;
7. removes staged bundle/ADR inputs after the call; and
8. includes staged input text when provider usage is unavailable and tokens must be estimated.

Historical thin brownfield objects are not forced through a full rewrite, but an affected slice cannot remove an existing contract or bypass the checks above.

## Remaining boundaries

- Live provider authentication, model behavior, and provider-reported token usage require environment-specific qualification.
- Graphify and Headroom are optional. Their absence does not block correctness, and neither is an authority source.
- The hosted `main` branch is protected by an active ruleset with required pull requests, Python 3.11/3.12 CI, up-to-date branches, resolved conversations, linear history, and force-push/deletion blocking. PyPI trusted publishing, deployment hooks, and application-specific security remain repository/operator responsibilities.
- The Node fixture checks basic language and form-label properties; it is not a complete accessibility audit.

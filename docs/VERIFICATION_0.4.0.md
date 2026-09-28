# Vega SDD 0.4.0 verification

This document records reproducible framework evidence. It is not certification of every coding-agent provider, operating system, Git host, or application built with Vega.

## Verified baseline

The capability and integrity implementation was independently reviewed at commit `0dbf8f587cf06857bd889c2743e4dd6d20cd2ae3`. The review found no remaining blocker or high-severity issue in the requested capability-routing, initialization-isolation, approval, mutation-guard, recovery, locking, and linked-worktree scope.

The final framework suite at that baseline contained **205 tests**.

```bash
python -m pytest -q
python -m compileall -q src tests
python -m build --wheel --sdist
git diff --check
```

Observed results:

```text
205 tests collected
205 tests passed
Successfully built vega_sdd-0.4.0-py3-none-any.whl
Successfully built vega_sdd-0.4.0.tar.gz
```

## GitHub Actions

[Framework checks run 18](https://github.com/teja499-tech/vega-sdd/actions/runs/36421471825) completed successfully on Python 3.11 and Python 3.12.

Each job ran:

1. package installation with development dependencies;
2. the complete test suite;
3. incident-service lifecycle benchmark;
4. documentation benchmark;
5. cross-project benchmarks;
6. wheel/source build.

## Incident-service lifecycle benchmark

The scripted benchmark exercises the controller lifecycle rather than a live coding provider. It covers initialization, project artifacts, task implementation/review/repair state, application acceptance checks, completion, and generated evidence.

Latest locally observed acceptance result before the documentation refresh:

```text
application tests exit 0
recorded events 75
repair events 1
final state completed
```

The benchmark intentionally seeds a defect so the repair path is exercised.

Run it:

```bash
python examples/incident-service/run_benchmark.py /tmp/vega-incident
python examples/incident-service/verify_documentation.py \
  /tmp/vega-incident /tmp/vega-brownfield
```

## Cross-project benchmarks

Four local project shapes are exercised:

| Fixture | Main behavior |
| --- | --- |
| Python library | Public API compatibility and packaging |
| CLI | Unicode/output and exit-code behavior |
| SQLite pipeline | Upsert, transaction, data-quality, and replay behavior |
| Node web | HTTP status and basic HTML label/language behavior |

Each fixture runs exported checks, creates an immutable artifact, deploys the same digest through local staging/production hooks, verifies idempotency, detects a seeded regression, and passes after repair.

```bash
python examples/cross-projects/run_benchmarks.py /tmp/vega-cross
```

These fixtures demonstrate stack-neutral contracts; they do not certify WCAG, cloud deployment, mobile devices, production databases, or every project kind.

## Adversarial integrity checks

Regression coverage includes:

- unapproved project-local skill descriptions not entering initialization prompts;
- initialization in an isolated framework workspace;
- source inspection through a bounded copy with common secret and provider instruction/configuration surfaces removed;
- capability approval invalidation for cross-provider instructions, skills, settings, hooks, and context filters;
- rejection of unsafe/missing/oversized/symlinked skills and task-selected lifecycle skills;
- security routing for OAuth/OIDC/JWT/password/PII/encryption/KMS/payment terminology;
- protected controller runtime and projection transaction records;
- fail-closed, evidence-preserving corrupt/incomplete projection recovery;
- original Git ref restoration after an agent branch switch;
- file-mode, tag, Git config, and hook restoration after read-only calls;
- Git common-directory restoration in linked worktrees;
- serialization of mutation, question, intervention, graph, clarification, and scaffold flows;
- positive-integer, operator-configurable snapshot bounds.

## Mock sample output

A disposable `PRD.md` initialized with `--agent mock --project-kind new --yes` produced:

```text
4/4 Readiness review
✓ Requirements: 1
✓ Features: 1
✓ Architecture decisions: 1
✓ Traceability: valid (0 warning(s))
Project is ready for implementation.
```

`sdd status` then reported specification 100%, implementation 0%, verification 0%, and run status `ready`. `sdd verify` reported:

```text
Traceability PASS (0 warning(s))
```

The documented five-minute journey was also replayed through `sdd start`. Its mock implementation and independent-review phases passed, and the final status reported one of one tasks and one of one requirements verified. This demonstrates the controller flow only; the mock adapter does not write production application code.

## Documentation validation

The current documentation refresh was checked for local Markdown targets and heading anchors, CLI command-group availability, whitespace errors, and inclusion in the source distribution. The complete 205-test suite, bytecode compilation, and wheel/source build continued to pass after the refresh.

## Packaging contents

The wheel contains the controller modules, all supported adapters, and all 18 packaged `SKILL.md` runbooks. A clean temporary installation imported version `0.4.0` successfully.

## What remains environment-specific

Validate these in the actual project environment before relying on them:

- live Cursor/Codex/Claude/Gemini/Copilot CLI versions and authentication;
- provider sandbox, network, and filesystem behavior;
- Windows/macOS behavior beyond the current Linux CI matrix;
- real GitHub rulesets, environments, merge queues, or a custom host provider;
- cloud credentials, deployment hooks, smoke checks, and rollback semantics;
- application-specific security, privacy, accessibility, performance, migration, data, hardware, and disaster-recovery requirements;
- semantic truth of generated architecture and human documentation.

Use `sdd doctor`, a one-task smoke run, `sdd project check`, host audits, and environment-specific tests before granting broader automation.

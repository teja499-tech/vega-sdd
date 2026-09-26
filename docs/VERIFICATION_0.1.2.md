# Universal SDD v0.1.2 — enterprise documentation update

Date: September 26, 2026

## Conclusion

The audited v0.1.1 package did **not** generate dedicated high-level, low-level or database designs. It produced a short architecture summary, ADRs, requirements, tasks and machine-oriented journal events. It did not provide a human-oriented task/spec changelog with explicit Git attribution.

v0.1.2 implements those missing documentation and history mechanisms. It remains an experimental development controller, not a fully certified enterprise software factory.

## What changed

| Capability | v0.1.1 finding | v0.1.2 implementation |
|---|---|---|
| Human system understanding | Short product and architecture prose | Indexed system overview, HLD, LLD, database and API designs |
| Operational documentation | Scattered test/release lists | Security, operations, test plan, contribution guidance and release plan contracts |
| Existing/full application adoption | Lightweight repository inventory | Explicit as-is/to-be documentation contract, evidence/unknowns, compatibility and migration sections; read-only enrichment |
| Documentation freshness | No dedicated document validator | Canonical source fingerprint, required section checks, gaps, applicability reasons, manual-edit detection |
| Human change history | JSONL events and change YAML | Readable changelog with task scope, requirements, evidence, approvals and invalidations |
| Exact specification history | Current spec state only | Immutable content-addressed snapshots plus transition diffs, linked to lifecycle events |
| Git traceability | No explicit task/commit association | Full SHA, author/date, subject, files and summary; local object/ancestry validation |
| Automatic attribution | Absent | Exact SDD-Task trailers in commits created between task-start HEAD and current HEAD |
| Enterprise root entry points | No common human entry point | Non-overwriting project guide, changelog/contributing/security entry points and PR template |

The design-generation prompt requests project-specific prose, tables and Mermaid diagrams. The example pack includes actual diagrams and database/API tables. The framework does not treat a document heading, populated prose or an agent's assertion as proof that a design has been implemented.

## Verification

- **94 framework tests passed**, including the original 75 tests and 19 documentation/history regressions.
- **91% statement coverage** (1,987 statements; 173 missed in the measured suite).
- The installed v0.1.2 wheel was used for the incident-service lifecycle: **16 CLI invocations** with real application tests, pause/resume, authentication-defect repair and approved title-limit change.
- **Six additional CLI invocations** exercised document checks/refresh, real Git commit linking, readable history and adoption into an existing application.
- The final incident-service suite contains **12 passing application acceptance tests**.
- Brownfield initialization preserved **seven pre-existing files byte-for-byte**, including source code, README, security policy and release history.
- Documentation checks intentionally returned exit 2 for unresolved production details. Those are expected validation outcomes, not ignored failures.

New tests cover legacy bundles, existing-system gaps, complete structural documentation, stale canonical input, manual-edit preservation, applicability reasons, exact A→B→A revision history, real Git metadata, invalid/unknown/unreachable commits, idempotent links, event-time task intent, automatic trailer attribution excluding unrelated commits, malformed enrichment responses, read-only enrichment and traceability refresh after verification.

The code tests use structural fixtures where appropriate. The lifecycle uses a separately authored incident-service design fixture with concrete API, schema and operations details. Agent output remains scripted. Git operations, HTTP requests, application execution, filesystem-preservation checks and CLI subprocesses are real.

## Reproduce

From the source archive:

```bash
python -m pip install -e '.[dev]'
python -m pytest -o addopts='' tests -q
python examples/incident-service/run_benchmark.py /tmp/sdd-example-new
python examples/incident-service/verify_documentation.py \
  /tmp/sdd-example-new /tmp/sdd-example-existing
```

Use fresh destination directories. The documentation benchmark expects exit 2 for known production gaps. Evidence is under `audit-v012/`; the older `audit/` and `docs/VERIFICATION_REPORT.md` belong to v0.1.1. Generated example documents are under `audit-v012/benchmark/.sdd/docs/`, and its human history is `.sdd/CHANGELOG.md`.

## Usage and compatibility

Existing SDD state remains readable. Upgrade the package, then run:

```bash
sdd docs refresh --enrich
sdd docs check
sdd changelog
```

Enrichment requires an installed, authenticated coding agent. It changes only descriptive design content and retains a spec snapshot; it does not approve changed requirements or architecture. The usual `sdd change` flow remains authoritative for intent changes.

A completed application uses `sdd init --project-kind existing` with its PRD. Documentation describes known behavior and the target design. Adoption does not automatically mark existing code or generated tasks verified.

See [HUMAN_DOCUMENTATION.md](HUMAN_DOCUMENTATION.md) for all generated files, commands, conflict handling, commit trailers, manual links and limitations.

## Remaining limitations

- No authenticated live Codex/Cursor/Claude run has been certified here. Tests establish the controller contract, not autonomous model output quality.
- Structural documentation checks cannot certify factual prose, source references, diagram correctness or semantic agreement with code. Code changes require documentation enrichment/review; source fingerprints detect canonical spec drift only.
- Generated runbooks with unresolved owners, recovery targets or production commands remain drafts. This example intentionally has such gaps.
- The local journal and history files are not a tamper-proof compliance store. HEAD context is never presented as task ownership without attribution.
- Narrative LLD/API changes still depend on the reconciliation agent returning correct updated design content. The benchmark proves the lifecycle writes the supplied updates.
- Research provenance, adaptive architecture workshops, journal replay recovery, stronger agent isolation and an objective release evaluator remain prior-audit gaps.
- CI/CD pipelines, branch protection, SBOM/signing, security scanning, CODEOWNERS, licensing, operational ownership and production approvals need project-specific implementation and evidence. This update documents relevant expectations without pretending they are configured.

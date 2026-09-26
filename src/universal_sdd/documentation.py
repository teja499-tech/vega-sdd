"""Human documentation projections. Canonical intent remains in the structured spec."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .models import SpecBundle
from .storage import SDDPaths, atomic_write, load_yaml, dump_yaml

CONTRACT = {
    'SYSTEM_OVERVIEW': ['Purpose and scope', 'Users and workflows', 'System boundaries'],
    'HLD': ['Components and responsibilities', 'Interactions and data flows', 'Deployment topology', 'Quality attributes and tradeoffs'],
    'LLD': ['Modules and interfaces', 'Key execution flows', 'Validation and failure handling', 'Concurrency and idempotency'],
    'DATABASE_DESIGN': ['Entities and relationships', 'Fields and constraints', 'Indexes and access patterns', 'Migrations and retention'],
    'API_DESIGN': ['Contracts and authentication', 'Requests and responses', 'Errors and compatibility'],
    'SECURITY': ['Trust boundaries and threats', 'Access control and secrets', 'Privacy and audit'],
    'OPERATIONS': ['Configuration and deployment', 'Monitoring and alerts', 'Backup and restore', 'Incident response and rollback'],
    'TEST_PLAN': ['Acceptance and integration', 'Performance and security', 'Test data and environments'],
    'EXISTING_SYSTEM': ['Observed current behavior', 'Evidence and unknowns', 'Intended changes and compatibility', 'Migration and rollback'],
    'CONTRIBUTING': ['Local setup', 'Development and review workflow', 'Ownership and escalation'],
    'RELEASE_PLAN': ['Release criteria', 'Versioning and release notes', 'Rollout and rollback'],
}


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def source_digest(paths: SDDPaths) -> str:
    data = {p.name: load_yaml(p, {}) for p in [paths.spec_bundle_file, paths.architecture_decisions_file]}
    return digest(json.dumps(data, sort_keys=True, default=str))


def issues(bundle: SpecBundle, kind: str) -> list[str]:
    result = []
    for key, headings in CONTRACT.items():
        doc = bundle.design_documents.get(key)
        if key == 'EXISTING_SYSTEM' and kind == 'new' and doc is None:
            continue
        if doc is None:
            result.append(f'{key}: design content missing')
            continue
        if doc.status == 'not_applicable':
            if len(doc.not_applicable_reason.strip()) < 15:
                result.append(f'{key}: applicability reason missing or too short')
            continue
        if doc.status != 'documented':
            result.append(f'{key}: draft, not documented')
        if not doc.summary.strip() or not doc.sources:
            result.append(f'{key}: summary or source references missing')
        for heading in headings:
            text = doc.sections.get(heading, '').strip()
            if len(text) < 30 or text.lower() in {'todo', 'tbd', 'unknown'}:
                result.append(f'{key}: incomplete section {heading}')
        result.extend(f'{key}: {gap}' for gap in doc.gaps)
    result.extend(f'Unknown document key: {key}' for key in bundle.design_documents if key not in CONTRACT)
    return result


def render_docs(paths: SDDPaths) -> list[str]:
    bundle = SpecBundle.model_validate(load_yaml(paths.spec_bundle_file))
    config = load_yaml(paths.config_file, {}) or {}
    kind = config.get('project_kind', 'new')
    docs = paths.sdd / 'docs'
    docs.mkdir(parents=True, exist_ok=True)
    manifest_path = paths.state / 'documentation.yaml'
    manifest = load_yaml(manifest_path, {}) or {}
    hashes = manifest.get('files', {})
    conflicts = []
    generated = {}
    fingerprint = source_digest(paths)

    def write(name, text):
        path = docs / name
        previous = hashes.get(name)
        if path.exists() and digest(path.read_text()) != previous:
            conflicts.append(f'{name}: manual edits preserved; move edits into canonical design_documents or a companion file, then remove the generated file to refresh')
            return
        atomic_write(path, text)
        generated[name] = digest(text)

    intro = (f'Project: {bundle.product.name}\n\nSource revision: `{fingerprint}`\n\n'
             'Generated descriptive documentation. Documented means structurally populated; it does not mean independently reviewed, implemented, or release certified.\n\n')
    for key, headings in CONTRACT.items():
        doc = bundle.design_documents.get(key)
        text = f'# {key.replace("_", " ").title()}\n\n' + intro
        if key == 'EXISTING_SYSTEM' and kind == 'new' and doc is None:
            text += 'Status: Not applicable — explicitly initialized as a new project; no existing-system baseline claimed.\n'
        elif doc:
            text += f'Status: {doc.status}\n\n{doc.summary}\n\n'
            if doc.status == 'not_applicable':
                text += f'Applicability: {doc.not_applicable_reason}\n'
            else:
                for heading in headings:
                    text += f'## {heading}\n\n{doc.sections.get(heading) or "Unresolved — no design supplied."}\n\n'
                for heading, content in doc.sections.items():
                    if heading not in headings:
                        text += f'## {heading}\n\n{content}\n\n'
            text += '## Sources\n\n' + '\n'.join(f'- {x}' for x in doc.sources) + '\n\n'
            text += '## Open gaps\n\n' + ('\n'.join(f'- {x}' for x in doc.gaps) or 'None recorded; review still required.') + '\n'
        else:
            text += 'Status: INCOMPLETE — agent did not supply this design.\n\n'
            for heading in headings:
                text += f'## {heading}\n\nUnresolved — no design supplied.\n\n'
        if key == 'SYSTEM_OVERVIEW':
            text += '\n## Canonical product summary\n\n' + bundle.product.summary + '\n\n' + '\n'.join(f'- {u}' for u in bundle.product.users) + '\n'
        if key == 'HLD':
            text += '\n## Canonical architecture summary\n\n' + bundle.architecture_summary + '\n\n[Architecture decisions](../architecture/decisions.md)\n'
        if key == 'TEST_PLAN':
            text += '\n## Approved test strategy\n\n' + '\n'.join(f'- {x}' for x in bundle.test_strategy) + '\n'
        if key == 'RELEASE_PLAN':
            text += '\n## Approved release criteria\n\n' + '\n'.join(f'- {x}' for x in bundle.release_criteria) + '\n'
        write(key + '.md', text)
    features = load_yaml(paths.features_file, []) or []
    rows = ['# Requirements Traceability', '', '| Requirement | Feature | Task | Status | Evidence |', '|---|---|---|---|---|']
    for req in bundle.requirements:
        matched = False
        for feature in features:
            for task in feature.get('tasks', []):
                if req.id in task.get('implements', []):
                    matched = True
                    values = [req.id, feature['id'], task['id'], task['status'], ', '.join(task.get('evidence', [])) or 'Not recorded']
                    rows.append('| ' + ' | '.join(str(v).replace('|', '\\|').replace('\n', ' ') for v in values) + ' |')
        if not matched:
            rows.append(f'| {req.id} | Unmapped | Unmapped | Unverified | None |')
    rows += ['', '[Human change history and commit links](../CHANGELOG.md)', '']
    write('TRACEABILITY.md', '\n'.join(rows))
    findings = issues(bundle, kind)
    index = ['# Project Documentation', '', intro, '## Reading order', '']
    index += [f'- [{key.replace("_", " ").title()}]({key}.md)' for key in CONTRACT]
    index += ['- [Traceability](TRACEABILITY.md)', '- [Human changelog](../CHANGELOG.md)', '- [Live status](../STATUS.md)', '', '## Documentation gaps', '']
    index += [f'- {x}' for x in findings] or ['No structural gaps detected. Semantic review and operational validation remain required.']
    write('README.md', '\n'.join(index) + '\n')
    dump_yaml(manifest_path, {'source_digest': fingerprint, 'files': {**hashes, **generated}, 'conflicts': conflicts, 'gaps': findings})
    # Add discoverable entry points without replacing any enterprise-owned file.
    entrypoints = {
        'SDD_PROJECT.md': '# Project engineering guide\n\nStart with [human project documentation](.sdd/docs/README.md), then [live status](.sdd/STATUS.md) and [change history](.sdd/CHANGELOG.md).\n\nGenerated documents distinguish planned design from observed implementation. Run `sdd docs check` to inspect gaps.\n',
        'CHANGELOG.md': '# Changelog\n\n[SDD task, specification and commit history](.sdd/CHANGELOG.md). Release tagging and release approval remain separate activities.\n',
        'CONTRIBUTING.md': '# Contributing\n\nSee [project contribution guidance](.sdd/docs/CONTRIBUTING.md), [traceability](.sdd/docs/TRACEABILITY.md) and AGENTS.md. Use `sdd change` for intent changes. Include `SDD-Task: <task-id>` as a Git commit trailer on authorized task commits.\n',
        'SECURITY.md': '# Security\n\nSee [security design](.sdd/docs/SECURITY.md). Private vulnerability reporting contact and response ownership are not configured by SDD; project owners must provide them before public release. Do not publish secrets in issues.\n',
        '.github/pull_request_template.md': '## What changed and why\n\n## Requirements, specs, tasks and change requests\n\n## Verification evidence\n\n## Compatibility, migration and rollback\n\n## Documentation and security impact\n',
    }
    for name, text in entrypoints.items():
        path = paths.root / name
        if not path.exists():
            atomic_write(path, text)
    return findings + conflicts


def check_docs(paths: SDDPaths) -> list[str]:
    manifest = load_yaml(paths.state / 'documentation.yaml', {}) or {}
    bundle = SpecBundle.model_validate(load_yaml(paths.spec_bundle_file))
    config = load_yaml(paths.config_file, {}) or {}
    findings = issues(bundle, config.get('project_kind', 'new'))
    if manifest.get('source_digest') != source_digest(paths):
        findings.append('Documentation source revision is stale; run sdd docs refresh')
    findings.extend(manifest.get('conflicts', []))
    for name in [k + '.md' for k in CONTRACT] + ['README.md', 'TRACEABILITY.md']:
        path = paths.sdd / 'docs' / name
        if not path.exists():
            findings.append(f'{name}: file missing')
        elif digest(path.read_text()) != manifest.get('files', {}).get(name):
            findings.append(f'{name}: manual modification detected')
    return findings

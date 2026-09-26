"""Human history with explicit, locally verified commit attribution."""
from __future__ import annotations
import difflib
import json
import re
import subprocess
from pathlib import Path

from .models import utcnow
from .storage import SDDPaths, atomic_write, load_yaml, dump_yaml


def git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(['git', *args], cwd=root, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return ''
    return result.stdout.strip() if result.returncode == 0 else ''


def git_context(root: Path) -> dict:
    head = git(root, 'rev-parse', '--verify', 'HEAD')
    return {'head': head or None, 'branch': git(root, 'branch', '--show-current') or None,
            'working_tree': git(root, 'status', '--porcelain') if head else 'No committed HEAD available'}


def snapshot_specs(paths: SDDPaths) -> str:
    """Retain immutable full canonical snapshots plus exact diffs, including initial import."""
    data = {name: load_yaml(path, {}) for name, path in [('bundle', paths.spec_bundle_file), ('decisions', paths.architecture_decisions_file)]}
    text = json.dumps(data, indent=2, sort_keys=True, default=str) + '\n'
    import hashlib
    revision = hashlib.sha256(text.encode()).hexdigest()
    folder = paths.sdd / 'history' / 'specs'
    folder.mkdir(parents=True, exist_ok=True)
    index_path = paths.state / 'spec-history.yaml'
    index = load_yaml(index_path, []) or []
    if index and index[-1]['revision'] == revision:
        return revision
    prior = (folder / (index[-1]['revision'] + '.json')).read_text() if index else ''
    atomic_write(folder / (revision + '.json'), text)
    # Full snapshots use content addresses; each transition gets its own diff (supports A→B→A).
    transition = f'{len(index)+1:06d}'
    atomic_write(folder / (transition + '.diff'), ''.join(difflib.unified_diff(prior.splitlines(True), text.splitlines(True), fromfile='before', tofile='after')))
    index.append({'revision': revision, 'transition': transition, 'timestamp': utcnow(), 'git': git_context(paths.root)})
    dump_yaml(index_path, index)
    return revision


def link_commit(paths: SDDPaths, task_id: str, commit: str, summary: str) -> dict:
    tasks = {t['id']: t for f in load_yaml(paths.features_file, []) for t in f.get('tasks', [])}
    if task_id not in tasks:
        raise ValueError(f'Unknown task: {task_id}')
    if not re.fullmatch(r'[a-fA-F0-9]{7,64}', commit):
        raise ValueError('Supply a hexadecimal commit SHA (at least 7 characters), not a branch or option')
    sha = git(paths.root, 'rev-parse', '--verify', commit + '^{commit}')
    if not sha:
        raise ValueError('Commit does not resolve to a local Git commit')
    reachable = subprocess.run(['git', 'merge-base', '--is-ancestor', sha, 'HEAD'], cwd=paths.root, capture_output=True)
    if reachable.returncode != 0:
        raise ValueError('Commit is not reachable from the current HEAD')
    if not summary.strip():
        raise ValueError('A human change summary is required')
    file = paths.state / 'commit-links.yaml'
    entries = load_yaml(file, []) or []
    existing = next((e for e in entries if e['task'] == task_id and e['sha'] == sha), None)
    if existing:
        return existing
    details = git(paths.root, 'show', '-s', '--format=%an%n%aI%n%s', sha).splitlines()
    entry = {'task': task_id, 'requirements': tasks[task_id].get('implements', []), 'sha': sha,
             'author': details[0], 'date': details[1], 'subject': '\n'.join(details[2:]),
             'files': git(paths.root, 'diff-tree', '--root', '--no-commit-id', '--name-only', '-r', sha).splitlines(),
             'summary': summary, 'linked_at': utcnow(), 'attribution': 'explicit user/controller link; commit existence and ancestry verified, semantic relevance requires review'}
    entries.append(entry)
    dump_yaml(file, entries)
    from .journal import Journal
    Journal(paths.event_log).append('commit_linked', task=task_id, sha=sha, summary=summary)
    return entry


def render_history(paths: SDDPaths) -> None:
    from .journal import Journal
    events = Journal(paths.event_log).read()
    tasks = {t['id']: t for f in load_yaml(paths.features_file, []) or [] for t in f.get('tasks', [])}
    links = load_yaml(paths.state / 'commit-links.yaml', []) or []
    lines = ['# Project Changelog', '',
             'Human-readable development history, not release certification. HEAD snapshots are context only; only explicit links attribute commits to tasks. Unlinked work remains uncommitted/unattributed.', '',
             '[Design documentation](docs/README.md) · [Traceability](docs/TRACEABILITY.md)', '']
    relevant = {'project_initialized', 'task_verified', 'implementation_repair_created', 'change_applied', 'commit_linked', 'run_completed', 'run_paused', 'task_failed', 'task_blocked_after_review', 'run_failed', 'documentation_updated'}
    for event in reversed(events):
        if event.get('event') not in relevant:
            continue
        task_id = event.get('task', '')
        task = tasks.get(task_id, {})
        title = event.get('task_title') or task.get('title') or event.get('change_id') or ''
        lines += [f'## {event.get("timestamp", "unknown date")} — {event["event"].replace("_", " ")} {task_id}', '', str(title), '']
        reqs = event.get('requirements', task.get('implements', []))
        if reqs:
            lines += ['Requirements: ' + (', '.join(reqs) if isinstance(reqs, list) else str(reqs)), '']
        if event.get('task_description'):
            lines += ['Task scope: ' + event['task_description'], '']
        if event.get('spec_revision'):
            lines += [f'Specification: [snapshot](history/specs/{event["spec_revision"]}.json) · [transition diff](history/specs/{event["spec_transition"]}.diff)', '']
        if event.get('evidence'):
            lines += ['Verification evidence: ' + str(event['evidence']), '']
        for field in ['summary', 'notes', 'invalidated_tasks', 'reason', 'error']:
            if event.get(field):
                lines += [f'{field.replace("_", " ").title()}: {event[field]}', '']
        if event.get('change_id'):
            cr = load_yaml(paths.changes / f'{event["change_id"]}.yaml', {}) or {}
            lines += [f'Change: [{event["change_id"]}](changes/{event["change_id"]}.yaml)', '',
                      f'Description: {cr.get("description", "Not recorded")}', '',
                      f'Classification: {cr.get("classification", "unknown")}; approved: {cr.get("approved", False)}', '']
        if task_id:
            matches = [e for e in links if e['task'] == task_id]
            for entry in matches:
                lines += [f'Commit: `{entry["sha"]}` — {entry["subject"]}', '',
                          f'{entry["author"]} · {entry["date"]}', '', entry['summary'], '',
                          'Changed files: ' + ', '.join(f'`{p}`' for p in entry['files']), '']
            if not matches:
                lines += ['Commit: not linked (work may be uncommitted or attribution pending).', '']
        context = event.get('git', {})
        if context:
            lines += [f'Observed HEAD (not attribution): `{context.get("head") or "none"}`; branch: {context.get("branch") or "none"}', '']
    lines += ['## Specification revisions', '', 'Full snapshots and before/after diffs preserve the specification history.', '']
    for revision in load_yaml(paths.state / 'spec-history.yaml', []) or []:
        ident = revision['revision']
        lines += [f'- {revision["timestamp"]}: [snapshot {ident[:12]}](history/specs/{ident}.json) · [exact diff](history/specs/{revision["transition"]}.diff)']
    lines += ['', '## Commit links', '']
    for entry in links:
        lines += [f'- {entry["task"]}: `{entry["sha"]}` — {entry["summary"]}']
    atomic_write(paths.sdd / 'CHANGELOG.md', '\n'.join(lines) + '\n')


def discover_task_commits(paths: SDDPaths, task_id: str, before: str | None) -> list[str]:
    """Import explicit SDD-Task trailers from commits created during a bounded task."""
    if not before or not git(paths.root, 'rev-parse', '--verify', before + '^{commit}'):
        return []  # Unborn/imported histories require explicit link-commit.
    result = subprocess.run(['git','merge-base','--is-ancestor',before,'HEAD'], cwd=paths.root, capture_output=True)
    if result.returncode:
        return []
    shas = git(paths.root, 'rev-list', '--reverse', before + '..HEAD').splitlines()
    found = []
    for sha in shas:
        message = git(paths.root, 'show', '-s', '--format=%B', sha)
        if re.search(r'^SDD-Task:\s*' + re.escape(task_id) + r'\s*$', message, re.MULTILINE):
            link_commit(paths, task_id, sha, 'Automatically linked from explicit SDD-Task commit trailer: ' + message.splitlines()[0])
            found.append(sha)
    return found

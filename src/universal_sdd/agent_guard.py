"""Detect controller and Git mutations; this is not an OS sandbox."""
import fnmatch
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

def _source_names(root: Path):
    listing = subprocess.run(
        ['git', 'ls-files', '-co', '--exclude-standard', '-z'],
        cwd=root,
        capture_output=True,
    )
    if listing.returncode:
        raise RuntimeError('Git repository required for source-bound evidence')
    names = []
    for name in sorted(set(listing.stdout.decode().split('\0')) - {''}):
        if name == '.sdd-controller.lock' or (name.startswith('.sdd/') and not name.startswith('.sdd/ci/')):
            continue
        names.append(name)
    return names


def _read_source(root: Path, name: str):
    path = root / name
    if path.is_symlink():
        return b'\x00SYMLINK:' + os.readlink(path).encode()
    if path.is_file():
        return path.read_bytes()
    return None


def snapshot_source(root: Path):
    return {name: _read_source(root, name) for name in _source_names(root)}


def restore_source(root: Path, snapshot: dict) -> list[str]:
    changed = []
    for name, content in snapshot.items():
        path = root / name
        current = _read_source(root, name)
        if current == content:
            continue
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
        if content is None:
            changed.append(name)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if content.startswith(b'\x00SYMLINK:'):
            path.symlink_to(content[len(b'\x00SYMLINK:'):].decode())
        else:
            path.write_bytes(content)
        changed.append(name)
    for name in _source_names(root):
        if name in snapshot:
            continue
        path = root / name
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
        changed.append(name)
    return changed


def files(root,patterns):
    result={}
    # NOTE: `.cursor/` as a whole is NOT protected. SDD scaffolds only
    # `.cursor/agents/` and `.cursor/rules/vega-sdd.mdc`; the Cursor CLI may
    # write transcripts/caches elsewhere under `.cursor/` during writable runs.
    # Guarding the entire directory turns normal CLI activity into
    # "Agent modified protected controller files" run failures.
    def protected(rel):return rel in {'AGENTS.md','CLAUDE.md','.sdd','.agents','.codex','.claude','.cursor/agents','.cursor/rules'} or rel.startswith(('.sdd/','.agents/','.codex/','.claude/','.cursor/agents/','.cursor/rules/')) or any(fnmatch.fnmatch(rel,p) for p in patterns)
    for folder,dirs,names in os.walk(root):
        dirs[:]=[d for d in dirs if d not in {'.git','node_modules','.venv','__pycache__','dist','build'}]
        for name in names+[d for d in dirs if (Path(folder)/d).is_symlink()]:
            path=Path(folder)/name;rel=path.relative_to(root).as_posix()
            if rel.startswith('.sdd/runtime/'):continue
            if protected(rel):result[rel]=(b'\x00SYMLINK:'+os.readlink(path).encode()) if path.is_symlink() else path.read_bytes()
    return result

def workspace_snapshot(root: Path) -> dict:
    """Walk the working tree. Git ls-files would hide gitignored and some untracked files."""
    result = {}
    skip = {'.git', 'node_modules', '.venv', '__pycache__', 'dist', 'build'}
    for folder, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in skip]
        for name in names:
            path = Path(folder) / name
            rel = path.relative_to(root).as_posix()
            if rel.startswith('.sdd/') and not rel.startswith('.sdd/ci/'):
                continue
            if rel in {'.sdd-controller.lock', '.fixture-prompt.txt'}:
                continue
            result[rel] = _read_source(root, rel)
    return result


def changed_since(root: Path, before: dict) -> list[str]:
    after = workspace_snapshot(root)
    names = set(before) | set(after)
    return sorted(name for name in names if before.get(name) != after.get(name))


def snapshot_hashes(snapshot: dict) -> dict[str, str]:
    return {name: hashlib.sha256(content or b"").hexdigest() for name, content in snapshot.items()}


def persist_task_baseline(paths, task_id: str, snapshot: dict) -> None:
    folder = paths.runtime / "task-baselines"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{task_id}.json").write_text(
        json.dumps(snapshot_hashes(snapshot), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def load_task_baseline(paths, task_id: str) -> dict[str, str] | None:
    path = paths.runtime / "task-baselines" / f"{task_id}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def clear_task_baseline(paths, task_id: str) -> None:
    (paths.runtime / "task-baselines" / f"{task_id}.json").unlink(missing_ok=True)


def changed_since_hashes(root: Path, hashes: dict[str, str]) -> list[str]:
    after = snapshot_hashes(workspace_snapshot(root))
    return sorted(name for name in set(hashes) | set(after) if hashes.get(name) != after.get(name))


def git_index_path(root: Path) -> Path | None:
    completed = subprocess.run(
        ["git", "rev-parse", "--git-path", "index"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        return None
    raw = (completed.stdout or "").strip()
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_absolute() else (root / path).resolve()


def snapshot_git_index(root: Path) -> bytes | None:
    path = git_index_path(root)
    if path is None or not path.is_file():
        return None
    return path.read_bytes()


def restore_git_state(root: Path, original: tuple) -> None:
    """Restore HEAD and the captured index file. Does not rewrite the working tree."""
    head, ref, index_bytes = original
    head_text = head.decode().strip() if isinstance(head, (bytes, bytearray)) else str(head).strip()
    ref_text = ref.decode().strip() if isinstance(ref, (bytes, bytearray)) else str(ref).strip()
    if head_text:
        subprocess.run(["git", "update-ref", "HEAD", head_text], cwd=root, capture_output=True)
    if ref_text:
        subprocess.run(["git", "symbolic-ref", "HEAD", ref_text], cwd=root, capture_output=True)
    path = git_index_path(root)
    if path is None:
        return
    lock = path.with_name(path.name + ".lock")
    lock.unlink(missing_ok=True)
    if index_bytes is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(index_bytes)


def restore_workspace(root: Path, snapshot: dict) -> list[str]:
    after = workspace_snapshot(root)
    changed: list[str] = []
    for name, content in snapshot.items():
        path = root / name
        if after.get(name) == content:
            continue
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
        if content is None:
            changed.append(name)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes) and content.startswith(b"\x00SYMLINK:"):
            path.symlink_to(content[len(b"\x00SYMLINK:"):].decode())
        elif isinstance(content, bytes):
            path.write_bytes(content)
        changed.append(name)
    for name in after:
        if name in snapshot:
            continue
        path = root / name
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
        changed.append(name)
    return changed


def guarded_run(adapter,prompt,root:Path,patterns=(),**kwargs):
    before=files(root,patterns)
    if any(v.startswith(b'\x00SYMLINK:') for v in before.values()):raise RuntimeError('Protected controller symlink')
    def git_state():
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True).stdout
        ref = subprocess.run(["git", "symbolic-ref", "-q", "HEAD"], cwd=root, capture_output=True).stdout
        return (head, ref, snapshot_git_index(root))
    original=git_state();source=None
    if not kwargs.get('writable',False):
        source=workspace_snapshot(root)
    try:return adapter.run(prompt,**kwargs)
    finally:
        after=files(root,patterns)
        changed=[p for p in before.keys()|after.keys() if before.get(p)!=after.get(p)]
        journal='.sdd/journal/events.jsonl'
        if journal in changed and after.get(journal,b'').startswith(before.get(journal,b'')) and (root/'.sdd/runtime/pause-requested').exists():
            try:
                new=after[journal][len(before.get(journal,b'')):].splitlines()
                if new and all(json.loads(x).get('event')=='pause_requested' for x in new):changed.remove(journal)
            except (ValueError,TypeError):pass
        violations=[]
        if changed:
            def regenerable(rel):
                return rel in {'.sdd/CHANGELOG.md','.sdd/STATUS.md','.sdd/roadmap.md'} or rel.startswith('.sdd/docs/')
            for name in sorted(changed,key=lambda p:len(Path(p).parts)):
                path=root/name
                if path.is_symlink():path.unlink()
            for name in sorted(changed):
                path=root/name
                if name in before:
                    if path.is_dir():shutil.rmtree(path)
                    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(before[name])
                elif path.exists():path.unlink()
            material=[p for p in changed if not regenerable(p)]
            if material:
                violations.append('Agent modified protected controller files; restored: '+', '.join(material))
        if source is not None:
            restore_workspace(root, source)
        if git_state()!=original:
            restore_git_state(root, original)
            violations.append('Agent changed Git HEAD, branch or index; inspect working tree')
        if violations:
            raise RuntimeError('; '.join(violations))

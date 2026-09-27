"""Detect controller and Git mutations; this is not an OS sandbox."""
import fnmatch
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

def guarded_run(adapter,prompt,root:Path,patterns=(),**kwargs):
    before=files(root,patterns)
    if any(v.startswith(b'\x00SYMLINK:') for v in before.values()):raise RuntimeError('Protected controller symlink')
    def git_state():return tuple(subprocess.run(['git',*args],cwd=root,capture_output=True).stdout for args in [('rev-parse','HEAD'),('symbolic-ref','-q','HEAD'),('diff','--cached','--raw')])
    original=git_state();source=None
    if not kwargs.get('writable',False) and (root/'.sdd/workspace.yaml').exists():
        source=snapshot_source(root)
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
                raise RuntimeError('Agent modified protected controller files; restored: '+', '.join(material))
        if source is not None:
            restore_source(root, source)
        if git_state()!=original:raise RuntimeError('Agent changed Git HEAD, branch or index; inspect working tree')

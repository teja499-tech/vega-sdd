"""Detect controller and Git mutations; this is not an OS sandbox."""
import fnmatch
import json
import os
import shutil
import subprocess
from pathlib import Path

def files(root,patterns):
    result={}
    def protected(rel):return rel in {'AGENTS.md','CLAUDE.md','.sdd','.agents','.codex','.claude','.cursor'} or rel.startswith(('.sdd/','.agents/','.codex/','.claude/','.cursor/')) or any(fnmatch.fnmatch(rel,p) for p in patterns)
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
        from .workspace import fingerprint
        source=fingerprint(root)
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
            for name in sorted(changed,key=lambda p:len(Path(p).parts)):
                path=root/name
                if path.is_symlink():path.unlink()
            for name in sorted(changed):
                path=root/name
                if name in before:
                    if path.is_dir():shutil.rmtree(path)
                    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(before[name])
                elif path.exists():path.unlink()
            raise RuntimeError('Agent modified protected controller files; restored: '+', '.join(changed))
        if git_state()!=original:raise RuntimeError('Agent changed Git HEAD, branch or index; inspect working tree')
        if source is not None and fingerprint(root)!=source:raise RuntimeError('Read-only agent changed source; inspect changes')

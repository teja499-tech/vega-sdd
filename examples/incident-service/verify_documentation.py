"""Extend a completed lifecycle with real Git attribution and brownfield adoption."""
import json
import shutil
import subprocess
import sys
from pathlib import Path
import yaml

BASE=Path(__file__).resolve().parent
root=Path(sys.argv[1]).resolve()
brown=Path(sys.argv[2]).resolve()
steps=[]
def cli(target,label,args,expected=0):
    result=subprocess.run([sys.executable,str(BASE/'fixture_cli.py'),*args,'--root',str(target)],text=True,capture_output=True,timeout=90)
    (root/'evidence'/f'enterprise-{label}.log').write_text(result.stdout+'\n'+result.stderr)
    steps.append({'step':label,'exit_code':result.returncode,'expected':expected})
    assert result.returncode==expected,(label,result.stdout,result.stderr)
    return result

assert (root/'.sdd/docs/HLD.md').exists()
assert '120 characters' not in (root/'.sdd/docs/API_DESIGN.md').read_text()
assert '80 characters' in (root/'.sdd/docs/API_DESIGN.md').read_text()
cli(root,'document-check',['docs','check'],2) # Real operational unknowns must remain visible.
cli(root,'document-refresh',['docs','refresh'])
def git(*args):
    return subprocess.check_output(['git',*args],cwd=root,text=True).strip()
git('init','-q');git('config','user.name','SDD benchmark fixture');git('config','user.email','fixture@example.test')
git('add','service.py','store.py','OPERATIONS.md');git('commit','-qm','Record tested incident reference implementation')
sha=git('rev-parse','HEAD')
cli(root,'commit-link',['link-commit','TASK-F002-001','--commit',sha,'--summary','Record the tested 80-character title limit and authenticated incident API reference implementation.'])
cli(root,'human-changelog',['changelog'])
assert sha in (root/'.sdd/CHANGELOG.md').read_text()
assert 'REQ-002' in (root/'.sdd/CHANGELOG.md').read_text()
assert 'exact diff' in (root/'.sdd/CHANGELOG.md').read_text()

assert not brown.exists()
brown.mkdir()
for name in ['service.py','store.py','OPERATIONS.md','PRD.md']:
    shutil.copyfile(root/name,brown/name)
(brown/'README.md').write_text('Existing enterprise application README\n')
(brown/'SECURITY.md').write_text('Existing private security policy\n')
(brown/'CHANGELOG.md').write_text('Existing release history\n')
protected={p.name:p.read_bytes() for p in brown.iterdir() if p.is_file()}
cli(brown,'brownfield-init',['init','--agent','codex','--project-kind','existing','--yes'])
for name,content in protected.items():
    assert (brown/name).read_bytes()==content,name
assert yaml.safe_load((brown/'.sdd/config.yaml').read_text())['project_kind']=='existing'
assert 'Observed current behavior' in (brown/'.sdd/docs/EXISTING_SYSTEM.md').read_text()
cli(brown,'brownfield-doc-check',['docs','check'],2)
summary={'mode':'Scripted agent fixture; real Git commits and repository-preservation assertions','steps':steps,'commit_sha':sha,'protected_brownfield_files':list(protected),'operational_gaps_correctly_reported':True,'live_provider_certification':False}
(root/'evidence/enterprise-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))

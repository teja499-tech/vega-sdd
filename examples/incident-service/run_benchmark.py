"""Replay real CLI subprocesses with scripted agent responses and real application tests."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
import yaml
BASE=Path(__file__).resolve().parent
ROOT=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else BASE/'run'
if ROOT.exists():raise SystemExit('Choose a fresh destination to preserve prior evidence')
ROOT.mkdir(parents=True);shutil.copyfile(BASE/'PRD.md',ROOT/'PRD.md')
logs=ROOT/'evidence';logs.mkdir();steps=[]
(ROOT/'.gitignore').write_text('.sdd/\n.sdd-controller.lock\n.fixture-prompt.txt\nfixture-*\nevidence/\n__pycache__/\n*.pyc\n')
def git(*args):subprocess.run(['git',*args],cwd=ROOT,check=True,capture_output=True)
git('init','-q','-b','main');git('config','user.name','SDD fixture');git('config','user.email','fixture@example.test')

def cli(label,args,input=None,expected=0):
    r=subprocess.run([sys.executable,str(BASE/'fixture_cli.py'),*args,'--root',str(ROOT)],input=input,text=True,capture_output=True,timeout=120)
    (logs/f'{len(steps):02}-{label}.log').write_text(r.stdout+'\n'+r.stderr)
    steps.append({'step':label,'exit_code':r.returncode,'expected':expected})
    assert r.returncode==expected,(label,r.stdout,r.stderr)
    return r
cli('interactive-init',['init','--agent','codex','--project-kind','new'],input='120\na\nWhy SQLite?\n1\nSingle host approved\n')
config=ROOT/'.sdd/config.yaml';data=yaml.safe_load(config.read_text());data['test_command']=f'{sys.executable} -m unittest discover -s acceptance -v';config.write_text(yaml.safe_dump(data))
policy=ROOT/'workspace-policy.yaml'
policy.write_text(yaml.safe_dump({'components':[{'id':'incidents','kind':'service','checks':{'test':{'argv':[sys.executable,'-m','unittest','discover','-s','acceptance','-v']},'contract':{'run_at':'release','argv':[sys.executable,'-m','unittest','discover','-s','acceptance','-p','test_api.py','-v']}}}]}))
cli('configure-policy',['project','configure','--file',str(policy)])
git('add','.');git('commit','-qm','Fixture baseline')
cli('execution-branch',['repo','branch','benchmark'])
cli('first-task',['start','--max-tasks','1'])
assert yaml.safe_load((ROOT/'.sdd/state/project.yaml').read_text())['run_status']=='paused'
cli('status-while-paused',['status'])
# New CLI process, no prior agent session; auth defect fails tests and gets repaired.
cli('resume-auto-repair',['resume'])
assert yaml.safe_load((ROOT/'.sdd/state/project.yaml').read_text())['run_status']=='completed'
for command in ['verify','roadmap','requirements','architecture','doctor','log']:
    cli(command,[command])
cli('feature',['feature','F002'])
cli('intervene',['intervene'],input='Why SQLite?\nexit\n')
before=(ROOT/'.sdd/state/features.yaml').read_bytes()
cli('preview-change',['change','Set title limit to 80'])
assert (ROOT/'.sdd/state/features.yaml').read_bytes()==before
change_files=sorted((ROOT/'.sdd/changes').glob('CR-*.yaml'),key=lambda p:p.stat().st_mtime_ns)
preview_id=yaml.safe_load(change_files[-1].read_text())['id']
cli('approve-change',['change','--approve-id',preview_id])
fs=yaml.safe_load((ROOT/'.sdd/state/features.yaml').read_text())
assert fs[0]['tasks'][0]['status']=='verified'
assert fs[1]['tasks'][0]['status']=='invalidated'
assert fs[2]['tasks'][0]['status']=='invalidated'
cli('resume-after-change',['resume'])
cli('final-status',['status'])
cli('project-check',['project','check'])
checks=subprocess.run([sys.executable,'-m','unittest','discover','-s','acceptance','-v'],cwd=ROOT,text=True,capture_output=True,timeout=120)
(logs/'application-tests.log').write_text(checks.stdout+'\n'+checks.stderr)
assert checks.returncode==0,checks.stderr
events=[json.loads(line) for line in (ROOT/'.sdd/journal/events.jsonl').read_text().splitlines()]
assert any(e['event']=='repair_started' for e in events)
assert any(e['event']=='deterministic_check' and e['status']=='fail' for e in events)
summary={'agent_mode':'SCRIPTED PROCESS FIXTURE — no live provider or autonomous generation certification','steps':steps,'application_tests_exit':checks.returncode,'recorded_events':len(events),'repair_events':sum(e['event']=='repair_started' for e in events),'final_state':yaml.safe_load((ROOT/'.sdd/state/project.yaml').read_text()),'production_release_certified':False}
(logs/'summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))

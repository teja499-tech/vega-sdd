import subprocess,sys
from pathlib import Path
from types import SimpleNamespace
import pytest
from typer.testing import CliRunner
from universal_sdd.workspace import PROFILES,Workspace,Component,configure,load_workspace,ordered,gaps,run_checks,quality_current,policy_path
from universal_sdd.delivery import git,guard,create_branch,merge_gaps
from universal_sdd.pipelines import export
from universal_sdd.releases import build,deploy,reconcile
from universal_sdd.recovery import checkpoint,restore
from universal_sdd.agent_guard import guarded_run
from universal_sdd.cli import app

@pytest.fixture
def repo(tmp_path):
    root=tmp_path/'repo';root.mkdir()
    git(root,'init','-q','-b','main');git(root,'config','user.name','Test');git(root,'config','user.email','test@example.test')
    (root/'.gitignore').write_text('out/\n.sdd/\n__pycache__/\n')
    (root/'app.py').write_text('VALUE=1\n')
    git(root,'add','.');git(root,'commit','-qm','baseline')
    configure(root,{'components':[{'id':'app','kind':'custom','checks':{'test':{'argv':[sys.executable,'-c','import app;assert app.VALUE==1']}}}]})
    return root

@pytest.mark.parametrize('kind',list(PROFILES))
def test_profile_contract(repo,kind):
    cfg=configure(repo,{'components':[{'id':'app','kind':kind,'checks':{n:{'argv':[sys.executable,'-c','pass']} for n in PROFILES[kind]}}]})
    assert not gaps(cfg) and run_checks(repo)['passed']

def test_evidence_and_dependencies(repo):
    assert run_checks(repo)['passed'] and quality_current(repo)
    (repo/'app.py').write_text('VALUE=2');assert not quality_current(repo)
    assert [x.id for x in ordered([Component(id='consumer',kind='custom',depends_on=['producer']),Component(id='producer',kind='custom')])]==['producer','consumer']
    with pytest.raises(ValueError):Workspace(components=[Component(id='a',kind='custom',depends_on=['a'])])
    policy_path(repo).write_text(policy_path(repo).read_text()+'\n# changed')
    with pytest.raises(RuntimeError):load_workspace(repo)

def test_release_only_check_not_task_certification(repo):
    cfg=load_workspace(repo).model_dump()
    cfg['components'][0]['checks']['integration']={'argv':[sys.executable,'-c','raise SystemExit(1)'],'run_at':'release'}
    configure(repo,cfg)
    assert run_checks(repo,phase='task')['passed'] and not quality_current(repo)
    assert not run_checks(repo)['passed']

def test_protected_branch_and_nonoverwrite_ci(repo,tmp_path):
    with pytest.raises(RuntimeError):guard(repo)
    create_branch(repo,'feature',tmp_path/'work')
    assert policy_path(tmp_path/'work').exists()
    paths=export(repo,'github');assert '.sdd/ci/verify.py' in paths
    assert subprocess.run([sys.executable,str(repo/'.sdd/ci/verify.py')],cwd=repo,capture_output=True).returncode==0
    p=repo/'.github/workflows/sdd-checks.yml';p.write_text('user workflow')
    with pytest.raises(RuntimeError,match='preserved'):export(repo,'github')
    assert p.read_text()=='user workflow'

@pytest.mark.parametrize('provider',['gitlab','azure'])
def test_ci_fragments(repo,provider):assert '.sdd/ci/verify.py' in export(repo,provider)

def release_config(repo):
    cfg=load_workspace(repo).model_dump()
    cfg['components'][0].update(build={'argv':[sys.executable,'-c','from pathlib import Path;p=Path("out/a");p.parent.mkdir(exist_ok=True);p.write_text("package")']},artifact='out/a')
    cmd={'argv':[sys.executable,'-c','import os;from pathlib import Path;Path(".sdd/deployed").write_text(os.environ["SDD_RELEASE_VERSION"])']}
    smoke={'argv':[sys.executable,'-c','import os;from pathlib import Path;assert Path(".sdd/deployed").read_text()==os.environ["SDD_RELEASE_VERSION"]']}
    cfg['environments']={'stage':{'deploy':cmd,'smoke':smoke,'requires_approval':False},'prod':{'deploy':cmd,'smoke':smoke,'promote_from':'stage'}}
    configure(repo,cfg);run_checks(repo);return cfg

def test_immutable_release_promote_and_digest(repo):
    release_config(repo);record=build(repo,'1')
    with pytest.raises(RuntimeError,match='approval'):deploy(repo,'1','prod')
    with pytest.raises(RuntimeError,match='Promote'):deploy(repo,'1','prod',approve=True)
    assert deploy(repo,'1','stage')['status']=='succeeded'
    result=deploy(repo,'1','prod',approve=True)
    assert result['status']=='succeeded' and deploy(repo,'1','prod')['operation']==result['operation']
    with pytest.raises(RuntimeError,match='exists'):build(repo,'1')
    (repo/record['artifacts'][0]['path']).write_text('tampered')
    with pytest.raises(RuntimeError,match='digest'):deploy(repo,'1','stage')

def test_unknown_deployment_requires_reconcile(repo):
    cfg=release_config(repo);cfg['environments']['stage']['smoke']={'argv':[sys.executable,'-c','raise SystemExit(1)']}
    configure(repo,cfg);run_checks(repo);build(repo,'1')
    assert deploy(repo,'1','stage')['status']=='unknown'
    with pytest.raises(RuntimeError):deploy(repo,'1','stage')
    assert reconcile(repo,'stage','failed','Observed failed target after inspection')['status']=='failed'

@pytest.mark.parametrize('field,value',[('head','old'),('base','wrong'),('review',''),('draft',True),('mergeable',False),('checks',[]),('state','closed')])
def test_pr_fail_closed(repo,field,value):
    head=git(repo,'rev-parse','HEAD');data={'state':'open','draft':False,'head':head,'base':'main','review':'APPROVED','mergeable':True,'checks':[{'name':'SDD checks','status':'SUCCESS'}]};data[field]=value
    assert merge_gaps(data,load_workspace(repo).repo,head)

def test_guard_restore_and_checkpoint(repo):
    p=policy_path(repo);before=p.read_bytes()
    def change(*a,**k):p.write_text('modified');(repo/'app.py').write_text('user work')
    with pytest.raises(RuntimeError,match='restored'):guarded_run(SimpleNamespace(run=change),'task',repo,writable=True)
    assert p.read_bytes()==before and (repo/'app.py').read_text()=='user work'
    saved=checkpoint(repo);restore(repo,saved['id'])
    assert (repo/'app.py').read_text()=='user work' and not quality_current(repo)

def test_cli_check(repo):assert CliRunner().invoke(app,['project','check','--root',str(repo)]).exit_code==0

def test_command_provider_push_and_merge(repo,tmp_path):
    from universal_sdd.delivery import Provider
    remote=tmp_path/'remote.git';git(tmp_path,'init','--bare',str(remote));git(repo,'remote','add','origin',str(remote));git(repo,'push','origin','main')
    hook=repo/'.sdd/provider.py'
    hook.write_text('''import json,os,sys
from pathlib import Path
request=json.loads(os.environ['SDD_REQUEST']);path=Path('.sdd/provider-pr.json');action=sys.argv[1]
print('diagnostics',file=sys.stderr)
if action=='open':
 data={'id':'1','state':'open','draft':False,'head':request['head'],'base':request['base'],'review':'APPROVED','mergeable':True,'checks':[{'name':'SDD checks','status':'SUCCESS'}]};path.write_text(json.dumps(data))
else:
 data=json.loads(path.read_text())
 if action=='merge':
  assert request['expected_head']==data['head'];data['state']='merged';path.write_text(json.dumps(data))
print(json.dumps(data))
''')
    cfg=load_workspace(repo).model_dump();cfg['repo'].update(provider='command',allow_push=True,allow_merge=True,provider_commands={name:{'argv':[sys.executable,str(hook),name]} for name in ['open','view','merge']});configure(repo,cfg)
    create_branch(repo,'provider');run_checks(repo)
    provider=Provider(repo);record=provider.open('Title','Body')
    assert record['head']==git(repo,'rev-parse','HEAD')
    assert provider.merge(record['id'])['state']=='merged'


def test_resumable_local_lifecycle(repo):
    from universal_sdd.lifecycle import advance
    from universal_sdd.storage import SDDPaths,load_project_state,save_project_state
    from universal_sdd.models import RunStatus
    release_config(repo)
    # A completed approved task run should proceed without another agent invocation.
    state=load_project_state(SDDPaths(repo));state.run_status=RunStatus.completed;save_project_state(SDDPaths(repo),state)
    result=advance(repo,'1','stage')
    assert result['stage']=='delivered'
    assert git(repo,'branch','--show-current').startswith('sdd/')
    assert advance(repo,'1','stage')['deployment']['operation']==result['deployment']['operation']

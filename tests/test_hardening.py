import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner
from universal_sdd.cli import app
from universal_sdd.models import *
from universal_sdd.storage import *
from universal_sdd.status import metrics, load_features
from universal_sdd.orchestrator import run_development, apply_change
from universal_sdd.traceability import validate_traceability

@pytest.fixture
def initialized(demo_repo):
    r = CliRunner().invoke(app, ['init','--root',str(demo_repo),'--agent','mock','--yes'])
    assert r.exit_code == 0, r.output
    return SDDPaths(demo_repo)

def test_empty_project_cannot_verify(tmp_path):
    assert not validate_traceability(SDDPaths(tmp_path)).ok

@pytest.mark.parametrize('kind', ['feature_cycle','task_cycle','duplicate_requirement','duplicate_task','missing_ac'])
def test_invalid_graph(initialized, kind):
    p = initialized
    fs = load_features(p)
    rs = load_yaml(p.requirements_file)
    if kind == 'feature_cycle': fs[0].depends_on = [fs[0].id]
    if kind == 'task_cycle': fs[0].tasks[0].depends_on = [fs[0].tasks[0].id]
    if kind == 'duplicate_task': fs[0].tasks.append(fs[0].tasks[0].model_copy())
    if kind == 'duplicate_requirement': rs.append(rs[0].copy())
    if kind == 'missing_ac': rs[0]['acceptance_criteria'] = []
    dump_yaml(p.features_file, fs)
    dump_yaml(p.requirements_file, rs)
    assert not validate_traceability(p).ok

def test_requirement_needs_all_tasks(initialized):
    fs = load_features(initialized)
    fs[0].tasks[0].status = ItemStatus.verified
    fs[0].tasks.append(fs[0].tasks[0].model_copy(update={'id':'TASK-F001-002','status':ItemStatus.pending}))
    dump_yaml(initialized.features_file, fs)
    m = metrics(initialized)
    assert m.requirements_verified == 0
    assert m.verification_pct == 0

class Scripted:
    def __init__(self, root, reviews=None, repair=None, fail=False):
        self.root = root
        self.calls = []
        self.reviews = iter(reviews or ['pass'])
        self.repair = repair
        self.fail = fail
    def capabilities(self): return AgentCapabilities(installed=True)
    def interrupt(self): return True
    def run(self, prompt, **kwargs):
        self.calls.append(prompt)
        if 'TASK_REVIEW_JSON' in prompt:
            status = next(self.reviews, 'pass')
            if status == 'malformed': return AgentResult(success=True,text='garbage')
            return AgentResult(success=True,text=json.dumps({'status':status,'findings':[{'summary':'fix'}] if status == 'fail' else [],'summary':status}))
        if 'Findings:' in prompt and self.repair: self.repair()
        return AgentResult(success=not self.fail, text='done', exit_code=1 if self.fail else 0)

def set_check(p, command):
    c = load_config(p); c.test_command=command; save_config(p,c)

def test_implemented_task_is_not_reimplemented(initialized):
    p = initialized
    fs = load_features(p); fs[0].tasks[0].status = ItemStatus.implemented; dump_yaml(p.features_file,fs)
    set_check(p, f'{sys.executable} -c "pass"')
    a = Scripted(p.root)
    with patch('universal_sdd.orchestrator.get_adapter', return_value=a): run_development(p.root)
    assert not any('TASK_IMPLEMENTATION' in c for c in a.calls)

def test_test_failure_auto_repairs(initialized):
    p = initialized
    (p.root/'check.py').write_text('raise SystemExit(1)')
    set_check(p, f'{sys.executable} check.py')
    a = Scripted(p.root, repair=lambda:(p.root/'check.py').write_text('pass'))
    with patch('universal_sdd.orchestrator.get_adapter',return_value=a): state=run_development(p.root)
    assert state.run_status == RunStatus.completed
    assert any('Findings:' in c for c in a.calls)

def test_review_repair_must_rerun_tests(initialized):
    p=initialized
    (p.root/'check.py').write_text('pass')
    set_check(p, f'{sys.executable} check.py')
    a=Scripted(p.root,reviews=['fail','pass'],repair=lambda:(p.root/'check.py').write_text('raise SystemExit(1)'))
    with patch('universal_sdd.orchestrator.get_adapter',return_value=a): state=run_development(p.root)
    assert state.run_status == RunStatus.blocked
    assert load_features(p)[0].tasks[0].status != ItemStatus.verified

def test_malformed_review_records_blocked_state(initialized):
    p=initialized; set_check(p,f'{sys.executable} -c "pass"')
    a=Scripted(p.root,reviews=['malformed']*10)
    with patch('universal_sdd.orchestrator.get_adapter',return_value=a): state=run_development(p.root)
    assert state.run_status == RunStatus.blocked

def test_real_adapter_cannot_verify_without_test_command(initialized):
    p=initialized; c=load_config(p); c.primary_agent=AgentName.codex; save_config(p,c)
    a=Scripted(p.root)
    with patch('universal_sdd.orchestrator.get_adapter',return_value=a):
        with pytest.raises(RuntimeError,match='test_command'): run_development(p.root)
    assert not a.calls

def test_failed_run_returns_nonzero(initialized):
    p=initialized
    a=Scripted(p.root,fail=True)
    with patch('universal_sdd.orchestrator.get_adapter',return_value=a):
        r=CliRunner().invoke(app,['start','--root',str(p.root)])
    assert r.exit_code != 0

def test_force_missing_prd_keeps_state(initialized):
    p=initialized; before=p.config_file.read_bytes()
    r=CliRunner().invoke(app,['init','--root',str(p.root),'--agent','mock','--force','--prd','missing.md','--yes'])
    assert r.exit_code != 0
    assert p.config_file.read_bytes() == before

def test_unapproved_change_cannot_mutate(initialized):
    before=initialized.features_file.read_bytes()
    with pytest.raises(RuntimeError,match='approval'):
        apply_change(initialized.root,ChangeRequest(id='CR-1',description='new',classification='requirement_change'))
    assert initialized.features_file.read_bytes()==before

def test_change_is_idempotent(initialized):
    cr=ChangeRequest(id='CR-1',description='repair',classification='implementation_defect',affected_features=['F001'],affected_requirements=['REQ-001'])
    apply_change(initialized.root,cr)
    apply_change(initialized.root,cr)
    assert len(load_features(initialized)[0].tasks)==2

def test_single_writer_lease(initialized):
    from universal_sdd.storage import project_lock
    with project_lock(initialized.root):
        with pytest.raises(RuntimeError,match='controller'):
            run_development(initialized.root)

def test_pause_request_survives_task_save(initialized):
    from universal_sdd.orchestrator import request_pause
    p=initialized; fs=load_features(p)
    fs[0].tasks.append(fs[0].tasks[0].model_copy(update={'id':'TASK-F001-002'}))
    dump_yaml(p.features_file,fs)
    a=Scripted(p.root)
    orig=a.run
    def run(prompt,**kwargs):
        if 'TASK_IMPLEMENTATION' in prompt: request_pause(p.root)
        return orig(prompt,**kwargs)
    a.run=run
    with patch('universal_sdd.orchestrator.get_adapter',return_value=a): state=run_development(p.root)
    assert state.run_status == RunStatus.paused
    assert load_features(p)[0].tasks[1].status == ItemStatus.pending

def test_invalid_change_preserves_approved_state(initialized):
    p=initialized; before=p.features_file.read_bytes()
    # Cyclic feature dependency via slice update should fail validation before write.
    a=Scripted(p.root); a.run=lambda *args,**kwargs:AgentResult(success=True,text=json.dumps({
        'feature_updates':[{'id':'F001','depends_on':['F001']}],
        'invalidate_tasks':[],
    }))
    cr=ChangeRequest(id='CR-BAD',description='change',classification='requirement_change',approved=True)
    with patch('universal_sdd.orchestrator.get_adapter',return_value=a):
        with pytest.raises(RuntimeError,match='before mutation'): apply_change(p.root,cr)
    assert p.features_file.read_bytes()==before

def test_affected_task_invalidated_even_if_agent_omits_it(initialized):
    p=initialized; fs=load_features(p);fs[0].tasks[0].status=ItemStatus.verified;dump_yaml(p.features_file,fs)
    a=Scripted(p.root);a.run=lambda *args,**kwargs:AgentResult(success=True,text=json.dumps({
        'requirement_updates':[{'id':'REQ-001','statement':'Updated core requirement statement for the approved change.'}],
        'invalidate_tasks':[],
    }))
    cr=ChangeRequest(id='CR-CHANGE',description='change',classification='requirement_change',affected_requirements=['REQ-001'],approved=True)
    with patch('universal_sdd.orchestrator.get_adapter',return_value=a): apply_change(p.root,cr)
    assert load_features(p)[0].tasks[0].status==ItemStatus.invalidated

def test_classifier_cannot_bypass_approval(initialized):
    from universal_sdd.orchestrator import analyze_change
    a=Scripted(initialized.root)
    a.run=lambda *args,**kwargs:AgentResult(success=True,text=json.dumps({'classification':'architecture_change','requires_approval':False}))
    with patch('universal_sdd.orchestrator.get_adapter',return_value=a): cr=analyze_change(initialized.root,'switch database')
    assert cr.requires_approval

@pytest.mark.parametrize('model,kwargs',[(Feature,{'id':'../../escape','name':'x','summary':''}),(ArchitectureDecision,{'id':'ARCH-1','category':'../../escape','question':'x'})])
def test_agent_output_cannot_traverse_paths(model,kwargs):
    with pytest.raises(ValueError): model(**kwargs)

def test_large_stderr_does_not_deadlock(tmp_path):
    from universal_sdd.adapters.base import AgentAdapter
    import subprocess
    # Outer timeout makes this a bounded regression even if pipe draining breaks.
    script=tmp_path/'exercise.py'
    script.write_text('''import sys
from pathlib import Path
from universal_sdd.adapters.base import AgentAdapter
from universal_sdd.models import AgentCapabilities
class Local(AgentAdapter):
    def capabilities(self): return AgentCapabilities(installed=True)
    def build_command(self,prompt,**kwargs):
        return [sys.executable,'-c',"import sys; sys.stderr.write('x'*200000); print('done')"]
r=Local(Path('.')).run('test')
assert r.success and r.text=='done'
''')
    subprocess.run([sys.executable,str(script)],check=True,timeout=10)

def test_keyboard_interrupt_checkpoints(initialized):
    a=Scripted(initialized.root)
    a.run=lambda *args,**kwargs: (_ for _ in ()).throw(KeyboardInterrupt())
    with patch('universal_sdd.orchestrator.get_adapter',return_value=a): state=run_development(initialized.root)
    assert state.run_status==RunStatus.paused

def test_agent_exception_records_failure(initialized):
    a=Scripted(initialized.root)
    a.run=lambda *args,**kwargs: (_ for _ in ()).throw(RuntimeError('provider disconnected'))
    with patch('universal_sdd.orchestrator.get_adapter',return_value=a):
        with pytest.raises(RuntimeError):run_development(initialized.root)
    assert load_project_state(initialized).run_status==RunStatus.failed

def test_process_crash_releases_controller_lease(initialized):
    import subprocess,time
    p=initialized
    code="from pathlib import Path; import time; from universal_sdd.storage import project_lock;\nwith project_lock(Path('.')):\n print('locked',flush=True); time.sleep(30)"
    proc=subprocess.Popen([sys.executable,'-c',code],cwd=p.root,stdout=subprocess.PIPE,text=True)
    try:
        assert proc.stdout.readline().strip()=='locked'
        with pytest.raises(RuntimeError,match='controller'):run_development(p.root)
        proc.kill();proc.wait(timeout=5)
        assert run_development(p.root).run_status==RunStatus.completed
    finally:
        if proc.poll() is None:proc.kill();proc.wait(timeout=5)

def test_atomic_yaml_write_failure_retains_previous_file(initialized):
    p=initialized.config_file;before=p.read_bytes()
    with patch('universal_sdd.storage.os.replace',side_effect=OSError('disk error')):
        with pytest.raises(OSError):dump_yaml(p,{'broken':True})
    assert p.read_bytes()==before

def test_mixed_dependency_cycle(initialized):
    p=initialized;fs=load_features(p);f1=fs[0]
    f2=f1.model_copy(deep=True);f2.id='F002';f2.depends_on=['F001'];f2.tasks[0].id='TASK-F002-001';f2.tasks[0].feature_id='F002'
    f1.tasks[0].depends_on=['TASK-F002-001'];dump_yaml(p.features_file,[f1,f2])
    assert any('execution' in e for e in validate_traceability(p).errors)

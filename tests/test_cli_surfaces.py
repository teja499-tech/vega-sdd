from pathlib import Path
from unittest.mock import patch
import pytest
from typer.testing import CliRunner
from universal_sdd.cli import app
from universal_sdd.models import RunStatus,AgentResult
from universal_sdd.storage import SDDPaths,load_project_state

@pytest.fixture
def root(demo_repo):
    r=CliRunner().invoke(app,['init','--root',str(demo_repo),'--agent','mock','--yes'])
    assert r.exit_code==0
    return demo_repo

@pytest.mark.parametrize('args',[['status'],['doctor'],['roadmap'],['requirements'],['architecture'],['feature','F001'],['log'],['agent','list'],['agent','use','mock'],['verify'],['clarify']])
def test_read_commands(root,args):
    r=CliRunner().invoke(app,[*args,'--root',str(root)])
    assert r.exit_code==0,r.output

def test_watch_stops_cleanly(root):
    with patch('universal_sdd.cli.time.sleep',side_effect=KeyboardInterrupt):
        r=CliRunner().invoke(app,['watch','--root',str(root)])
    assert r.exit_code==0
    assert 'SDD Project Status' in r.output

def test_intervention(root):
    r=CliRunner().invoke(app,['intervene','--root',str(root)],input='Why this design?\nchange: broken behavior\nexit\n')
    assert r.exit_code==0,r.output
    assert 'Architect response' in r.output
    assert 'implementation_defect' in r.output

def test_pause_and_resume(root):
    runner=CliRunner()
    assert runner.invoke(app,['pause','--root',str(root)]).exit_code==0
    assert runner.invoke(app,['resume','--root',str(root)]).exit_code==0
    assert load_project_state(SDDPaths(root)).run_status==RunStatus.completed

@pytest.mark.parametrize('choice,extra',[('a','Why?\n2\nDjango approved\n'),('o','Custom backend\nExisting constraint\n'),('d',''),('bad','1\nApproved\n')])
def test_architecture_choices(demo_repo,choice,extra):
    r=CliRunner().invoke(app,['init','--root',str(demo_repo),'--agent','mock','--project-kind','new'],input=choice+'\n'+extra)
    assert r.exit_code==0,r.output

def test_force_keeps_backup(root):
    marker=root/'.sdd/keep.txt';marker.write_text('evidence')
    r=CliRunner().invoke(app,['init','--root',str(root),'--agent','mock','--force','--yes'])
    assert r.exit_code==0
    assert any((p/'keep.txt').read_text()=='evidence' for p in root.glob('.sdd-backup-*'))

@pytest.mark.parametrize('cmd',[['feature','missing'],['status'],['verify']])
def test_invalid_or_uninitialized_commands(tmp_path,cmd):
    r=CliRunner().invoke(app,[*cmd,'--root',str(tmp_path)])
    assert r.exit_code!=0

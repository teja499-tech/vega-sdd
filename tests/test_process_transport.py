import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch
import pytest
from universal_sdd.adapters.base import AgentAdapter
from universal_sdd.adapters.codex import CodexAdapter
from universal_sdd.adapters.claude import ClaudeAdapter
from universal_sdd.adapters.cursor import CursorAdapter
from universal_sdd.models import AgentCapabilities

class Local(AgentAdapter):
    def capabilities(self):return AgentCapabilities(installed=True)
    def build_command(self,prompt,**kwargs):return [sys.executable,'-c',prompt]

def test_stream_callback_and_nonzero(tmp_path):
    events=[]
    result=Local(tmp_path).run("import sys; print('hello'); sys.stderr.write('failure'); sys.exit(3)",on_event=events.append)
    assert result.exit_code==3 and not result.success
    assert 'failure' in result.text and events[0].message=='hello'

def test_missing_binary(tmp_path):
    a=Local(tmp_path);a.build_command=lambda *args,**kwargs:['/nonexistent/sdd-fixture']
    assert a.run('x').exit_code==127

@pytest.mark.parametrize('line',['[]','42','null','"text"','plain text'])
def test_nonobject_events(tmp_path,line):
    assert Local(tmp_path).parse_event(line).type=='agent_output'

@pytest.mark.parametrize('adapter,events,expected',[
    (CodexAdapter,[{'type':'item.completed','item':{'type':'agent_message','text':'final'}}],'final'),
    (ClaudeAdapter,[{'type':'assistant','message':{'content':[{'text':'draft'}]}},{'type':'result','result':'final'}],'final'),
    (CursorAdapter,[{'type':'result','result':'final'}],'final')])
def test_synthetic_provider_response_parsing(tmp_path,adapter,events,expected):
    assert adapter(tmp_path).final_text([json.dumps(e)+'\n' for e in events])==expected

def test_zero_exit_error_is_not_success(tmp_path):
    r=Local(tmp_path).run("print('{\"type\":\"result\",\"is_error\":true,\"result\":\"failed\"}')")
    assert not r.success

@pytest.mark.skipif(os.name=='nt',reason='POSIX process group behavior')
def test_interrupt_terminates_child_process(tmp_path):
    a=Local(tmp_path)
    def stop(event):
        assert a.interrupt()
    r=a.run("import time; print('ready',flush=True); time.sleep(30)",on_event=stop)
    assert not r.success
    assert a._active is None

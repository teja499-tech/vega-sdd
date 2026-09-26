"""Inject a clearly labelled subprocess fixture into the unchanged CLI routing."""
import json
import sys
import tempfile
from pathlib import Path
from universal_sdd.adapters.base import AgentAdapter
from universal_sdd.models import AgentCapabilities
import universal_sdd.cli as cli
import universal_sdd.orchestrator as orchestrator
class FixtureProcessAdapter(AgentAdapter):
    name='scripted-process-fixture'
    def capabilities(self):return AgentCapabilities(installed=True,authenticated=True,command='SCRIPTED_FIXTURE',version='not-a-provider')
    def build_command(self,prompt,**kwargs):
        # Prompt file avoids OS argument-size limits for this fixture transport.
        p=self.root/'.fixture-prompt.txt';p.write_text(prompt)
        return [sys.executable,str(Path(__file__).with_name('fixture_agent.py')),str(p)]
    def final_text(self,lines):return json.loads(lines[-1])['result']
cli.get_adapter=lambda name,root:FixtureProcessAdapter(root)
orchestrator.get_adapter=cli.get_adapter
if __name__=='__main__':cli.app()

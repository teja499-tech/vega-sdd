"""Generated verification and delivery pipelines; user edits are never overwritten."""
import hashlib
import json
import re
from pathlib import Path
import yaml
from .storage import atomic_write
from .workspace import load_workspace,ordered,policy_hash,gaps
CHECKOUT='actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1'
UPLOAD='actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a'
DOWNLOAD='actions/download-artifact@70fc10c6e5e1ce46ad2ea6f2b72d43f7d47b13c3'
RUNNER='''import hashlib,json,os,signal,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[2]
plan=json.loads((root/'.sdd/ci/plan.json').read_text())
if hashlib.sha256((root/'.sdd/workspace.yaml').read_bytes()).hexdigest()!=plan['policy']:
 raise SystemExit('Stale pipeline policy; regenerate through sdd pipeline export')
for item in plan['commands']:
 if '--setup-only' in sys.argv and item['label']!='Setup':continue
 cwd=(root/item['cwd']).resolve()
 if not cwd.is_relative_to(root):raise SystemExit('Invalid working directory')
 missing=[x for x in item['env_names'] if x not in os.environ]
 if missing:raise SystemExit('Missing environment names: '+','.join(missing))
 p=subprocess.Popen(item['argv'],cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,start_new_session=os.name!='nt')
 try:output,_=p.communicate(timeout=item['timeout'])
 except subprocess.TimeoutExpired:
  if os.name!='nt':os.killpg(p.pid,signal.SIGKILL)
  else:p.kill()
  p.communicate();raise SystemExit(124)
 for key in item['env_names']:
  if os.environ.get(key):output=output.replace(os.environ[key],'<redacted>')
 print(item['label'],output[-20000:],flush=True)
 if p.returncode:raise SystemExit(p.returncode)
'''

def export(root:Path,provider:str,wheel:Path|None=None,update_generated=False):
    cfg=load_workspace(root)
    if gaps(cfg):raise RuntimeError('; '.join(gaps(cfg)))
    cmds=[{'label':'Setup','cwd':'.',**x.model_dump()} for x in cfg.setup]
    for c in ordered(cfg.components):
        cmds.extend({'label':c.id+'/'+name,'cwd':c.path,**command.model_dump()} for name,command in c.checks.items())
    if not cmds:raise RuntimeError('No executable checks')
    files={'.sdd/ci/verify.py':RUNNER,'.sdd/ci/plan.json':json.dumps({'policy':policy_hash(root),'commands':cmds},indent=2)+'\n'}
    if provider=='github':
        files['.github/workflows/sdd-checks.yml']=yaml.safe_dump({'name':'SDD verification','on':{'pull_request':{},'push':{'branches':[cfg.repo.base_branch]},'merge_group':{}},'permissions':{'contents':'read'},'jobs':{'verify':{'name':'SDD checks','runs-on':'ubuntu-latest','timeout-minutes':60,'steps':[{'uses':CHECKOUT,'with':{'persist-credentials':False}},{'run':'python3 .sdd/ci/verify.py'}]}}},sort_keys=False)
    elif provider=='gitlab':
        files['.sdd/ci/gitlab-sdd.yml']=yaml.safe_dump({'sdd-checks':{'stage':'test','image':'python:3.12-slim','rules':[{'if':'$CI_PIPELINE_SOURCE == "merge_request_event"'},{'if':'$CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH'}],'script':['python .sdd/ci/verify.py']}},sort_keys=False)
        files['.sdd/ci/GITLAB_INSTALL.md']='Review runner/toolchain; include this fragment in the existing .gitlab-ci.yml. Configure branch approval/check policy on the host.\n'
    elif provider=='azure':
        files['.sdd/ci/azure-sdd.yml']=yaml.safe_dump({'steps':[{'script':'python .sdd/ci/verify.py','displayName':'SDD checks'}]},sort_keys=False)
        files['.sdd/ci/AZURE_INSTALL.md']='Reference this steps template in the existing pipeline. Configure build validation and reviewers on the host.\n'
    else:raise ValueError('Expected github, gitlab or azure')
    if wheel:
        if provider!='github':raise ValueError('Hosted delivery export currently GitHub only')
        if not wheel.is_file() or not re.fullmatch(r'universal_sdd-[A-Za-z0-9_.+-]+\.whl',wheel.name):raise ValueError('Supply tested wheel')
        files['.sdd/ci/'+wheel.name]=wheel.read_bytes()
        build=[{'uses':CHECKOUT,'with':{'persist-credentials':False,'fetch-depth':0}},{'run':f'python3 -m pip install .sdd/ci/{wheel.name}'},{'run':'python3 .sdd/ci/verify.py'},{'run':'sdd project configure --file .sdd/workspace.yaml'},{'run':'sdd project check'},{'run':'sdd release build "$SDD_VERSION"','env':{'SDD_VERSION':'${{ inputs.version }}'}},{'uses':UPLOAD,'with':{'name':'sdd-release','include-hidden-files':True,'path':'.sdd/artifacts/\n.sdd/releases/\n.sdd/state/quality.yaml','if-no-files-found':'error'}}]
        jobs={'build':{'if':"${{ github.ref == 'refs/heads/"+cfg.repo.base_branch+"' }}",'runs-on':'ubuntu-latest','timeout-minutes':60,'steps':build}}
        for name,env in cfg.environments.items():
            needs=['build','deploy-'+env.promote_from] if env.promote_from else ['build']
            steps=[{'uses':CHECKOUT,'with':{'persist-credentials':False,'fetch-depth':0}},{'uses':DOWNLOAD,'with':{'name':'sdd-release','path':'.sdd'}}]
            if env.promote_from:steps.append({'uses':DOWNLOAD,'with':{'name':'receipt-'+env.promote_from,'path':'.sdd/state/deployments'}})
            steps.extend([{'run':f'python3 -m pip install .sdd/ci/{wheel.name}'},{'run':'python3 .sdd/ci/verify.py --setup-only'},{'run':'sdd project configure --file .sdd/workspace.yaml'},{'run':f'sdd release deploy "$SDD_VERSION" {name} --approve','env':{'SDD_VERSION':'${{ inputs.version }}'}},{'uses':UPLOAD,'if':'always()','with':{'name':'receipt-'+name,'include-hidden-files':True,'path':'.sdd/state/deployments/'+name+'.yaml','if-no-files-found':'warn'}}])
            job={'needs':needs,'runs-on':'ubuntu-latest','timeout-minutes':60,'environment':name,'steps':steps}
            if env.requires_approval:job['if']='${{ inputs.approve == true }}'
            jobs['deploy-'+name]=job
        files['.github/workflows/sdd-delivery.yml']=yaml.safe_dump({'name':'SDD delivery','on':{'workflow_dispatch':{'inputs':{'version':{'type':'string','required':True},'approve':{'type':'boolean','required':True,'default':False}}}},'permissions':{'contents':'read'},'concurrency':{'group':'sdd-delivery','cancel-in-progress':False},'jobs':jobs},sort_keys=False)
        files['.sdd/ci/DELIVERY_SETUP.md']='Configure protected environments, secrets/identity, actual runner/toolchain and review action SHA pins before enabling. The export does not provision host policy or a cloud account.\n'
    manifest=root/'.sdd/state/pipeline-files.json';prior=json.loads(manifest.read_text()) if manifest.exists() else {}
    def hash_bytes(value):return hashlib.sha256(value).hexdigest()
    conflicts=[name for name,value in files.items() if (root/name).exists() and (root/name).read_bytes()!=(value if isinstance(value,bytes) else value.encode()) and not (update_generated and prior.get(name)==hash_bytes((root/name).read_bytes()))]
    if conflicts:raise RuntimeError('Existing files preserved; review conflicts: '+', '.join(conflicts))
    for name,value in files.items():
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
        if isinstance(value,bytes):path.write_bytes(value)
        else:atomic_write(path,value)
    prior.update({name:hash_bytes(value if isinstance(value,bytes) else value.encode()) for name,value in files.items()})
    atomic_write(manifest,json.dumps(prior,indent=2)+'\n')
    return sorted(files)

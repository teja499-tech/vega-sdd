"""Versioned canonical state checkpoints with evidence invalidation."""
import hashlib
import json
import re
import uuid
from pathlib import Path
import yaml
from .storage import SDDPaths,atomic_write,dump_yaml,load_yaml
from .models import utcnow,SDDConfig,SpecBundle,ProjectState,Feature
FILES=['config.yaml','workspace.yaml','state/project.yaml','state/features.yaml','state/requirements.yaml','state/spec-bundle.yaml','state/architecture-decisions.yaml','state/verification.yaml','state/workspace-approval.yaml']
def checkpoint(root:Path):
    data={name:(root/'.sdd'/name).read_text() for name in FILES if (root/'.sdd'/name).exists()}
    digest=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
    record={'id':'CHK-'+uuid.uuid4().hex[:12],'created_at':utcnow(),'files':data,'sha256':digest}
    atomic_write(root/'.sdd/recovery'/f'{record["id"]}.json',json.dumps(record,indent=2))
    return {'id':record['id'],'files':len(data),'sha256':digest}
def restore(root:Path,identifier:str):
    if not re.fullmatch(r'CHK-[a-f0-9]{12}',identifier):raise ValueError('Invalid checkpoint')
    record=json.loads((root/'.sdd/recovery'/f'{identifier}.json').read_text())
    if set(record['files'])-set(FILES):raise ValueError('Unauthorized checkpoint paths')
    if hashlib.sha256(json.dumps(record['files'],sort_keys=True).encode()).hexdigest()!=record['sha256']:raise ValueError('Checkpoint digest mismatch')
    parsed={k:yaml.safe_load(v) for k,v in record['files'].items()}
    for name,cls in [('config.yaml',SDDConfig),('state/project.yaml',ProjectState),('state/spec-bundle.yaml',SpecBundle)]:
        if name in parsed:cls.model_validate(parsed[name])
    for item in parsed.get('state/features.yaml',[]):Feature.model_validate(item)
    if 'workspace.yaml' in parsed:
        from .workspace import Workspace
        Workspace.model_validate(parsed['workspace.yaml'])
    backup=checkpoint(root)
    for name,text in record['files'].items():atomic_write(root/'.sdd'/name,text)
    state=parsed.get('state/project.yaml',{}) or {};state.update(run_status='paused',current_task=None,current_feature=None,pause_requested=False,last_checkpoint=identifier)
    dump_yaml(root/'.sdd/state/project.yaml',state)
    features=parsed.get('state/features.yaml',[]) or []
    for f in features:
        f['status']='invalidated'
        for t in f.get('tasks',[]):t.update(status='invalidated',evidence=[])
    dump_yaml(root/'.sdd/state/features.yaml',features)
    (root/'.sdd/state/lifecycle.yaml').unlink(missing_ok=True)
    dump_yaml(root/'.sdd/state/quality.yaml',{'passed':False,'reason':'Checkpoint restored; re-verification required'})
    from .status import publish_status
    from .documentation import render_docs
    from .journal import Journal
    paths=SDDPaths(root);publish_status(paths)
    if paths.spec_bundle_file.exists():render_docs(paths)
    Journal(paths.event_log).append('checkpoint_restored',checkpoint=identifier,backup=backup['id'])
    return {'restored':identifier,'backup':backup['id'],'verification':'invalidated'}

"""Immutable artifact and deployment receipts with explicit uncertain-state recovery."""
import hashlib
import re
import shutil
import uuid
from pathlib import Path
from .models import utcnow
from .storage import dump_yaml,load_yaml
from .workspace import load_workspace,execute,inside,quality_current,fingerprint,git_head,policy_hash,ordered
from .delivery import source_dirty

def valid(value):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',value):raise ValueError('Invalid release/environment ID')
    return value
def record_path(root,version):return root/'.sdd/releases'/f'{valid(version)}.yaml'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def deployment_path(root,env):return root/'.sdd/state/deployments'/f'{valid(env)}.yaml'
def build(root:Path,version:str):
    cfg=load_workspace(root);target=record_path(root,version)
    if target.exists():raise RuntimeError('Immutable release version exists')
    if source_dirty(root) or not quality_current(root):raise RuntimeError('Commit and run fresh full checks before release')
    if any(not c.build or not c.artifact for c in cfg.components):raise RuntimeError('Every component requires build/artifact')
    baseline=fingerprint(root);artifacts=[]
    for c in ordered(cfg.components):
        result=execute(c.build,inside(root,c.path))
        if result['returncode']:raise RuntimeError('Build failed: '+result['output'])
        output=inside(inside(root,c.path),c.artifact)
        if not output.is_file() or output.is_symlink():raise RuntimeError('Build must produce regular artifact')
        sha=digest(output);dest=root/'.sdd/artifacts'/sha/output.name
        dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists() and digest(dest)!=sha:raise RuntimeError('Stored artifact corrupt')
        shutil.copyfile(output,dest)
        artifacts.append({'component':c.id,'path':str(dest.relative_to(root)),'sha256':sha})
    if fingerprint(root)!=baseline:raise RuntimeError('Build modified source')
    record={'version':version,'created_at':utcnow(),'head':git_head(root),'policy':policy_hash(root),'fingerprint':baseline,'artifacts':artifacts,'quality':load_yaml(root/'.sdd/state/quality.yaml',{}).get('id'),'pull_request':load_yaml(root/'.sdd/state/pull-request.yaml',{})}
    dump_yaml(target,record)
    (root/'.sdd/releases'/f'{version}.md').write_text('# Release '+version+'\n\nCommit: '+str(record['head'])+'\n\nArtifact SHA-256:\n'+'\n'.join('- '+a['component']+': '+a['sha256'] for a in artifacts)+'\n')
    return record

def deploy(root:Path,version:str,environment:str,approve=False,rollback=False):
    cfg=load_workspace(root)
    if environment not in cfg.environments:raise ValueError('Unknown environment')
    env=cfg.environments[environment];release=load_yaml(record_path(root,version))
    if not release:raise ValueError('Unknown release')
    if source_dirty(root) or fingerprint(root)!=release['fingerprint'] or policy_hash(root)!=release['policy']:raise RuntimeError('Checkout exact release source/policy before deployment')
    if any(not inside(root,a['path']).is_file() or digest(inside(root,a['path']))!=a['sha256'] for a in release['artifacts']):raise RuntimeError('Artifact missing/digest mismatch')
    statefile=deployment_path(root,environment);previous=load_yaml(statefile,{}) or {}
    if previous.get('status') in {'started','unknown'}:raise RuntimeError('Unknown deployment; reconcile before retry')
    if previous.get('status')=='succeeded' and previous.get('version')==version and not rollback:return previous
    if env.requires_approval and not approve:raise RuntimeError('Release-specific approval required')
    if rollback:
        if not env.rollback or previous.get('previous_version')!=version:raise RuntimeError('Rollback target must be previous successful release')
    elif env.promote_from:
        prior=load_yaml(deployment_path(root,env.promote_from),{}) or {}
        if prior.get('status')!='succeeded' or prior.get('version')!=version:raise RuntimeError('Promote same version from '+env.promote_from)
    op='DEPLOY-'+uuid.uuid4().hex[:12]
    receipt={'operation':op,'status':'started','version':version,'environment':environment,'previous_version':previous.get('version') if previous.get('status')=='succeeded' else previous.get('previous_version'),'approved':approve or not env.requires_approval,'timestamp':utcnow(),'rollback':rollback}
    evidence=root/'.sdd/evidence/deployments'/f'{op}.yaml'
    dump_yaml(statefile,receipt);dump_yaml(evidence,receipt)
    variables={'SDD_RELEASE_MANIFEST':str(record_path(root,version).resolve()),'SDD_RELEASE_VERSION':version,'SDD_ENVIRONMENT':environment,'SDD_OPERATION_ID':op}
    try:
        result=execute(env.rollback if rollback else env.deploy,root,variables);receipt['deploy_result']=result
        if result['returncode']:receipt['status']='unknown'
        else:
            smoke=execute(env.smoke,root,variables);receipt['smoke_result']=smoke
            intact=all(inside(root,a['path']).is_file() and digest(inside(root,a['path']))==a['sha256'] for a in release['artifacts'])
            receipt['status']='succeeded' if not smoke['returncode'] and intact and fingerprint(root)==release['fingerprint'] else 'unknown'
    except BaseException:
        receipt['status']='unknown';dump_yaml(statefile,receipt);dump_yaml(evidence,receipt);raise
    receipt['finished_at']=utcnow();dump_yaml(statefile,receipt);dump_yaml(evidence,receipt)
    return receipt

def reconcile(root:Path,environment:str,outcome:str,note:str):
    cfg=load_workspace(root)
    if environment not in cfg.environments or outcome not in {'succeeded','failed'} or len(note.strip())<15:raise ValueError('Supply environment, observed outcome and evidence')
    file=deployment_path(root,environment);record=load_yaml(file,{}) or {}
    if record.get('status') not in {'started','unknown'}:raise RuntimeError('No uncertain operation')
    if outcome=='succeeded':
        release=load_yaml(record_path(root,record['version']))
        if fingerprint(root)!=release['fingerprint'] or policy_hash(root)!=release['policy']:raise RuntimeError('Release source/policy changed')
        if any(not inside(root,a['path']).is_file() or digest(inside(root,a['path']))!=a['sha256'] for a in release['artifacts']):raise RuntimeError('Artifact digest mismatch')
        env={'SDD_RELEASE_MANIFEST':str(record_path(root,record['version']).resolve()),'SDD_RELEASE_VERSION':record['version'],'SDD_ENVIRONMENT':environment,'SDD_OPERATION_ID':record['operation']}
        smoke=execute(cfg.environments[environment].smoke,root,env)
        if smoke['returncode']:raise RuntimeError('Smoke failed; cannot mark success')
        record['smoke_result']=smoke
    record.update(status=outcome,reconciled_at=utcnow(),reconciliation_note=note)
    dump_yaml(file,record);dump_yaml(root/'.sdd/evidence/deployments'/f'{record["operation"]}.yaml',record)
    return record

"""Resumable single-project implementation through reviewed delivery."""
import shutil
import uuid
from pathlib import Path
from .storage import SDDPaths,dump_yaml,load_yaml,project_lock,load_project_state
from .models import RunStatus,utcnow
from .workspace import load_workspace,run_checks,git_head
from .delivery import branch,create_branch,source_dirty,changed_files,guard,git,Provider,merge_gaps
from .orchestrator import run_development
from . import releases

def advance(root:Path,version=None,environment=None,approve=False):
    cfg=load_workspace(root);path=root/'.sdd/state/lifecycle.yaml'
    state=load_yaml(path,{}) or {'id':'FLOW-'+uuid.uuid4().hex[:12],'stage':'prepare'}
    def save(stage,message,**extra):
        state.update(stage=stage,message=message,updated_at=utcnow(),**extra);dump_yaml(path,state);return state
    if state['stage']=='prepare':
        with project_lock(root):
            if source_dirty(root):return save('prepare','Commit existing source before autonomous execution')
            if branch(root)==cfg.repo.base_branch:create_branch(root,state['id'].lower())
            guard(root)
            tasks=[t['id'] for f in load_yaml(root/'.sdd/state/features.yaml',[]) for t in f.get('tasks',[]) if t.get('status')!='verified']
            save('implement','Execution branch ready',branch=branch(root),tasks=tasks)
    if branch(root)!=state.get('branch'):raise RuntimeError('Resume from lifecycle branch '+str(state.get('branch')))
    if load_project_state(SDDPaths(root)).run_status!=RunStatus.completed:
        run_development(root)
        if load_project_state(SDDPaths(root)).run_status!=RunStatus.completed:return save('implement','Implementation paused or blocked; inspect status and resume')
    with project_lock(root):
        result=run_checks(root)
        if not result['passed']:return save('verify','Full checks failed',evidence=result['id'])
        if source_dirty(root):
            if not cfg.repo.auto_commit:return save('commit','Commit verified changes explicitly under repository policy')
            files=changed_files(root)
            forbidden=[p for p in files if Path(p).name.startswith('.env') or Path(p).name in {'credentials.json','id_rsa','id_ed25519'} or p.endswith(('.pem','.key','.p12','.pfx'))]
            if forbidden or git(root,'diff','--cached','--name-only'):return save('commit','Potential credentials or preexisting staging need review',files=forbidden)
            files=[p for p in files if not p.startswith(('.sdd/runtime/','.sdd/evidence/','.sdd/recovery/','.sdd/artifacts/','.sdd/journal/','.sdd/state/deployments/'))]
            if files:
                git(root,'add','--',*files)
                tasks=[t for f in load_yaml(root/'.sdd/state/features.yaml',[]) for t in f.get('tasks',[]) if t['id'] in state.get('tasks',[]) and t.get('status')=='verified']
                msg=root/'.sdd/runtime/lifecycle-commit.txt';msg.parent.mkdir(parents=True,exist_ok=True)
                msg.write_text('Implement verified SDD work\n\n'+''.join('SDD-Task: '+t['id']+'\n' for t in tasks))
                git(root,'commit','-F',str(msg))
                from .history import link_commit
                for task in tasks:link_commit(SDDPaths(root),task['id'],git_head(root),'Lifecycle commit; review exact diff for attribution')
        if cfg.repo.provider!='local':
            if not cfg.repo.allow_push:return save('publish','PR publication disabled by policy')
            provider=Provider(root);current=state.get('pr')
            if not current:
                current=provider.open('SDD implementation '+state['id'],'# Verified implementation\n\nSee .sdd/docs/TRACEABILITY.md and .sdd/CHANGELOG.md.');save('review','PR published',pr=current)
            current=provider.view(current['id'])
            if current.get('state')!='merged':
                if not cfg.repo.allow_merge:return save('review','Awaiting authorized merge',pr=current)
                problems=merge_gaps(current,cfg.repo,git_head(root))
                if problems:return save('review','; '.join(problems),pr=current)
                current=provider.merge(current['id'])
                if current.get('state')!='merged':return save('merge','Merge queued; resume after completion',pr=current)
            save('merged','Host reported merged PR',pr=current)
            if not version:return state
            merged=current.get('merge_commit')
            if not merged or len(merged)!=40 or any(x not in '0123456789abcdef' for x in merged):return save('merged','Provider must report actual integration commit')
            git(root,'fetch','--no-tags',cfg.repo.remote,cfg.repo.base_branch)
            if git(root,'merge-base',merged,cfg.repo.remote+'/'+cfg.repo.base_branch)!=merged:raise RuntimeError('Integration commit not on fetched base branch')
            release_root=root/'.sdd/runtime/release-worktrees'/merged
            if not release_root.exists():
                release_root.parent.mkdir(parents=True,exist_ok=True)
                git(root,'worktree','add','--detach',str(release_root),merged)
                shutil.copytree(root/'.sdd',release_root/'.sdd',dirs_exist_ok=True,ignore=shutil.ignore_patterns('runtime'))
            if git_head(release_root)!=merged:raise RuntimeError('Release worktree HEAD changed')
            checked=run_checks(release_root)
            if not checked['passed']:return save('release_verify','Merged source checks failed',release_root=str(release_root))
            root=release_root
        if not version:return save('verified','Provide version/environment to package or deliver')
        if not releases.record_path(root,version).exists():releases.build(root,version)
        if not environment:return save('packaged','Immutable artifacts built',version=version,release_root=str(root))
        delivered=releases.deploy(root,version,environment,approve)
        return save('delivered' if delivered['status']=='succeeded' else 'deployment_unknown','Delivery operation recorded',version=version,deployment=delivered,release_root=str(root))

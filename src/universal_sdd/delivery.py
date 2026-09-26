"""Local Git guards and policy-gated hosted PR delivery."""
import fnmatch
import json
import re
import shutil
import subprocess
from pathlib import Path
from .storage import dump_yaml,load_yaml
from .workspace import load_workspace,execute,quality_current,git_head,inside

def git(root,*args):
    p=subprocess.run(['git',*args],cwd=root,capture_output=True,text=True,timeout=120)
    if p.returncode:raise RuntimeError('Git failed: '+p.stderr[-2000:])
    return p.stdout.strip()
def branch(root):return git(root,'branch','--show-current')
def changed_files(root):
    files=[]
    for args in [('diff','--name-only','-z','HEAD'),('ls-files','--others','--exclude-standard','-z')]:
        p=subprocess.run(['git',*args],cwd=root,capture_output=True,text=True,timeout=60)
        if p.returncode:raise RuntimeError('Git inventory failed: '+p.stderr)
        files.extend(name for name in p.stdout.split('\0') if name)
    return sorted(set(files))
def source_dirty(root):
    return [x for x in changed_files(root) if x!='.sdd-controller.lock' and (not x.startswith('.sdd/') or x.startswith('.sdd/ci/'))]
def guard(root,clean=False):
    cfg=load_workspace(root);current=branch(root)
    if not current:raise RuntimeError('Detached/unborn Git HEAD')
    if current==cfg.repo.base_branch or any(fnmatch.fnmatch(current,x) for x in cfg.repo.protected_branches):raise RuntimeError('Protected branch: create an execution branch')
    if git(root,'ls-files','-u'):raise RuntimeError('Resolve merge conflicts')
    if clean and source_dirty(root):raise RuntimeError('Commit intentional source before delivery')
    return cfg

def create_branch(root:Path,name:str,worktree:Path|None=None):
    cfg=load_workspace(root)
    if source_dirty(root):raise RuntimeError('Preserve/commit existing source; no auto-stash')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_/-]*',name):raise ValueError('Invalid branch scope')
    target=cfg.repo.branch_prefix+'/'+name
    git(root,'check-ref-format','--branch',target)
    if target==cfg.repo.base_branch or any(fnmatch.fnmatch(target,x) for x in cfg.repo.protected_branches):raise ValueError('Protected target')
    if worktree:
        worktree=worktree.resolve()
        if worktree.exists():raise ValueError('Worktree already exists')
        git(root,'worktree','add','-b',target,str(worktree),cfg.repo.base_branch)
        shutil.copytree(root/'.sdd',worktree/'.sdd',dirs_exist_ok=True,ignore=shutil.ignore_patterns('runtime'))
    else:git(root,'switch','-c',target,cfg.repo.base_branch)
    return {'branch':target,'root':str(worktree or root)}

def merge_gaps(data,policy,head):
    gaps=[]
    if data.get('state')!='open' or data.get('draft',True):gaps.append('PR not open/ready')
    if data.get('head')!=head or data.get('base')!=policy.base_branch:gaps.append('PR head/base mismatch')
    if data.get('mergeable') is not True:gaps.append('Mergeability not confirmed')
    if policy.require_review and data.get('review')!='APPROVED':gaps.append('Current review missing')
    checks={}
    for c in data.get('checks',[]):checks.setdefault(c.get('name'),[]).append(c.get('status'))
    for name in policy.required_checks:
        if not checks.get(name) or any(x not in {'SUCCESS','success'} for x in checks[name]):gaps.append('Required check not successful: '+name)
    return gaps

class Provider:
    def __init__(self,root):self.root=Path(root);self.cfg=load_workspace(root)
    def gh(self,*args):
        p=subprocess.run(['gh',*args],cwd=self.root,capture_output=True,text=True,timeout=120)
        if p.returncode:raise RuntimeError('GitHub CLI failed: '+p.stderr[-2000:])
        return p.stdout.strip()
    def custom(self,action,payload):
        cmd=self.cfg.repo.provider_commands[action]
        result=execute(cmd,self.root,{'SDD_REQUEST':json.dumps(payload)},separate_stderr=True)
        if result['returncode']:raise RuntimeError('Provider command failed: '+result['stderr']+' '+result['output'])
        data=json.loads(result['output'])
        if not isinstance(data,dict):raise ValueError('Provider must return JSON object')
        return data
    def view(self,identifier):
        if self.cfg.repo.provider=='command':return self.custom('view',{'id':identifier})
        if self.cfg.repo.provider!='github':raise RuntimeError('Local provider has no PRs')
        data=json.loads(self.gh('pr','view',str(identifier),'--repo',self.cfg.repo.repository,'--json','number,url,state,isDraft,headRefOid,baseRefName,reviewDecision,mergeStateStatus,statusCheckRollup,mergeCommit'))
        return {'id':data['number'],'url':data['url'],'state':data['state'].lower(),'draft':data['isDraft'],'head':data['headRefOid'],'base':data['baseRefName'],'review':data.get('reviewDecision'),'mergeable':data.get('mergeStateStatus')=='CLEAN','merge_commit':(data.get('mergeCommit') or {}).get('oid'),'checks':[{'name':c.get('name',c.get('context','')),'status':c.get('conclusion',c.get('state'))} for c in data.get('statusCheckRollup') or []]}
    def open(self,title,body):
        policy=guard(self.root,clean=True).repo
        if not policy.allow_push:raise RuntimeError('Push disabled by policy')
        if not quality_current(self.root):raise RuntimeError('Full source verification stale')
        if policy.provider=='local':raise RuntimeError('Configure hosted provider')
        current=branch(self.root);head=git_head(self.root)
        git(self.root,'push','--set-upstream',policy.remote,current)
        if policy.provider=='command':record=self.custom('open',{'branch':current,'base':policy.base_branch,'head':head,'title':title,'body':body})
        else:
            existing=json.loads(self.gh('pr','list','--repo',policy.repository,'--head',current,'--base',policy.base_branch,'--state','open','--json','number'))
            if len(existing)>1:raise RuntimeError('Ambiguous matching PRs')
            if existing:identifier=existing[0]['number']
            else:
                p=self.root/'.sdd/runtime/pr-body.md';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(body)
                identifier=self.gh('pr','create','--repo',policy.repository,'--base',policy.base_branch,'--head',current,'--title',title,'--body-file',str(p))
            record=self.view(identifier)
        if record.get('head')!=head or record.get('base')!=policy.base_branch:raise RuntimeError('PR head/base mismatch')
        dump_yaml(self.root/'.sdd/state/pull-request.yaml',record)
        return record
    def merge(self,identifier):
        policy=guard(self.root,clean=True).repo
        if not policy.allow_merge or not quality_current(self.root):raise RuntimeError('Merge disabled or local checks stale')
        data=self.view(identifier);problems=merge_gaps(data,policy,git_head(self.root))
        if problems:raise RuntimeError('; '.join(problems))
        if policy.provider=='github':self.gh('pr','merge',str(identifier),'--repo',policy.repository,'--'+policy.merge_method,'--match-head-commit',data['head'])
        else:self.custom('merge',{'id':identifier,'expected_head':data['head'],'method':policy.merge_method})
        result=self.view(identifier);dump_yaml(self.root/'.sdd/state/pull-request.yaml',result)
        return result

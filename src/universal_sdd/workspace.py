"""Typed, approved, stack-neutral project execution contracts."""
from __future__ import annotations
import hashlib
import json
import os
import re
import signal
import subprocess
import uuid
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from .models import utcnow
from .storage import dump_yaml, load_yaml

PROFILES = {
    'web': ['test', 'accessibility'], 'service': ['test', 'contract'],
    'library': ['test', 'compatibility'], 'cli': ['test', 'smoke'],
    'data_pipeline': ['test', 'data_quality', 'replay'], 'ml': ['test', 'evaluation'],
    'infrastructure': ['test', 'plan'], 'mobile': ['test', 'device'],
    'desktop': ['test', 'platform'], 'embedded': ['test', 'hardware'],
    'docs': ['links'], 'custom': ['test'],
}
class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')
class Command(Strict):
    argv: list[str] = Field(min_length=1)
    timeout: int = Field(default=300, ge=1, le=86400)
    env_names: list[str] = Field(default_factory=list)
    run_at: Literal['task', 'release'] = 'task'
    @field_validator('argv')
    @classmethod
    def valid(cls, value):
        if not value[0] or any('\x00' in x for x in value): raise ValueError('Invalid argv')
        return value
class Component(Strict):
    id: str = Field(pattern=r'^[A-Za-z][A-Za-z0-9_-]*$')
    path: str = '.'
    kind: str
    depends_on: list[str] = Field(default_factory=list)
    checks: dict[str, Command] = Field(default_factory=dict)
    waivers: dict[str, str] = Field(default_factory=dict)
    build: Command | None = None
    artifact: str | None = None
    @field_validator('kind')
    @classmethod
    def kind_known(cls, v):
        if v not in PROFILES: raise ValueError('Unknown kind; use custom')
        return v
class Environment(Strict):
    deploy: Command
    smoke: Command
    rollback: Command | None = None
    requires_approval: bool = True
    promote_from: str | None = None
class Repository(Strict):
    provider: Literal['local', 'github', 'command'] = 'local'
    repository: str | None = None
    base_branch: str = 'main'
    protected_branches: list[str] = Field(default_factory=lambda: ['main', 'master', 'develop', 'release/*'])
    branch_prefix: str = 'sdd'
    remote: str = 'origin'
    required_checks: list[str] = Field(default_factory=lambda: ['SDD checks'])
    require_review: bool = True
    allow_push: bool = False
    allow_merge: bool = False
    auto_commit: bool = False
    merge_method: Literal['merge', 'squash', 'rebase'] = 'squash'
    provider_commands: dict[str, Command] = Field(default_factory=dict)
    @model_validator(mode='after')
    def valid_provider(self):
        if self.provider == 'github' and (not self.repository or not re.fullmatch(r'[\w.-]+/[\w.-]+', self.repository)):
            raise ValueError('Specify GitHub owner/repository')
        if self.provider == 'command' and not {'open', 'view', 'merge'} <= set(self.provider_commands):
            raise ValueError('Command provider needs open/view/merge hooks')
        if not re.fullmatch(r'[A-Za-z0-9_./-]+', self.base_branch) or '..' in self.base_branch:
            raise ValueError('Invalid integration branch')
        return self
class Workspace(Strict):
    schema_version: Literal[1] = 1
    components: list[Component] = Field(min_length=1)
    repo: Repository = Field(default_factory=Repository)
    environments: dict[str, Environment] = Field(default_factory=dict)
    setup: list[Command] = Field(default_factory=list)
    agent_timeout: int = Field(default=1800, ge=1, le=86400)
    max_tasks_per_run: int = Field(default=50, ge=1, le=10000)
    protected_paths: list[str] = Field(default_factory=list)
    @model_validator(mode='after')
    def valid_graph(self):
        ordered(self.components)
        for name, env in self.environments.items():
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', name): raise ValueError('Invalid environment')
            seen = {name}
            step = env.promote_from
            while step:
                if step not in self.environments or step in seen: raise ValueError('Invalid promotion graph')
                seen.add(step)
                step = self.environments[step].promote_from
        return self

def ordered(components):
    nodes = {c.id: c for c in components}
    if len(nodes) != len(components): raise ValueError('Duplicate component')
    done, stack, result = set(), set(), []
    def visit(name):
        if name not in nodes: raise ValueError('Unknown component dependency: ' + name)
        if name in stack: raise ValueError('Component dependency cycle')
        if name in done: return
        stack.add(name)
        for parent in nodes[name].depends_on: visit(parent)
        stack.remove(name); done.add(name); result.append(nodes[name])
    for name in nodes: visit(name)
    return result

def inside(root: Path, relative: str):
    path = (root / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(root.resolve()): raise ValueError('Path escapes repository: '+relative)
    return path

def policy_path(root): return Path(root) / '.sdd/workspace.yaml'
def policy_hash(root): return hashlib.sha256(policy_path(root).read_bytes()).hexdigest()

def require_approved_capabilities(root: Path, agent_name):
    """Require approval before a real agent can load repository capabilities."""
    name = getattr(agent_name, 'value', str(agent_name))
    if name == 'mock':
        return None
    if not policy_path(root).exists():
        raise RuntimeError('Approve a project policy before real-agent execution: sdd project setup')
    return load_workspace(root)

def capability_hash(root):
    """Bind approved execution to the agent instructions, roles, and skills it will load."""
    root=Path(root);h=hashlib.sha256()
    candidates=[]
    for name in ('.mcp.json','.cursor/mcp.json','.cursorignore','.cursorindexingignore','.github/copilot-instructions.md'):
        path=root/name
        if path.exists():candidates.append(path)
    for pattern in (
        '.agents/**/*', '.codex/**/*', '.claude/**/*',
        '.cursor/agents/**/*', '.cursor/rules/**/*',
        '.github/instructions/**/*.instructions.md',
        '**/AGENTS.md', '**/CLAUDE.md', '**/GEMINI.md',
    ):
        candidates.extend(sorted(root.glob(pattern)))
    unique=sorted(set(candidates),key=lambda p:p.relative_to(root).as_posix())
    if len(unique)>1000:raise RuntimeError('Capability catalog exceeds 1000 files')
    total=0
    for path in unique:
        if path.is_dir() or any(part in {'.git','node_modules','.venv','venv','dist','build'} for part in path.relative_to(root).parts):continue
        if path.is_symlink() or not path.is_file():raise RuntimeError('Capability files must be regular files: '+str(path.relative_to(root)))
        size=path.stat().st_size;total+=size
        if size>1_000_000 or total>32_000_000:raise RuntimeError('Capability files exceed approval size bounds')
        rel=path.relative_to(root).as_posix();h.update(rel.encode()+b'\0'+path.read_bytes()+b'\0')
    return h.hexdigest()
def load_workspace(root):
    config = Workspace.model_validate(load_yaml(policy_path(root)))
    for c in config.components:
        inside(Path(root), c.path)
        if c.artifact: inside(inside(Path(root), c.path), c.artifact)
    approval = load_yaml(Path(root) / '.sdd/state/workspace-approval.yaml', {}) or {}
    if approval.get('sha256') != policy_hash(root): raise RuntimeError('Policy changed or not approved; review and configure it')
    if approval.get('capabilities_sha256') != capability_hash(root):
        raise RuntimeError('Agent instructions, roles, or skills changed after approval; review them and reconfigure the project policy')
    return config

def configure(root: Path, data: dict):
    config = Workspace.model_validate(data)
    for c in config.components:
        if not inside(root, c.path).is_dir(): raise ValueError('Missing component directory')
        if c.artifact: inside(inside(root,c.path),c.artifact)
        for reason in c.waivers.values():
            if len(reason.strip()) < 15: raise ValueError('Waivers need a substantive reason')
    target = policy_path(root)
    if target.exists():
        old = hashlib.sha256(target.read_bytes()).hexdigest()
        copy = root / '.sdd/history/policies' / (old+'.yaml'); copy.parent.mkdir(parents=True,exist_ok=True)
        copy.write_bytes(target.read_bytes())
    dump_yaml(target,config)
    dump_yaml(root/'.sdd/state/workspace-approval.yaml',{
        'sha256':policy_hash(root),'capabilities_sha256':capability_hash(root),'approved_at':utcnow()
    })
    return config

def gaps(config):
    result=[]
    for c in config.components:
        for name in PROFILES[c.kind]:
            if name not in c.checks and name not in c.waivers: result.append(f'{c.id}: missing {name} check or documented waiver')
        if bool(c.build)!=bool(c.artifact): result.append(f'{c.id}: build/artifact must be paired')
    return result

def execute(cmd: Command, cwd: Path, extra_env=None, separate_stderr=False):
    missing=[k for k in cmd.env_names if k not in os.environ]
    if missing: raise RuntimeError('Missing environment variable names: '+', '.join(missing))
    env=os.environ.copy(); env.update(extra_env or {})
    try:
        p=subprocess.Popen(cmd.argv,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE if separate_stderr else subprocess.STDOUT,text=True,start_new_session=os.name!='nt')
    except OSError as e: return {'returncode':127,'output':str(e),'stderr':'','timeout':False}
    timed=False
    try:output,err=p.communicate(timeout=cmd.timeout)
    except subprocess.TimeoutExpired:
        timed=True
        if os.name!='nt': os.killpg(p.pid,signal.SIGKILL)
        else: p.kill()
        output,err=p.communicate()
    except BaseException:
        if os.name!='nt': os.killpg(p.pid,signal.SIGKILL)
        else:p.kill()
        p.communicate();raise
    err=err or ''
    for key in cmd.env_names:
        value=env[key]
        if value:output=output.replace(value,'<redacted>');err=err.replace(value,'<redacted>')
    return {'returncode':124 if timed else p.returncode,'output':output[-20000:],'stderr':err[-20000:],'timeout':timed}

def git_head(root):
    p=subprocess.run(['git','rev-parse','--verify','HEAD'],cwd=root,capture_output=True,text=True)
    return p.stdout.strip() if p.returncode==0 else None

def fingerprint(root):
    root=Path(root)
    p=subprocess.run(['git','ls-files','-co','--exclude-standard','-z'],cwd=root,capture_output=True)
    if p.returncode:raise RuntimeError('Git repository required for source-bound evidence')
    h=hashlib.sha256()
    for name in sorted(set(p.stdout.decode().split('\0'))-{''}):
        if name=='.sdd-controller.lock' or (name.startswith('.sdd/') and not name.startswith('.sdd/ci/')):continue
        path=root/name;h.update(name.encode()+b'\0')
        if path.is_symlink():h.update(('link:'+os.readlink(path)).encode())
        elif path.is_file():h.update(str(path.stat().st_mode & 0o111).encode()+path.read_bytes())
        elif path.is_dir():
            if not (path/'.git').exists():raise RuntimeError('Initialize submodule: '+name)
            sub=subprocess.run(['git','-C',str(path),'rev-parse','HEAD'],capture_output=True)
            if sub.returncode:raise RuntimeError('Submodule missing: '+name)
            h.update(sub.stdout)
            if subprocess.run(['git','-C',str(path),'status','--porcelain'],capture_output=True).stdout:raise RuntimeError('Dirty submodule: '+name)
        else:h.update(b'<deleted>')
    h.update(policy_hash(root).encode())
    h.update(capability_hash(root).encode())
    return h.hexdigest()

def run_checks(root, phase='all'):
    root=Path(root); cfg=load_workspace(root)
    if gaps(cfg):raise RuntimeError('; '.join(gaps(cfg)))
    if phase not in {'all','task','feature','release'}:raise ValueError('Invalid phase')
    before=fingerprint(root); results=[]
    for c in ordered(cfg.components):
        for name,cmd in c.checks.items():
            if phase in {'task', 'feature'} and cmd.run_at=='release':continue
            result=execute(cmd,inside(root,c.path));results.append({'component':c.id,'check':name,**result})
            if result['returncode']:break
        if results and results[-1]['returncode']:break
    data={'id':'CHECK-'+uuid.uuid4().hex[:12],'timestamp':utcnow(),'scope':phase,'fingerprint':before,'policy':policy_hash(root),'head':git_head(root),'results':results,'passed':bool(results) and all(not r['returncode'] for r in results)}
    if fingerprint(root)!=before:data.update(passed=False,reason='Checks changed source')
    dump_yaml(root/'.sdd/evidence'/f'{data["id"]}.yaml',data)
    dump_yaml(root/'.sdd/state/quality.yaml',data)
    return data

def quality_current(root):
    root=Path(root);data=load_yaml(root/'.sdd/state/quality.yaml',{}) or {}
    return bool(data.get('passed') and data.get('scope')=='all' and data.get('fingerprint')==fingerprint(root) and data.get('policy')==policy_hash(root))

def inventory(root:Path):
    import fnmatch
    ignored={'.git','.sdd','node_modules','.venv','venv','__pycache__','build','dist','.gradle','target'}
    markers={'pyproject.toml':'Python package','package.json':'JavaScript/TypeScript','Cargo.toml':'Rust','go.mod':'Go','pom.xml':'Java','build.gradle':'JVM/Android','*.csproj':'.NET','*.xcodeproj':'Apple application','dbt_project.yml':'dbt pipeline','*.tf':'Terraform','CMakeLists.txt':'C/C++','mkdocs.yml':'Documentation'}
    found=[];files=[]
    for folder,dirs,names in os.walk(root):
        dirs[:]=sorted(d for d in dirs if d not in ignored)
        for name in sorted(names)+[x for x in dirs if x.endswith('.xcodeproj')]:
            rel=str((Path(folder)/name).relative_to(root));files.append(rel)
            for pat,kind in markers.items():
                if fnmatch.fnmatch(name,pat):found.append({'path':rel,'ecosystem':kind})
        if len(files)>5000:break
    return {'markers':found,'inventory_truncated':len(files)>5000,'existing_ci':[x for x in files if x.startswith('.github/workflows/') or x in {'.gitlab-ci.yml','azure-pipelines.yml','Jenkinsfile'}],'note':'Manifests are hints; review real components and commands.'}

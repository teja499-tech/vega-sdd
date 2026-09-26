"""Project, Git, pipeline and artifact lifecycle commands."""
import json
import shlex
from pathlib import Path
import typer
from .storage import single_writer,load_yaml,SDDPaths
from .workspace import PROFILES,configure,load_workspace,gaps,run_checks,quality_current
from .delivery import create_branch,Provider,branch,git
from . import pipelines,releases

def show(data):typer.echo(json.dumps(data,indent=2,default=str))
def register(app):
    project=typer.Typer(help='Project profiles, policy and execution checks.')
    repo=typer.Typer(help='Protected branches and reviewed PR delivery.')
    pipeline=typer.Typer(help='Non-overwriting CI/CD export.')
    release=typer.Typer(help='Immutable builds, promotion and recovery.')
    for key,group in [('project',project),('repo',repo),('pipeline',pipeline),('release',release)]:app.add_typer(group,name=key)
    @project.command('profiles')
    def profiles():show(PROFILES)
    @project.command('inspect')
    def inspect(root:Path=typer.Option(Path('.'),'--root')):
        from .workspace import inventory
        show(inventory(root.resolve()))
    @project.command('configure')
    @single_writer
    def config(file:Path=typer.Option(...,'--file'),root:Path=typer.Option(Path('.'),'--root')):
        result=configure(root.resolve(),load_yaml(file));show({'configured':True,'gaps':gaps(result)})
    @project.command('setup')
    @single_writer
    def setup(root:Path=typer.Option(Path('.'),'--root')):
        root=root.resolve();show({'profiles':PROFILES})
        count=typer.prompt('Number of components',default=1,type=int)
        if not 1<=count<=100:raise typer.BadParameter('Choose 1..100 components')
        components=[]
        for n in range(count):
            ident=typer.prompt('Component ID',default='app' if count==1 else 'app'+str(n+1))
            path=typer.prompt('Component directory',default='.')
            kind=typer.prompt('Project kind',default='custom')
            if kind not in PROFILES:raise typer.BadParameter('Unknown project kind')
            checks={};waivers={}
            for name in PROFILES[kind]:
                text=typer.prompt(f'{ident}: {name} command (or waive: reason)')
                if text.startswith('waive:'):waivers[name]=text[6:].strip()
                else:checks[name]={'argv':shlex.split(text)}
            deps=typer.prompt('Depends on component IDs (comma-separated)',default='')
            components.append({'id':ident,'path':path,'kind':kind,'checks':checks,'waivers':waivers,'depends_on':[x.strip() for x in deps.split(',') if x.strip()]})
        provider=typer.prompt('Repository provider (local/github)',default='local')
        policy={'provider':provider,'base_branch':typer.prompt('Integration branch',default='main')}
        if provider=='github':policy['repository']=typer.prompt('GitHub owner/repository')
        policy['auto_commit']=typer.confirm('Allow lifecycle commits from a clean baseline?',default=False)
        policy['allow_push']=typer.confirm('Allow PR publication?',default=False)
        policy['allow_merge']=typer.confirm('Allow policy-checked merge?',default=False)
        configured=configure(root,{'components':components,'repo':policy})
        show({'configured':True,'gaps':gaps(configured),'next':'Review builds/environments, commit baseline and create an execution branch'})
    @project.command('check')
    @single_writer
    def check(root:Path=typer.Option(Path('.'),'--root')):
        result=run_checks(root.resolve());show(result)
        if not result['passed']:raise typer.Exit(2)
    @project.command('readiness')
    def readiness(root:Path=typer.Option(Path('.'),'--root')):
        root=root.resolve();cfg=load_workspace(root)
        result={'gaps':gaps(cfg),'checks_current':quality_current(root),'branch':branch(root),'provider':cfg.repo.provider,'environments':list(cfg.environments)}
        show(result)
        if result['gaps'] or not result['checks_current']:raise typer.Exit(2)
    @project.command('portfolio-check')
    def portfolio(file:Path=typer.Option(...,'--file')):
        from .portfolio import check
        result=check(file.resolve());show(result)
        if not result['passed']:raise typer.Exit(2)
    @repo.command('scaffold')
    @single_writer
    def scaffold(owner:str=typer.Option(None,'--owner'),root:Path=typer.Option(Path('.'),'--root')):
        from .repository_assets import scaffold
        show(scaffold(root.resolve(),owner))
    @repo.command('audit-host')
    def audit_host(root:Path=typer.Option(Path('.'),'--root')):
        from .repository_assets import audit_host
        result=audit_host(root.resolve());show(result)
        if not result['verified']:raise typer.Exit(2)
    @repo.command('branch')
    @single_writer
    def new_branch(name:str,root:Path=typer.Option(Path('.'),'--root'),worktree:Path=typer.Option(None,'--worktree')):
        show(create_branch(root.resolve(),name,worktree))
    @repo.command('pr')
    @single_writer
    def pr(title:str=typer.Option(...,'--title'),body:Path=typer.Option(...,'--body-file'),root:Path=typer.Option(Path('.'),'--root')):
        show(Provider(root.resolve()).open(title,body.read_text()))
    @repo.command('pr-status')
    def pr_status(identifier:str,root:Path=typer.Option(Path('.'),'--root')):show(Provider(root.resolve()).view(identifier))
    @repo.command('merge')
    @single_writer
    def merge(identifier:str,root:Path=typer.Option(Path('.'),'--root')):show(Provider(root.resolve()).merge(identifier))
    @pipeline.command('export')
    @single_writer
    def export(provider:str=typer.Option('github','--provider'),wheel:Path=typer.Option(None,'--wheel'),update_generated:bool=typer.Option(False,'--update-generated'),root:Path=typer.Option(Path('.'),'--root')):
        show(pipelines.export(root.resolve(),provider,wheel,update_generated))
    @release.command('build')
    @single_writer
    def build(version:str,root:Path=typer.Option(Path('.'),'--root')):show(releases.build(root.resolve(),version))
    @release.command('deploy')
    @single_writer
    def deploy(version:str,environment:str,approve:bool=typer.Option(False,'--approve'),root:Path=typer.Option(Path('.'),'--root')):
        result=releases.deploy(root.resolve(),version,environment,approve);show(result)
        if result['status']!='succeeded':raise typer.Exit(2)
    @release.command('rollback')
    @single_writer
    def rollback(version:str,environment:str,approve:bool=typer.Option(False,'--approve'),root:Path=typer.Option(Path('.'),'--root')):
        result=releases.deploy(root.resolve(),version,environment,approve,rollback=True);show(result)
        if result['status']!='succeeded':raise typer.Exit(2)
    @release.command('reconcile')
    @single_writer
    def reconcile(environment:str,outcome:str=typer.Option(...,'--outcome'),note:str=typer.Option(...,'--note'),root:Path=typer.Option(Path('.'),'--root')):
        show(releases.reconcile(root.resolve(),environment,outcome,note))
    @app.command('lifecycle')
    def lifecycle(version:str=typer.Option(None,'--version'),environment:str=typer.Option(None,'--environment'),approve:bool=typer.Option(False,'--approve'),root:Path=typer.Option(Path('.'),'--root')):
        from .lifecycle import advance
        result=advance(root.resolve(),version,environment,approve);show(result)
        if result['stage'] in {'verify','release_verify','deployment_unknown'}:raise typer.Exit(2)
    recovery=typer.Typer(help='Checkpoint and restore canonical state.')
    app.add_typer(recovery,name='recovery')
    @recovery.command('checkpoint')
    @single_writer
    def save_checkpoint(root:Path=typer.Option(Path('.'),'--root')):
        from .recovery import checkpoint
        show(checkpoint(root.resolve()))
    @recovery.command('restore')
    @single_writer
    def restore_checkpoint(identifier:str,root:Path=typer.Option(Path('.'),'--root')):
        from .recovery import restore
        show(restore(root.resolve(),identifier))

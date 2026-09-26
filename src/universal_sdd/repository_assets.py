"""Optional enterprise repository starters; never overwrite existing files."""
import json
import re
from pathlib import Path
from urllib.parse import quote
from .storage import atomic_write
from .workspace import load_workspace
from .delivery import Provider

def scaffold(root:Path,owner:str|None=None):
    if owner and not re.fullmatch(r'@[A-Za-z0-9][A-Za-z0-9_-]*(/[A-Za-z0-9][A-Za-z0-9_-]*)?',owner):raise ValueError('Supply real @user or @organization/team')
    files={
      'CONTRIBUTING.md':'# Contributing\n\nRead [project documentation](.sdd/docs/README.md) and [change history](.sdd/CHANGELOG.md). Work on short-lived branches, link tasks/specifications, run project and documentation checks, and request owner review. Fill in actual setup/ownership/escalation procedures here.\n',
      'SECURITY.md':'# Security\n\nConfigure a private vulnerability reporting channel, supported versions and response owner. Do not post credentials or private vulnerabilities in public issues. See .sdd/docs/SECURITY.md for design context; this starter is not certification.\n',
      'SUPPORT.md':'# Support\n\nConfigure support channels, owner/on-call escalation and supported versions. Operational incidents follow .sdd/docs/OPERATIONS.md.\n',
      '.github/pull_request_template.md':'## Why and scope\n\nRequirement/specification/task IDs and user-visible result.\n\n## Evidence and review\n\nChecks and tests; security, migration, compatibility and accessibility impact; design and human changelog changes.\n\n## Release\n\nRollout, monitoring, recovery/rollback, owner and risks.\n',
      '.github/ISSUE_TEMPLATE/bug_report.md':'---\nname: Bug report\nabout: Reproducible defect\n---\n\nExpected/actual behavior, reproducer, affected version, redacted evidence and impact. Do not include credentials.\n',
      '.github/ISSUE_TEMPLATE/feature_request.md':'---\nname: Feature request\nabout: Scoped change\n---\n\nUser problem, outcome, acceptance criteria, compatibility/data/operations impact and owner.\n',
    }
    if owner:files['.github/CODEOWNERS']=f'# Enable required owner review in host policy.\n* {owner}\n'
    made=[];preserved=[]
    for name,body in files.items():
        target=root/name
        if target.exists():preserved.append(name)
        else:atomic_write(target,body);made.append(name)
    return {'created':made,'preserved':preserved,'owner_configured':bool(owner),'remaining':'Complete real ownership, contacts and hosting branch rules'}

def audit_host(root:Path):
    cfg=load_workspace(root)
    if cfg.repo.provider!='github':return {'verified':False,'reason':'Read-only native audit supports GitHub classic branch protection only'}
    try: data=json.loads(Provider(root).gh('api',f'repos/{cfg.repo.repository}/branches/{quote(cfg.repo.base_branch,safe="")}/protection'))
    except RuntimeError as exc:return {'verified':False,'reason':'Cannot read protection; inspect rulesets and permission: '+str(exc)}
    reviews=data.get('required_pull_request_reviews') or {};checks=data.get('required_status_checks') or {}
    names=set(checks.get('contexts',[]))|{x.get('context') for x in checks.get('checks',[])}
    findings=[]
    if cfg.repo.require_review:
        if reviews.get('required_approving_review_count',0)<1:findings.append('Required approval missing')
        if not reviews.get('dismiss_stale_reviews'):findings.append('Stale approval dismissal missing')
    findings.extend('Required host check missing: '+n for n in cfg.repo.required_checks if n not in names)
    if not checks.get('strict'):findings.append('Up-to-date requirement missing; inspect merge queue alternative')
    if (data.get('allow_force_pushes') or {}).get('enabled'):findings.append('Force push enabled')
    return {'verified':not findings,'scope':'Classic branch protection only; rulesets, bypass actors and environments need separate host review','findings':findings}

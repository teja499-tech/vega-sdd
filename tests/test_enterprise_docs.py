import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner
from universal_sdd.cli import app
from universal_sdd.documentation import CONTRACT, render_docs, check_docs
from universal_sdd.history import link_commit, snapshot_specs, render_history
from universal_sdd.journal import Journal
from universal_sdd.models import SpecBundle, DesignDocument
from universal_sdd.storage import SDDPaths, load_yaml, dump_yaml

runner = CliRunner()

@pytest.fixture
def project(demo_repo):
    result = runner.invoke(app, ['init', '--root', str(demo_repo), '--agent', 'mock', '--yes', '--project-kind', 'new'])
    assert result.exit_code == 0, (result.output, result.exception)
    return SDDPaths(demo_repo)


def complete(paths):
    bundle = SpecBundle.model_validate(load_yaml(paths.spec_bundle_file))
    # Structural fixture, intentionally not a semantic design quality test.
    bundle.design_documents = {key: DesignDocument(status='documented', summary='Fixture description', sources=['PRD.md'], sections={h:'Fixture content sufficiently populated for structural section validation.' for h in headings}) for key, headings in CONTRACT.items()}
    dump_yaml(paths.spec_bundle_file, bundle)
    return bundle


def test_old_bundle_visible_gaps_and_new_scope(project):
    assert (project.sdd/'docs/HLD.md').exists()
    assert 'INCOMPLETE' in (project.sdd/'docs/DATABASE_DESIGN.md').read_text()
    assert 'Not applicable' in (project.sdd/'docs/EXISTING_SYSTEM.md').read_text()
    assert runner.invoke(app, ['docs', 'check', '--root', str(project.root)]).exit_code == 2


def test_brownfield_requires_as_is_evidence(project):
    data = load_yaml(project.config_file); data['project_kind'] = 'existing'; dump_yaml(project.config_file, data)
    render_docs(project)
    assert any('EXISTING_SYSTEM' in x for x in check_docs(project))


def test_complete_docs_and_stale_source(project):
    bundle = complete(project); assert render_docs(project) == []
    assert check_docs(project) == []
    bundle.architecture_summary += ' Updated target'
    dump_yaml(project.spec_bundle_file, bundle)
    assert any('stale' in x for x in check_docs(project))


def test_manual_edits_and_existing_readme_preserved(project):
    p = project.sdd/'docs/HLD.md'; p.write_text('Human design: preserve this exactly')
    readme = project.root/'README.md'; readme.write_text('Existing enterprise README')
    assert any('manual edits' in x for x in render_docs(project))
    assert p.read_text() == 'Human design: preserve this exactly'
    assert readme.read_text() == 'Existing enterprise README'


def test_applicability_needs_reason(project):
    bundle = complete(project)
    bundle.design_documents['DATABASE_DESIGN'] = DesignDocument(status='not_applicable')
    dump_yaml(project.spec_bundle_file, bundle); render_docs(project)
    assert any('applicability' in x for x in check_docs(project))
    bundle.design_documents['DATABASE_DESIGN'].not_applicable_reason = 'Stateless calculator with no persistent storage in approved scope.'
    dump_yaml(project.spec_bundle_file, bundle); render_docs(project)
    assert check_docs(project) == []


def test_spec_history_transition_and_diff(project):
    first = snapshot_specs(project)
    bundle = load_yaml(project.spec_bundle_file); original = dict(bundle)
    bundle['architecture_summary'] = 'New approved architecture'
    dump_yaml(project.spec_bundle_file, bundle); second = snapshot_specs(project)
    dump_yaml(project.spec_bundle_file, original); third = snapshot_specs(project)
    assert first == third and first != second
    index = load_yaml(project.state/'spec-history.yaml')
    assert len(index) == 3
    assert 'New approved architecture' in (project.sdd/'history/specs/000002.diff').read_text()
    snapshot_specs(project); assert len(load_yaml(project.state/'spec-history.yaml')) == 3


def git_repo(paths):
    def run(*args):
        return subprocess.check_output(['git', *args], cwd=paths.root, text=True).strip()
    run('init', '-q'); run('config', 'user.email', 'fixture@example.test'); run('config', 'user.name', 'Test Author')
    (paths.root/'app.py').write_text('print("example")\n')
    run('add', 'app.py'); run('commit', '-qm', 'Implement notes task')
    return run, run('rev-parse', 'HEAD')


def task_id(paths):
    return load_yaml(paths.features_file)[0]['tasks'][0]['id']


def test_real_commit_link_idempotent_with_details(project):
    run, sha = git_repo(project)
    result = runner.invoke(app, ['link-commit', task_id(project), '--commit', sha[:9], '--summary', 'Implement notes workflow', '--root', str(project.root)])
    assert result.exit_code == 0, (result.output, result.exception)
    link_commit(project, task_id(project), sha, 'Implement notes workflow')
    links = load_yaml(project.state/'commit-links.yaml'); assert len(links) == 1
    assert links[0]['files'] == ['app.py'] and links[0]['author'] == 'Test Author'
    assert sha in (project.sdd/'CHANGELOG.md').read_text()


@pytest.mark.parametrize('bad', ['--help', 'HEAD', 'f'*40, 'abc'])
def test_invalid_commit_rejected(project, bad):
    git_repo(project)
    with pytest.raises(ValueError): link_commit(project, task_id(project), bad, 'Change')


def test_unknown_task_rejected(project):
    _, sha = git_repo(project)
    with pytest.raises(ValueError): link_commit(project, 'TASK-UNKNOWN', sha, 'Change')


def test_unreachable_commit_rejected(project):
    run, sha = git_repo(project)
    run('checkout', '-qb', 'other'); (project.root/'app.py').write_text('changed')
    run('commit', '-qam', 'other work'); other = run('rev-parse', 'HEAD')
    run('checkout', '--detach', sha)
    with pytest.raises(ValueError): link_commit(project, task_id(project), other, 'Not on current branch')


def test_history_pins_task_intent_and_unlinked_state(project):
    Journal(project.event_log).append('task_verified', task=task_id(project), evidence='VERIFY-001')
    features = load_yaml(project.features_file); title = features[0]['tasks'][0]['title']
    features[0]['tasks'][0]['title'] = 'Changed title later'; dump_yaml(project.features_file, features)
    render_history(project); text = (project.sdd/'CHANGELOG.md').read_text()
    assert title in text and 'VERIFY-001' in text and 'not linked' in text


def test_refresh_readonly_agent_enrichment(project, monkeypatch):
    bundle = complete(project)
    docs = {k:v.model_dump() for k,v in bundle.design_documents.items()}
    before = load_yaml(project.features_file)
    def run(prompt, **kwargs):
        assert kwargs['writable'] is False
        assert 'Observed current behavior' in prompt
        return SimpleNamespace(success=True, text=json.dumps(docs))
    monkeypatch.setattr('universal_sdd.cli.get_adapter', lambda *a: SimpleNamespace(run=run))
    result = runner.invoke(app, ['docs','refresh','--enrich','--root',str(project.root)])
    assert result.exit_code == 0, (result.output, result.exception)
    assert check_docs(project) == [] and load_yaml(project.features_file) == before


def test_bad_enrichment_keeps_spec(project, monkeypatch):
    before = project.spec_bundle_file.read_bytes()
    monkeypatch.setattr('universal_sdd.cli.get_adapter', lambda *a: SimpleNamespace(run=lambda *a,**k: SimpleNamespace(success=True,text='{}')))
    result = runner.invoke(app, ['docs','refresh','--enrich','--root',str(project.root)])
    assert result.exit_code != 0 and project.spec_bundle_file.read_bytes() == before


def test_task_completion_refreshes_traceability(project):
    result = runner.invoke(app, ['start','--root',str(project.root)])
    assert result.exit_code == 0, result.output
    assert '| verified |' in (project.sdd/'docs/TRACEABILITY.md').read_text()
    assert 'task verified' in (project.sdd/'CHANGELOG.md').read_text()


def test_automatic_trailer_link_excludes_unrelated_commits(project):
    run, base = git_repo(project)
    Journal(project.event_log).append('task_started', task=task_id(project))
    (project.root/'app.py').write_text('authorized change')
    run('commit','-qam', 'Notes fix\n\nSDD-Task: ' + task_id(project))
    correct = run('rev-parse','HEAD')
    (project.root/'other.txt').write_text('unrelated change'); run('add','other.txt'); run('commit','-qm','Unrelated work')
    Journal(project.event_log).append('task_verified',task=task_id(project),evidence='TEST-001')
    links = load_yaml(project.state/'commit-links.yaml')
    assert [r['sha'] for r in links] == [correct]


def test_root_enterprise_files_not_overwritten(project):
    for name in ['SECURITY.md','CONTRIBUTING.md','CHANGELOG.md','.github/pull_request_template.md']:
        file = project.root/name; file.parent.mkdir(parents=True,exist_ok=True); file.write_text('Owned enterprise policy')
    render_docs(project)
    for name in ['SECURITY.md','CONTRIBUTING.md','CHANGELOG.md','.github/pull_request_template.md']:
        assert (project.root/name).read_text() == 'Owned enterprise policy'

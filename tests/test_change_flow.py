from pathlib import Path

from typer.testing import CliRunner

from universal_sdd.cli import app
from universal_sdd.models import ChangeRequest, Feature
from universal_sdd.storage import SDDPaths, dump_yaml, load_yaml

runner = CliRunner()


def test_implementation_defect_creates_repair_task(demo_repo: Path):
    result = runner.invoke(app, ["init", "--root", str(demo_repo), "--agent", "mock", "--project-kind", "new", "--yes"])
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["change", "The current core implementation violates its acceptance criteria", "--root", str(demo_repo)])
    assert result.exit_code == 0, result.output
    features = [Feature.model_validate(x) for x in load_yaml(SDDPaths(demo_repo).features_file)]
    ids = [t.id for t in features[0].tasks]
    assert any("-R" in x for x in ids)


def test_approved_requirement_change_reconciles_and_invalidates(demo_repo: Path):
    from universal_sdd.models import ChangeRequest, ItemStatus
    from universal_sdd.orchestrator import apply_change

    result = runner.invoke(app, ["init", "--root", str(demo_repo), "--agent", "mock", "--project-kind", "new", "--yes"])
    assert result.exit_code == 0
    cr = ChangeRequest(
        id="CR-TEST01",
        description="Change the approved core requirement",
        classification="requirement_change",
        affected_requirements=["REQ-001"],
        affected_features=["F001"],
        affected_tasks=["TASK-F001-001"],
        proposed_changes=["Update core behavior"],
        requires_approval=True,
        approved=True,
        status="approved",
    )
    apply_change(demo_repo, cr)
    features = [Feature.model_validate(x) for x in load_yaml(SDDPaths(demo_repo).features_file)]
    assert features[0].tasks[0].status == ItemStatus.invalidated


def test_cli_approve_id_applies_exact_stored_change_without_reanalysis(demo_repo: Path, monkeypatch):
    paths = SDDPaths(demo_repo)
    paths.ensure()
    cr = ChangeRequest(
        id="CR-EXACT1",
        description="Apply the exact reviewed requirement change",
        classification="requirement_change",
        affected_requirements=["REQ-001"],
        proposed_changes=["Clarify the approved core workflow"],
        requires_approval=True,
    )
    dump_yaml(paths.changes / f"{cr.id}.yaml", cr)
    captured = {}

    def fail_analysis(*args, **kwargs):
        raise AssertionError("approval must not re-run change analysis")

    def capture_apply(root, approved, **kwargs):
        captured["change"] = approved.model_copy(deep=True)
        approved.status = "applied"
        return approved

    monkeypatch.setattr("universal_sdd.cli.analyze_change", fail_analysis)
    monkeypatch.setattr("universal_sdd.cli.apply_change", capture_apply)
    result = runner.invoke(app, ["change", "--approve-id", cr.id, "--root", str(demo_repo)])

    assert result.exit_code == 0, result.output
    assert captured["change"].id == cr.id
    assert captured["change"].approved is True
    assert captured["change"].affected_requirements == ["REQ-001"]


def test_cli_rejects_unbound_approve_flag(demo_repo: Path):
    result = runner.invoke(
        app,
        ["change", "Rewrite the requirement", "--approve", "--root", str(demo_repo)],
    )
    assert result.exit_code == 2
    assert "--approve-id" in result.output


def test_intervene_prints_exact_stored_change_approval(demo_repo: Path, monkeypatch):
    cr = ChangeRequest(
        id="CR-CHAT01",
        description="Change approved behavior",
        classification="requirement_change",
        affected_requirements=["REQ-001"],
        requires_approval=True,
    )
    monkeypatch.setattr("universal_sdd.cli.analyze_change", lambda root, description: cr)
    result = runner.invoke(
        app,
        ["intervene", "--root", str(demo_repo)],
        input="change: Change approved behavior\nexit\n",
    )
    assert result.exit_code == 0, result.output
    assert "sdd change --approve-id CR-CHAT01" in result.output

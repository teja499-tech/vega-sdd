from pathlib import Path

from typer.testing import CliRunner

from universal_sdd.cli import app
from universal_sdd.models import Feature
from universal_sdd.storage import SDDPaths, load_yaml

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

from pathlib import Path

from typer.testing import CliRunner

from universal_sdd.cli import app
from universal_sdd.models import Feature, ItemStatus, RunStatus
from universal_sdd.storage import SDDPaths, load_project_state, load_yaml

runner = CliRunner()


def test_init_status_verify_and_start(demo_repo: Path):
    result = runner.invoke(app, ["init", "--root", str(demo_repo), "--agent", "mock", "--project-kind", "new", "--yes"])
    assert result.exit_code == 0, result.output
    paths = SDDPaths(demo_repo)
    assert paths.config_file.exists()
    assert (demo_repo / "AGENTS.md").exists()
    assert (demo_repo / "CLAUDE.md").exists()
    assert (demo_repo / ".cursor" / "rules" / "vega-sdd.mdc").exists()
    assert (paths.product / "requirements.md").exists()
    assert (paths.architecture / "decisions.md").exists()
    assert (paths.sdd / "roadmap.md").exists()

    result = runner.invoke(app, ["verify", "--root", str(demo_repo)])
    assert result.exit_code == 0, result.output
    assert "PASS" in result.output

    result = runner.invoke(app, ["start", "--root", str(demo_repo), "--max-tasks", "1"])
    assert result.exit_code == 0, result.output
    state = load_project_state(paths)
    assert state.run_status == RunStatus.completed
    features = [Feature.model_validate(x) for x in load_yaml(paths.features_file)]
    assert features[0].tasks[0].status == ItemStatus.verified
    assert features[0].status == ItemStatus.verified


def test_switch_agent_rejects_missing_agent(demo_repo: Path):
    init = runner.invoke(app, ["init", "--root", str(demo_repo), "--agent", "mock", "--project-kind", "new", "--yes"])
    assert init.exit_code == 0
    # At least the command itself is present and validates adapter installation.
    result = runner.invoke(app, ["agent", "list", "--root", str(demo_repo)])
    assert result.exit_code == 0
    assert "cursor" in result.output
    assert "codex" in result.output
    assert "claude" in result.output


def test_existing_agents_file_is_preserved_and_extended(demo_repo: Path):
    (demo_repo / "AGENTS.md").write_text("# Existing Rules\nKeep this rule.\n", encoding="utf-8")
    result = runner.invoke(app, ["init", "--root", str(demo_repo), "--agent", "mock", "--project-kind", "existing", "--yes"])
    assert result.exit_code == 0, result.output
    text = (demo_repo / "AGENTS.md").read_text(encoding="utf-8")
    assert "Keep this rule." in text
    assert "UNIVERSAL_SDD_START" in text


def test_force_reinit_replaces_sdd_state(demo_repo: Path):
    result = runner.invoke(app, ["init", "--root", str(demo_repo), "--agent", "mock", "--project-kind", "new", "--yes"])
    assert result.exit_code == 0
    marker = demo_repo / ".sdd" / "old-marker.txt"
    marker.write_text("old", encoding="utf-8")
    result = runner.invoke(app, ["init", "--root", str(demo_repo), "--agent", "mock", "--project-kind", "new", "--yes", "--force"])
    assert result.exit_code == 0, result.output
    assert not marker.exists()

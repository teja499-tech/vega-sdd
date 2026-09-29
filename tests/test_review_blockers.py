import json

import pytest
from typer.testing import CliRunner

from universal_sdd.adapters.base import UNRESTRICTED_ENV
from universal_sdd.adapters.copilot import CopilotAdapter
from universal_sdd.adapters.cursor import CursorAdapter
from universal_sdd.adapters.gemini import GeminiAdapter
from universal_sdd.cli import app
from universal_sdd.mcp_server import _call
from universal_sdd.models import AgentName, SDDConfig, Task
from universal_sdd.storage import SDDPaths, load_project_state
from universal_sdd.task_checks import safe_repo_paths, scoped_test_argv


@pytest.fixture
def initialized(demo_repo):
    result = CliRunner().invoke(app, ["init", "--root", str(demo_repo), "--agent", "mock", "--yes"])
    assert result.exit_code == 0, result.output
    return SDDPaths(demo_repo)


def test_check_paths_reject_shell_metacharacters(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_ok.py").write_text("ok\n", encoding="utf-8")
    rejected = safe_repo_paths(
        tmp_path,
        [
            "tests/test_ok.py; rm -rf /",
            "$(reboot)",
            "`id`",
            "../../etc/passwd",
            "/tmp/x.py",
        ],
    )
    assert rejected == []
    assert safe_repo_paths(tmp_path, ["tests/test_ok.py"]) == ["tests/test_ok.py"]
    cfg = SDDConfig(project_name="p", primary_agent=AgentName.mock, test_command="pytest -q")
    poisoned = Task(id="T", feature_id="F", title="t", description="d", check_paths=["tests/x.py; id"])
    assert scoped_test_argv(tmp_path, cfg, poisoned) == ["pytest", "-q"]
    ok = Task(id="T", feature_id="F", title="t", description="d", check_paths=["tests/test_ok.py"])
    assert scoped_test_argv(tmp_path, cfg, ok) == ["pytest", "-q", "tests/test_ok.py"]


def test_unrestricted_agent_flags_are_opt_in(tmp_path, monkeypatch):
    monkeypatch.delenv(UNRESTRICTED_ENV, raising=False)
    assert "--force" not in CursorAdapter(tmp_path).build_command("hello", writable=True)
    assert "--yolo" not in GeminiAdapter(tmp_path).build_command("hello", writable=True)
    assert "--allow-all" not in CopilotAdapter(tmp_path).build_command("hello", writable=True)
    monkeypatch.setenv(UNRESTRICTED_ENV, "1")
    assert "--force" in CursorAdapter(tmp_path).build_command("hello", writable=True, mode="agent")
    assert "--yolo" in GeminiAdapter(tmp_path).build_command("hello", writable=True)
    assert "--allow-all" in CopilotAdapter(tmp_path).build_command("hello", writable=True)


def test_failed_init_is_not_initialized_and_resumes(demo_repo, monkeypatch):
    from universal_sdd.artifacts import write_spec_bundle as real_write

    calls = {"n": 0}

    def boom(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("Specification bundle is too thin")
        return real_write(*args, **kwargs)

    monkeypatch.setattr("universal_sdd.cli.write_spec_bundle", boom)
    runner = CliRunner()
    first = runner.invoke(app, ["init", "--root", str(demo_repo), "--agent", "mock", "--yes"])
    assert first.exit_code != 0
    paths = SDDPaths(demo_repo)
    state = load_project_state(paths)
    assert state.initialized is False
    assert state.run_status.value == "failed"
    second = runner.invoke(app, ["init", "--root", str(demo_repo), "--agent", "mock", "--yes"])
    assert second.exit_code == 0, second.output
    assert load_project_state(paths).initialized is True


def test_mcp_change_cannot_self_approve(initialized, monkeypatch):
    monkeypatch.chdir(initialized.root)
    before = initialized.features_file.read_bytes()
    text = _call("sdd_change", {"description": "Add a weekly digest email", "approve": True})
    data = json.loads(text)
    assert data["applied"] is False
    assert f"sdd change --approve-id {data['id']}" in data["next_step"]
    assert initialized.features_file.read_bytes() == before


def test_generated_readme_does_not_invent_ai_stack(initialized):
    text = (initialized.root / "README.md").read_text()
    lowered = text.lower()
    assert "ollama" not in lowered
    assert "openrouter" not in lowered
    guide = (initialized.sdd / "docs" / "DEVELOPER_GUIDE.md").read_text().lower()
    assert "ollama" not in guide
    assert "openrouter" not in guide


def test_generated_cursor_change_command_uses_exact_approval(initialized):
    command = (initialized.root / ".cursor" / "commands" / "sdd-change.md").read_text()
    assert "sdd change --approve-id CR-..." in command
    assert "Never re-run the request text" in command

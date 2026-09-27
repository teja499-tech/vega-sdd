import json
from pathlib import Path

import pytest
from typer.testing import CliRunner
from universal_sdd.adapters.copilot import CopilotAdapter
from universal_sdd.adapters.gemini import GeminiAdapter
from universal_sdd.cli import app
from universal_sdd.clarifications import Clarification, assert_start_ready, save_clarifications, unresolved_material
from universal_sdd.context_pack import build_context_pack
from universal_sdd.mcp_server import _call, _tools
from universal_sdd.models import SpecBundle, Task
from universal_sdd.project_graph import refresh_graph
from universal_sdd.spec_quality import spec_quality_errors
from universal_sdd.status import load_features
from universal_sdd.storage import SDDPaths
from universal_sdd.task_checks import compact_output, scoped_test_command
from universal_sdd.tokens import estimate_tokens


@pytest.fixture
def initialized(demo_repo):
    result = CliRunner().invoke(app, ["init", "--root", str(demo_repo), "--agent", "mock", "--yes"])
    assert result.exit_code == 0, result.output
    return SDDPaths(demo_repo)


def test_title_only_feature_is_rejected():
    bundle = SpecBundle.model_validate({
        "product": {"name": "X", "summary": "short", "users": [], "capabilities": [], "workflows": [], "constraints": [], "assumptions": [], "open_questions": []},
        "requirements": [{"id": "REQ-1", "title": "T", "statement": "x", "acceptance_criteria": []}],
        "features": [{"id": "F001", "name": "N", "summary": "thin", "requirements": ["REQ-1"], "tasks": [
            {"id": "TASK-F001-001", "feature_id": "F001", "title": "Do it", "description": "Do it", "implements": [], "verification": []}
        ]}],
    })
    errors = spec_quality_errors(bundle)
    assert any("title-only" in e or "thin" in e for e in errors)


def test_context_pack_and_graph(initialized):
    features = load_features(initialized)
    pack = build_context_pack(initialized, features[0].tasks[0], features[0])
    text = pack.render()
    assert "Acceptance criteria" in text
    assert "implement-task" in text
    assert "graphify query" in text
    assert "## Failure modes" not in text
    graph = refresh_graph(initialized)
    corpus = initialized.root / "graphify-corpus" / "sdd-traceability.md"
    assert corpus.exists()
    assert "REQ-001" in corpus.read_text()
    assert graph["installed"] is False
    assert "nodes" not in graph


def test_ask_and_clarify_and_docs_readme(initialized):
    runner = CliRunner()
    asked = runner.invoke(app, ["ask", "What is the approved backend?", "--root", str(initialized.root)])
    assert asked.exit_code == 0, asked.output
    assert "Architect" in asked.output or "PRD" in asked.output or "FastAPI" in asked.output or "current" in asked.output
    listed = runner.invoke(app, ["clarify", "--root", str(initialized.root)])
    assert listed.exit_code == 0
    assert (initialized.root / "README.md").exists()
    assert "setup" in (initialized.root / "README.md").read_text().lower()
    assert (initialized.sdd / "docs" / "DEVELOPER_GUIDE.md").exists()
    assert (initialized.root / ".agents" / "skills" / "api-design" / "SKILL.md").exists()
    assert "Required output" in (initialized.root / ".agents" / "skills" / "api-design" / "SKILL.md").read_text()
    assert (initialized.root / ".cursor" / "commands" / "sdd-ask.md").exists()


def test_start_blocked_by_deferred_question(initialized):
    save_clarifications(initialized, [Clarification(id="Q1", question="Which model host?", status="deferred")])
    with pytest.raises(RuntimeError, match="clarifications"):
        assert_start_ready(initialized)
    assert unresolved_material(initialized)
    runner = CliRunner()
    blocked = runner.invoke(app, ["start", "--root", str(initialized.root)])
    assert blocked.exit_code != 0
    accepted = runner.invoke(app, ["start", "--accept-deferred", "--root", str(initialized.root)])
    assert accepted.exit_code == 0, accepted.output


def test_compact_output_and_scoped_pytest():
    dots = compact_output("." * 4000 + "\nOK")
    assert "4000" in dots or len(dots) < 4000
    failed = compact_output(".....\nFAILED tests/test_x.py::test_one\nAssertionError: boom\n")
    assert "FAILED" in failed
    task = Task(id="T", feature_id="F", title="t", description="d", check_paths=["tests/test_x.py"])
    from universal_sdd.models import SDDConfig, AgentName, ProjectKind
    cfg = SDDConfig(project_name="p", primary_agent=AgentName.mock, test_command="pytest -q")
    assert "tests/test_x.py" in scoped_test_command(cfg, task)


def test_skill_runbook_is_operational_and_not_inlined():
    from universal_sdd.skill_library import SKILLS, skill_summary
    implement = SKILLS["implement-task/SKILL.md"]
    review = SKILLS["review-task/SKILL.md"]
    assert "## Directory map" in implement
    assert "## Failure modes" in implement
    assert "graphify query" in implement
    assert "## Failure modes" in review
    assert "violates_ac" in review
    assert len(implement.splitlines()) > 80
    assert len(review.splitlines()) > 70
    assert "Directory map" not in skill_summary("implement-task")


def test_compression_records_savings_without_stopping(initialized):
    from universal_sdd.compress import compress_for_prompt
    from universal_sdd.tokens import savings_summary
    text = "FAILED tests/test_notes.py::test_empty\n" + ("noise line\n" * 40)
    out = compress_for_prompt(initialized, text, label="check")
    assert "FAILED" in out or out == text or "Full original" in out
    summary = savings_summary(initialized)
    assert summary["events"] >= 1
    originals = [p for p in (initialized.runtime / "originals").glob("*.txt") if p.name != "index.txt"]
    assert originals and any("FAILED" in p.read_text() for p in originals)


def test_graphify_query_uses_cli_when_present(initialized, monkeypatch):
    from universal_sdd.graphify_index import query_knowledge_graph, refresh_knowledge_graph
    calls = []

    def fake_run(root, args, timeout):
        calls.append(args)
        if args[:1] == ["query"]:
            return 0, "app/notes.py tests/test_notes.py"
        return 0, "built"

    monkeypatch.setattr("universal_sdd.graphify_index.graphify_installed", lambda: True)
    monkeypatch.setattr("universal_sdd.graphify_index.graph_json", lambda root: initialized.root / "graphify-out" / "graph.json")
    (initialized.root / "graphify-out").mkdir()
    (initialized.root / "graphify-out" / "graph.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr("universal_sdd.graphify_index.run_graphify", fake_run)
    assert "notes.py" in query_knowledge_graph(initialized.root, "notes")
    refresh_knowledge_graph(initialized)
    assert calls[-1][0] == "update"
    assert calls[-1][1] == str(initialized.root)


def test_token_estimate_and_gemini_copilot_commands(tmp_path: Path):
    assert estimate_tokens("abcd") == 1
    gem = GeminiAdapter(tmp_path).build_command("hello", writable=True)
    assert gem[:2] == ["gemini", "-p"]
    assert "--yolo" not in gem
    assert "--sandbox" in gem
    assert "--sandbox" in GeminiAdapter(tmp_path).build_command("hello", writable=False)
    cop = CopilotAdapter(tmp_path).build_command("hello", writable=True)
    assert cop[:2] == ["copilot", "-p"]
    assert "--allow-all" not in cop
    assert "--silent" in cop


def test_mcp_tool_catalog():
    names = {tool["name"] for tool in _tools()}
    assert names == {"sdd_ask", "sdd_status", "sdd_change"}


def test_mcp_ask_uses_project(initialized, monkeypatch):
    monkeypatch.chdir(initialized.root)
    text = _call("sdd_ask", {"question": "What is in scope?"})
    assert text
    status = _call("sdd_status", {})
    assert "verified=" in status

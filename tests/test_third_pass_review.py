import json
import sys
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from universal_sdd.agent_guard import persist_task_baseline, workspace_snapshot
from universal_sdd.artifacts import write_architecture
from universal_sdd.clarifications import (
    Clarification,
    accept_deferred_defaults,
    answer_clarification,
    load_decisions,
    record_architecture_decisions,
    save_clarifications,
)
from universal_sdd.cli import app
from universal_sdd.context_pack import ContextPack, build_context_pack, rebuild_review_pack
from universal_sdd.graphify_index import query_knowledge_graph, write_trace_corpus
from universal_sdd.models import AgentCapabilities, AgentResult, DecisionStatus, ItemStatus, RunStatus, SpecBundle
from universal_sdd.orchestrator import apply_change, run_development
from universal_sdd.status import load_features
from universal_sdd.storage import SDDPaths, load_config, load_project_state, load_yaml, save_config, save_project_state


@pytest.fixture
def initialized(demo_repo):
    result = CliRunner().invoke(app, ["init", "--root", str(demo_repo), "--agent", "mock", "--yes"])
    assert result.exit_code == 0, result.output
    return SDDPaths(demo_repo)


def test_placeholder_answer_does_not_resolve_architecture(initialized):
    decisions = load_decisions(initialized)
    decisions[0].status = DecisionStatus.deferred
    decisions[0].selected = None
    write_architecture(initialized, decisions)
    record_architecture_decisions(initialized, decisions)
    with pytest.raises(ValueError, match="placeholder"):
        answer_clarification(initialized, "ARCH-001", "Deferred")
    after = load_decisions(initialized)
    assert after[0].selected is None
    assert after[0].status == DecisionStatus.deferred


def test_accept_deferred_is_atomic_across_decisions(initialized):
    decisions = load_decisions(initialized)
    first = decisions[0]
    first.status = DecisionStatus.deferred
    first.selected = None
    second = first.model_copy(
        update={
            "id": "ARCH-099",
            "question": "Which host?",
            "recommendation": None,
            "options": [],
            "status": DecisionStatus.deferred,
            "selected": None,
        }
    )
    write_architecture(initialized, [first, second])
    record_architecture_decisions(initialized, [first, second])
    with pytest.raises(RuntimeError, match="explicit default"):
        accept_deferred_defaults(initialized)
    after = {d.id: d for d in load_decisions(initialized)}
    assert after["ARCH-001"].status == DecisionStatus.deferred
    assert after["ARCH-001"].selected is None
    assert after["ARCH-099"].status == DecisionStatus.deferred


def test_read_only_restores_source_after_protected_and_git_mutations(initialized):
    from universal_sdd.orchestrator import invoke_agent

    app_file = initialized.root / "app.py"
    app_file.write_text("ORIGINAL = 1\n", encoding="utf-8")
    agents = initialized.root / "AGENTS.md"
    original_agents = agents.read_text(encoding="utf-8")

    class Mutating:
        def capabilities(self):
            return AgentCapabilities(installed=True)

        def interrupt(self):
            return True

        def run(self, prompt, **kwargs):
            agents.write_text("poisoned\n", encoding="utf-8")
            app_file.write_text("MUTATED = 1\n", encoding="utf-8")
            (initialized.root / "staged.txt").write_text("x\n", encoding="utf-8")
            import subprocess
            subprocess.run(["git", "add", "staged.txt"], cwd=initialized.root, check=True, capture_output=True)
            return AgentResult(success=True, text="ok")

    with pytest.raises(RuntimeError, match="protected controller files"):
        invoke_agent(Mutating(), "peek", initialized.root, writable=False, mode="ask")
    assert agents.read_text(encoding="utf-8") == original_agents
    assert app_file.read_text(encoding="utf-8") == "ORIGINAL = 1\n"
    cached = __import__("subprocess").run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=initialized.root,
        capture_output=True,
        text=True,
    )
    assert "staged.txt" not in cached.stdout


def test_review_sees_files_after_crash_recovery(initialized):
    cfg = load_config(initialized)
    cfg.test_command = f'{sys.executable} -c "pass"'
    save_config(initialized, cfg)
    features = load_features(initialized)
    task, feature = features[0].tasks[0], features[0]
    persist_task_baseline(initialized, task.id, workspace_snapshot(initialized.root))
    created = initialized.root / "app" / "crash_created.py"
    created.parent.mkdir(parents=True, exist_ok=True)
    created.write_text("VALUE = 1\n", encoding="utf-8")
    task.status = ItemStatus.implemented
    feature.status = ItemStatus.in_progress
    from universal_sdd.orchestrator import _save_features
    _save_features(initialized, features)
    seen = {}

    class Agent:
        def capabilities(self):
            return AgentCapabilities(installed=True)

        def interrupt(self):
            return True

        def run(self, prompt, **kwargs):
            if "TASK_IMPLEMENTATION" in prompt:
                raise AssertionError("recovery must not re-implement")
            if "TASK_REVIEW_JSON" in prompt:
                seen["review"] = prompt
                return AgentResult(success=True, text=json.dumps({"status": "pass", "findings": [], "summary": "ok"}))
            return AgentResult(success=True, text="done")

    with patch("universal_sdd.orchestrator.get_adapter", return_value=Agent()):
        state = run_development(initialized.root)
    assert state.run_status == RunStatus.completed
    assert "crash_created.py" in seen["review"]


def test_repair_prompt_uses_implement_skill_not_review(initialized):
    cfg = load_config(initialized)
    cfg.test_command = f'{sys.executable} -c "pass"'
    cfg.max_repair_attempts = 1
    save_config(initialized, cfg)
    seen = {}
    reviews = {"n": 0}

    class Agent:
        def capabilities(self):
            return AgentCapabilities(installed=True)

        def interrupt(self):
            return True

        def run(self, prompt, **kwargs):
            if "TASK_IMPLEMENTATION" in prompt:
                return AgentResult(success=True, text="implemented")
            if "TASK_REVIEW_JSON" in prompt:
                reviews["n"] += 1
                if reviews["n"] == 1:
                    return AgentResult(
                        success=True,
                        text=json.dumps({
                            "status": "fail",
                            "findings": [{"severity": "high", "violates_ac": True, "summary": "broken"}],
                            "summary": "fail",
                        }),
                    )
                return AgentResult(success=True, text=json.dumps({"status": "pass", "findings": [], "summary": "ok"}))
            if "repairing a failed SDD review" in prompt:
                seen["repair"] = prompt
                return AgentResult(success=True, text="repaired")
            return AgentResult(success=True, text="done")

    with patch("universal_sdd.orchestrator.get_adapter", return_value=Agent()):
        run_development(initialized.root)
    assert "implement-task" in seen["repair"]
    assert "Load `implement-task`" in seen["repair"]


def test_verify_feature_is_controller_contract(initialized):
    cfg = load_config(initialized)
    cfg.test_command = f'{sys.executable} -c "pass"'
    save_config(initialized, cfg)
    called = {"verify": 0}

    class Agent:
        def capabilities(self):
            return AgentCapabilities(installed=True)

        def interrupt(self):
            return True

        def run(self, prompt, **kwargs):
            if "verify-feature" in prompt and "Load `verify-feature`" in prompt:
                raise AssertionError("verify-feature must not be an agent skill invocation")
            if "TASK_REVIEW_JSON" in prompt:
                return AgentResult(success=True, text=json.dumps({"status": "pass", "findings": [], "summary": "ok"}))
            return AgentResult(success=True, text="implemented")

    real_verify = __import__("universal_sdd.orchestrator", fromlist=["_verify_feature"])._verify_feature

    def wrapped(*args, **kwargs):
        called["verify"] += 1
        return real_verify(*args, **kwargs)

    with patch("universal_sdd.orchestrator.get_adapter", return_value=Agent()):
        with patch("universal_sdd.orchestrator._verify_feature", side_effect=wrapped):
            state = run_development(initialized.root)
    assert called["verify"] >= 1
    assert state.run_status == RunStatus.completed
    events = (initialized.journal / "events.jsonl").read_text(encoding="utf-8")
    assert "verify-feature" in events
    assert "controller" in events


def test_graphify_keeps_corpus_when_code_graph_is_huge(initialized, monkeypatch):
    write_trace_corpus(initialized)
    (initialized.root / "graphify-out").mkdir(exist_ok=True)
    (initialized.root / "graphify-out" / "graph.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr("universal_sdd.graphify_index.graphify_installed", lambda: True)
    monkeypatch.setattr(
        "universal_sdd.graphify_index.run_graphify",
        lambda root, args, timeout: (0, "CODE " * 2000) if args[:1] == ["query"] else (0, "built"),
    )
    text = query_knowledge_graph(initialized.root, "REQ-001")
    assert "REQ-001" in text
    assert "Traceability corpus" in text


def test_apply_change_rolls_back_when_render_fails(initialized):
    original = initialized.spec_bundle_file.read_text(encoding="utf-8")
    decisions = initialized.architecture_decisions_file.read_text(encoding="utf-8")
    bundle = load_yaml(initialized.spec_bundle_file)

    class Reconciler:
        def capabilities(self):
            return AgentCapabilities(installed=True)

        def interrupt(self):
            return True

        def run(self, prompt, **kwargs):
            return AgentResult(success=True, text=json.dumps({"bundle": bundle, "invalidate_tasks": []}))

    from universal_sdd.models import ChangeRequest
    with patch("universal_sdd.orchestrator.get_adapter", return_value=Reconciler()):
        with patch("universal_sdd.documentation.render_docs", side_effect=RuntimeError("render boom")):
            with pytest.raises(RuntimeError, match="render boom"):
                apply_change(
                    initialized.root,
                    ChangeRequest(
                        id="CR-ROLL",
                        description="clarify wording",
                        classification="requirement_change",
                        affected_requirements=["REQ-001"],
                        approved=True,
                    ),
                )
    assert initialized.spec_bundle_file.read_text(encoding="utf-8") == original
    assert initialized.architecture_decisions_file.read_text(encoding="utf-8") == decisions


def test_init_status_matches_ready_state(initialized):
    state = load_project_state(initialized)
    assert state.run_status == RunStatus.ready
    assert "Run status: **ready**" in initialized.status_file.read_text(encoding="utf-8")


def test_copilot_scopes_approved_check_shell(initialized):
    from universal_sdd.adapters.copilot import CopilotAdapter

    cfg = load_config(initialized)
    cfg.test_command = "pytest -q"
    save_config(initialized, cfg)
    cmd = CopilotAdapter(initialized.root).build_command("hello", writable=True)
    assert "--no-ask-user" in cmd
    assert "--allow-all" not in cmd
    tools = [cmd[i + 1] for i, part in enumerate(cmd) if part == "--allow-tool"]
    assert "write" in tools
    assert "shell(pytest)" in tools
    assert "shell" not in tools


def test_review_fails_closed_when_change_set_exceeds_limit(initialized):
    features = load_features(initialized)
    task, feature = features[0].tasks[0], features[0]
    pack = build_context_pack(initialized, task, feature, phase="review")
    changed = [f"app/file_{i}.py" for i in range(20)]
    with pytest.raises(RuntimeError, match="review limit"):
        rebuild_review_pack(initialized, task, feature, changed, pack)


def test_review_render_keeps_every_changed_file(initialized):
    features = load_features(initialized)
    task, feature = features[0].tasks[0], features[0]
    pack = ContextPack(
        task_id=task.id,
        feature_id=feature.id,
        skill="review-task",
        changed_files=[f"app/mod_{i}.py" for i in range(12)],
        spec_excerpt="SPEC " * 4000,
        graph_excerpt="GRAPH " * 4000,
    )
    text = pack.render()
    for name in pack.changed_files:
        assert name in text

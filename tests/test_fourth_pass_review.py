import json
import subprocess
import sys
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from universal_sdd.adapters.copilot import CopilotAdapter, copilot_shell_spec
from universal_sdd.agent_guard import persist_task_baseline, workspace_snapshot
from universal_sdd.artifacts import recover_projection_transaction, write_spec_bundle
from universal_sdd.cli import app
from universal_sdd.graphify_index import query_knowledge_graph, write_trace_corpus
from universal_sdd.models import AgentCapabilities, AgentName, AgentResult, ItemStatus, RunStatus, SpecBundle
from universal_sdd.orchestrator import _feature_evidence_gaps, invoke_agent, run_development
from universal_sdd.status import load_features
from universal_sdd.storage import SDDPaths, load_config, load_yaml, save_config


@pytest.fixture
def initialized(demo_repo):
    result = CliRunner().invoke(app, ["init", "--root", str(demo_repo), "--agent", "mock", "--yes"])
    assert result.exit_code == 0, result.output
    return SDDPaths(demo_repo)


def test_read_only_restore_keeps_owner_staged_index(initialized):
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=initialized.root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=initialized.root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.test"], cwd=initialized.root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=initialized.root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=initialized.root, check=True, capture_output=True)
    owner = initialized.root / "owner-change.txt"
    owner.write_text("mine\n", encoding="utf-8")
    subprocess.run(["git", "add", "owner-change.txt"], cwd=initialized.root, check=True, capture_output=True)

    class Mutating:
        def capabilities(self):
            return AgentCapabilities(installed=True)

        def interrupt(self):
            return True

        def run(self, prompt, **kwargs):
            owner.write_text("stolen\n", encoding="utf-8")
            subprocess.run(["git", "add", "owner-change.txt"], cwd=initialized.root, check=True, capture_output=True)
            return AgentResult(success=True, text="ok")

    with pytest.raises(RuntimeError, match="Git HEAD, branch or index"):
        invoke_agent(Mutating(), "peek", initialized.root, writable=False, mode="ask")
    assert owner.read_text(encoding="utf-8") == "mine\n"
    shown = subprocess.run(
        ["git", "show", ":owner-change.txt"],
        cwd=initialized.root,
        capture_output=True,
        text=True,
        check=True,
    )
    assert shown.stdout == "mine\n"


def test_baseline_survives_failed_verified_save(initialized):
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
    from universal_sdd import orchestrator as orch
    _save_features(initialized, features)

    real_save = orch._save_features

    def boom(paths, rows):
        if any(t.status == ItemStatus.verified for f in rows for t in f.tasks):
            raise RuntimeError("save boom")
        return real_save(paths, rows)

    class Agent:
        def capabilities(self):
            return AgentCapabilities(installed=True)

        def interrupt(self):
            return True

        def run(self, prompt, **kwargs):
            if "TASK_REVIEW_JSON" in prompt:
                return AgentResult(success=True, text=json.dumps({"status": "pass", "findings": [], "summary": "ok"}))
            return AgentResult(success=True, text="implemented")

    with patch("universal_sdd.orchestrator.get_adapter", return_value=Agent()):
        with patch("universal_sdd.orchestrator._save_features", side_effect=boom):
            with pytest.raises(RuntimeError, match="save boom"):
                run_development(initialized.root)
    assert (initialized.runtime / "task-baselines" / f"{task.id}.json").exists()

    seen = {}

    class Recover:
        def capabilities(self):
            return AgentCapabilities(installed=True)

        def interrupt(self):
            return True

        def run(self, prompt, **kwargs):
            if "TASK_IMPLEMENTATION" in prompt:
                raise AssertionError("must recover, not re-implement")
            if "TASK_REVIEW_JSON" in prompt:
                seen["review"] = prompt
                return AgentResult(success=True, text=json.dumps({"status": "pass", "findings": [], "summary": "ok"}))
            return AgentResult(success=True, text="done")

    with patch("universal_sdd.orchestrator.get_adapter", return_value=Recover()):
        run_development(initialized.root)
    assert "crash_created.py" in seen["review"]


def test_copilot_rejects_bare_interpreter_shell():
    assert copilot_shell_spec(["python", "-c", "pass"]) is None
    assert copilot_shell_spec(["python"]) is None
    assert copilot_shell_spec(["bash"]) is None
    assert copilot_shell_spec(["pytest", "-q"]) == "shell(pytest:*)"
    assert copilot_shell_spec(["python", "-m", "pytest", "-q"]) == "shell(python -m pytest:*)"
    assert copilot_shell_spec(["npm", "run", "test"]) == "shell(npm run test:*)"


def test_copilot_python_pytest_is_prefixed(initialized):
    cfg = load_config(initialized)
    cfg.test_command = "python -m pytest -q"
    save_config(initialized, cfg)
    cmd = CopilotAdapter(initialized.root).build_command("hello", writable=True)
    tools = [cmd[i + 1] for i, part in enumerate(cmd) if part == "--allow-tool"]
    assert "shell(python -m pytest:*)" in tools
    assert "shell(python)" not in tools
    assert "shell(python:*)" not in tools


def test_feature_evidence_mapping_blocks_empty_evidence(initialized):
    features = load_features(initialized)
    feature = features[0]
    for task in feature.tasks:
        task.status = ItemStatus.verified
        task.evidence = []
    gaps = _feature_evidence_gaps(initialized, feature)
    assert gaps
    assert any("no passing evidence" in gap for gap in gaps)


def test_graphify_query_honors_small_limit(initialized, monkeypatch):
    write_trace_corpus(initialized)
    (initialized.root / "graphify-out").mkdir(exist_ok=True)
    (initialized.root / "graphify-out" / "graph.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr("universal_sdd.graphify_index.graphify_installed", lambda: True)
    monkeypatch.setattr(
        "universal_sdd.graphify_index.run_graphify",
        lambda root, args, timeout: (0, "CODE " * 2000) if args[:1] == ["query"] else (0, "built"),
    )
    text = query_knowledge_graph(initialized.root, "REQ-001", limit=200)
    assert len(text) <= 200
    assert "REQ-001" in text


def test_projection_tx_rolls_back_keyboardinterrupt(initialized):
    original = initialized.spec_bundle_file.read_text(encoding="utf-8")
    bundle = SpecBundle.model_validate(load_yaml(initialized.spec_bundle_file))
    with patch("universal_sdd.documentation.render_docs", side_effect=KeyboardInterrupt()):
        with pytest.raises(KeyboardInterrupt):
            write_spec_bundle(initialized, bundle, preserve_verification=True)
    assert initialized.spec_bundle_file.read_text(encoding="utf-8") == original
    assert not (initialized.runtime / "projection-tx").exists()


def test_projection_tx_recovers_after_process_kill(initialized):
    from universal_sdd.artifacts import _canonical_files, _persist_tx

    snapshot = _canonical_files(initialized)
    _persist_tx(initialized, snapshot)
    initialized.spec_bundle_file.write_text("corrupt: true\n", encoding="utf-8")
    assert recover_projection_transaction(initialized) is True
    assert "corrupt" not in initialized.spec_bundle_file.read_text(encoding="utf-8")
    assert not (initialized.runtime / "projection-tx").exists()


def test_require_distinct_review_agent_blocks_self_review(initialized):
    cfg = load_config(initialized)
    cfg.require_distinct_review_agent = True
    save_config(initialized, cfg)
    with pytest.raises(RuntimeError, match="require_distinct_review_agent"):
        run_development(initialized.root)
    cfg.review_agent = AgentName.mock
    save_config(initialized, cfg)
    with pytest.raises(RuntimeError, match="require_distinct_review_agent"):
        run_development(initialized.root)
    cfg.review_agent = AgentName.cursor
    cfg.test_command = f'{sys.executable} -c "pass"'
    save_config(initialized, cfg)

    class Implementer:
        def capabilities(self):
            return AgentCapabilities(installed=True)

        def interrupt(self):
            return True

        def run(self, prompt, **kwargs):
            if "TASK_REVIEW_JSON" in prompt:
                raise AssertionError("primary must not review")
            return AgentResult(success=True, text="implemented")

    class Reviewer:
        def capabilities(self):
            return AgentCapabilities(installed=True)

        def interrupt(self):
            return True

        def run(self, prompt, **kwargs):
            return AgentResult(success=True, text=json.dumps({"status": "pass", "findings": [], "summary": "ok"}))

    def fake_get(name, root):
        return Reviewer() if AgentName(name) == AgentName.cursor else Implementer()

    with patch("universal_sdd.orchestrator.get_adapter", side_effect=fake_get):
        state = run_development(initialized.root)
    assert state.run_status == RunStatus.completed


def test_skills_do_not_claim_graphify_indexes_corpus():
    from universal_sdd.skill_library import SKILLS

    implement = SKILLS["implement-task/SKILL.md"]
    spec = SKILLS["create-feature-spec/SKILL.md"]
    assert "Corpus Graphify indexes" not in implement
    assert "Graphify indexes" not in spec
    assert "deterministically" in implement
    assert "--code-only" in implement

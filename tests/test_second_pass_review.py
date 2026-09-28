import json
import subprocess
import sys
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from universal_sdd.artifacts import write_architecture, write_spec_bundle
from universal_sdd.clarifications import (
    Clarification,
    accept_deferred_defaults,
    answer_clarification,
    assert_start_ready,
    load_decisions,
    merge_open_questions,
    record_architecture_decisions,
    save_clarifications,
)
from universal_sdd.cli import app
from universal_sdd.compress import HEADROOM_FAILURE_LIMIT, compress_for_prompt, headroom_compress
from universal_sdd.context_pack import ContextPack, adr_id_from_path, build_context_pack, rebuild_review_pack, skills_for_phase
from universal_sdd.graphify_index import query_knowledge_graph, write_trace_corpus
from universal_sdd.models import AgentCapabilities, AgentName, AgentResult, DecisionStatus, RunStatus, SpecBundle
from universal_sdd.orchestrator import apply_change, ask_project, run_development
from universal_sdd.prompts import architecture_prompt, change_analysis_prompt, reconcile_change_prompt, repair_task_prompt, spec_bundle_prompt
from universal_sdd.skill_library import LIFECYCLE_SKILLS, SKILLS, lifecycle_skill
from universal_sdd.status import load_features
from universal_sdd.storage import SDDPaths, load_config, load_project_state, load_yaml, save_config, save_project_state


@pytest.fixture
def initialized(demo_repo):
    result = CliRunner().invoke(app, ["init", "--root", str(demo_repo), "--agent", "mock", "--yes"])
    assert result.exit_code == 0, result.output
    return SDDPaths(demo_repo)


def test_accept_deferred_writes_architecture_default(initialized):
    decisions = load_decisions(initialized)
    decisions[0].status = DecisionStatus.deferred
    decisions[0].selected = None
    write_architecture(initialized, decisions)
    record_architecture_decisions(initialized, decisions)
    accept_deferred_defaults(initialized)
    updated = load_decisions(initialized)
    assert updated[0].selected == "FastAPI"
    assert updated[0].status == DecisionStatus.selected
    adr = next(initialized.decisions.glob("arch-001-*.md"))
    assert "FastAPI" in adr.read_text()
    assert_start_ready(initialized)


def test_accept_deferred_rejects_missing_default(initialized):
    save_clarifications(initialized, [Clarification(id="Q1", question="Which host?", status="deferred")])
    with pytest.raises(RuntimeError, match="explicit default"):
        assert_start_ready(initialized, accept_deferred=True)
    with pytest.raises(RuntimeError, match="selected=None|unresolved|clarifications"):
        decisions = load_decisions(initialized)
        decisions[0].status = DecisionStatus.deferred
        decisions[0].selected = None
        decisions[0].recommendation = None
        decisions[0].options = []
        write_architecture(initialized, decisions)
        record_architecture_decisions(initialized, decisions)
        assert_start_ready(initialized, accept_deferred=True)


def test_answer_clarification_updates_adr(initialized):
    decisions = load_decisions(initialized)
    decisions[0].status = DecisionStatus.deferred
    decisions[0].selected = None
    write_architecture(initialized, decisions)
    record_architecture_decisions(initialized, decisions)
    answer_clarification(initialized, "ARCH-001", "Django")
    assert load_decisions(initialized)[0].selected == "Django"
    assert "Django" in next(initialized.decisions.glob("arch-001-*.md")).read_text()


def test_spec_phase_questions_enter_the_gate(initialized):
    merge_open_questions(initialized, ["Must notes be encrypted at rest?"])
    with pytest.raises(RuntimeError, match="encrypted"):
        assert_start_ready(initialized)


def test_write_spec_bundle_does_not_reset_lifecycle(initialized):
    state = load_project_state(initialized)
    state.active_run_id = "RUN-KEEP"
    state.tokens_used = 99
    state.current_task = "TASK-F001-001"
    state.initialized = False
    state.run_status = RunStatus.initializing
    save_project_state(initialized, state)
    bundle = SpecBundle.model_validate(load_yaml(initialized.spec_bundle_file))
    write_spec_bundle(initialized, bundle, preserve_verification=True)
    after = load_project_state(initialized)
    assert after.initialized is False
    assert after.run_status == RunStatus.initializing
    assert after.active_run_id == "RUN-KEEP"
    assert after.tokens_used == 99
    assert after.current_task == "TASK-F001-001"


def test_apply_change_preserves_run_accounting(initialized):
    state = load_project_state(initialized)
    state.active_run_id = "RUN-KEEP"
    state.tokens_used = 42
    save_project_state(initialized, state)

    class Reconciler:
        def capabilities(self):
            return AgentCapabilities(installed=True)

        def interrupt(self):
            return True

        def run(self, prompt, **kwargs):
            return AgentResult(
                success=True,
                text=json.dumps(
                    {
                        "requirement_updates": [
                            {
                                "id": "REQ-001",
                                "statement": "The system shall support the clarified core workflow.",
                            }
                        ],
                        "invalidate_tasks": [],
                    }
                ),
            )

    from universal_sdd.models import ChangeRequest
    with patch("universal_sdd.orchestrator.get_adapter", return_value=Reconciler()):
        apply_change(
            initialized.root,
            ChangeRequest(
                id="CR-KEEP",
                description="clarify wording",
                classification="requirement_change",
                affected_requirements=["REQ-001"],
                approved=True,
            ),
        )
    after = load_project_state(initialized)
    assert after.active_run_id == "RUN-KEEP"
    assert after.tokens_used >= 42
    ledger = load_yaml(initialized.state / "token-ledger.yaml", []) or []
    assert any(row.get("phase") == "change-reconcile" for row in ledger)


def test_review_pack_includes_new_untracked_file(initialized):
    features = load_features(initialized)
    task, feature = features[0].tasks[0], features[0]
    pack = build_context_pack(initialized, task, feature, phase="implement")
    new_file = initialized.root / "app" / "notes.py"
    new_file.parent.mkdir(parents=True)
    new_file.write_text("def create_note():\n    return 1\n", encoding="utf-8")
    rebuilt = rebuild_review_pack(initialized, task, feature, ["app/notes.py"], pack)
    text = rebuilt.render()
    assert rebuilt.skill == "review-task"
    assert "app/notes.py" in rebuilt.files
    assert "app/notes.py" in rebuilt.changed_files
    assert "app/notes.py" in rebuilt.out_of_scope
    assert "review-task" in text
    assert "Last review findings" in text


def test_greenfield_review_prompt_sees_new_file(initialized):
    cfg = load_config(initialized)
    cfg.test_command = f'{sys.executable} -c "pass"'
    save_config(initialized, cfg)
    seen = {}

    class Agent:
        def capabilities(self):
            return AgentCapabilities(installed=True)

        def interrupt(self):
            return True

        def run(self, prompt, **kwargs):
            if "TASK_IMPLEMENTATION" in prompt:
                path = initialized.root / "app" / "created.py"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("VALUE = 1\n", encoding="utf-8")
                return AgentResult(success=True, text="implemented")
            if "TASK_REVIEW_JSON" in prompt:
                seen["review"] = prompt
                return AgentResult(success=True, text=json.dumps({"status": "pass", "findings": [], "summary": "ok"}))
            return AgentResult(success=True, text="done")

    with patch("universal_sdd.orchestrator.get_adapter", return_value=Agent()):
        state = run_development(initialized.root)
    assert state.run_status == RunStatus.completed
    assert "created.py" in seen["review"]
    assert "review-task" in seen["review"]


def test_review_agent_is_selected(initialized):
    cfg = load_config(initialized)
    cfg.test_command = f'{sys.executable} -c "pass"'
    cfg.review_agent = AgentName.cursor
    save_config(initialized, cfg)
    names = []

    class Implementer:
        def capabilities(self):
            return AgentCapabilities(installed=True)

        def interrupt(self):
            return True

        def run(self, prompt, **kwargs):
            if "TASK_REVIEW_JSON" in prompt:
                raise AssertionError("primary agent must not review when review_agent is set")
            return AgentResult(success=True, text="implemented")

    class Reviewer:
        def capabilities(self):
            return AgentCapabilities(installed=True)

        def interrupt(self):
            return True

        def run(self, prompt, **kwargs):
            assert "configured review agent" in prompt
            return AgentResult(success=True, text=json.dumps({"status": "pass", "findings": [], "summary": "ok"}))

    def fake_get(name, root):
        names.append(AgentName(name))
        return Reviewer() if AgentName(name) == AgentName.cursor else Implementer()

    with patch("universal_sdd.orchestrator.get_adapter", side_effect=fake_get):
        state = run_development(initialized.root)
    assert AgentName.cursor in names
    assert state.run_status == RunStatus.completed


def test_read_only_restore_keeps_existing_untracked_files(initialized):
    from universal_sdd.agent_guard import workspace_snapshot
    from universal_sdd.orchestrator import invoke_agent

    created = initialized.root / "app" / "kept.py"
    created.parent.mkdir(parents=True, exist_ok=True)
    created.write_text("ok\n", encoding="utf-8")
    before = workspace_snapshot(initialized.root)

    class Peek:
        def capabilities(self):
            return AgentCapabilities(installed=True)

        def interrupt(self):
            return True

        def run(self, prompt, **kwargs):
            (initialized.root / "app" / "extra.py").write_text("new\n", encoding="utf-8")
            return AgentResult(success=True, text="ok")

    invoke_agent(Peek(), "hello", initialized.root, writable=False, mode="ask")
    assert created.exists()
    assert not (initialized.root / "app" / "extra.py").exists()
    rel = created.relative_to(initialized.root).as_posix()
    assert workspace_snapshot(initialized.root)[rel] == before[rel]


def test_ask_restores_source_mutations(initialized):
    secret = initialized.root / "leaked.txt"

    class Mutating:
        def capabilities(self):
            return AgentCapabilities(installed=True)

        def interrupt(self):
            return True

        def run(self, prompt, **kwargs):
            secret.write_text("exfiltrated", encoding="utf-8")
            return AgentResult(success=True, text="FastAPI is approved.")

    with patch("universal_sdd.orchestrator.get_adapter", return_value=Mutating()):
        text = ask_project(initialized.root, "What backend was chosen?")
    assert "FastAPI" in text or "approved" in text.lower()
    assert not secret.exists()


def test_query_returns_requirement_from_corpus(initialized, monkeypatch):
    write_trace_corpus(initialized)
    (initialized.root / "graphify-out").mkdir(exist_ok=True)
    (initialized.root / "graphify-out" / "graph.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr("universal_sdd.graphify_index.graphify_installed", lambda: True)
    monkeypatch.setattr(
        "universal_sdd.graphify_index.run_graphify",
        lambda root, args, timeout: (0, "app/notes.py") if args[:1] == ["query"] else (0, "built"),
    )
    text = query_knowledge_graph(initialized.root, "REQ-001")
    assert "REQ-001" in text
    assert "Traceability corpus" in text
    assert "app/notes.py" in text


def test_lifecycle_skills_are_routed():
    required = {
        "implement-task",
        "review-task",
        "architecture-design",
        "create-feature-spec",
        "reconcile",
        "spec-drift",
        "verify-feature",
    }
    shipped = {path.split("/")[0] for path in SKILLS}
    assert required <= shipped
    assert set(LIFECYCLE_SKILLS.values()) == required
    from universal_sdd.models import Task
    task = Task(id="T", feature_id="F", title="t", description="d")
    assert skills_for_phase("implement", task)[0] == "implement-task"
    assert skills_for_phase("review", task)[0] == "review-task"
    assert lifecycle_skill("verify") == "verify-feature"
    assert "architecture-design" in architecture_prompt("prd")
    assert "create-feature-spec" in spec_bundle_prompt("prd", [])
    assert "spec-drift" in change_analysis_prompt("x", "ctx")
    assert "reconcile" in reconcile_change_prompt(
        "x",
        "requirement_change",
        stage_dir=".sdd/runtime/reconcile/CR-TEST",
        affected_requirements=["REQ-001"],
    )
    pack = ContextPack(task_id="T", feature_id="F", skill="implement-task")
    assert "implement-task" in repair_task_prompt(task, [], pack)
    assert "review-task" not in repair_task_prompt(task, [], pack)


def test_context_pack_keeps_findings_and_adr_ids(initialized):
    (initialized.decisions / "ADR-001-cache.md").write_text("# cache\n", encoding="utf-8")
    (initialized.decisions / "ADR-002-auth.md").write_text("# auth\n", encoding="utf-8")
    features = load_features(initialized)
    pack = build_context_pack(initialized, features[0].tasks[0], features[0])
    assert "ADR-001" in pack.adr_ids
    assert "ADR-002" in pack.adr_ids
    assert "ARCH-001" in pack.adr_ids
    oversized = pack.model_copy(
        update={
            "spec_excerpt": "SPEC " * 4000,
            "graph_excerpt": "GRAPH " * 4000,
            "acceptance_criteria": ["must keep this AC"],
            "last_findings": [{"summary": "blocking repair", "severity": "high", "violates_ac": True}],
        }
    )
    text = oversized.render()
    assert "must keep this AC" in text
    assert "blocking repair" in text
    assert "Last review findings" in text
    assert adr_id_from_path(initialized.decisions / "ADR-001-cache.md") == "ADR-001"


def test_headroom_timeout_opens_circuit(monkeypatch):
    from universal_sdd import compress as compress_mod

    compress_mod._FAILURES = 0
    compress_mod._CIRCUIT_OPEN = False
    monkeypatch.setattr(compress_mod, "_headroom_importable", lambda: True)

    def hang(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="headroom", timeout=1)

    monkeypatch.setattr(compress_mod.subprocess, "run", hang)
    for _ in range(HEADROOM_FAILURE_LIMIT):
        assert headroom_compress("payload") is None
    assert compress_mod._CIRCUIT_OPEN
    assert headroom_compress("payload") is None
    compress_mod._FAILURES = 0
    compress_mod._CIRCUIT_OPEN = False


def test_headroom_opt_out(initialized, monkeypatch):
    cfg = load_config(initialized)
    cfg.enable_headroom = False
    save_config(initialized, cfg)
    called = {"n": 0}

    def boom(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("Headroom must not run when disabled")

    monkeypatch.setattr("universal_sdd.compress.headroom_compress", boom)
    out = compress_for_prompt(initialized, "FAILED check\n" + ("x\n" * 20), label="opt-out")
    assert "FAILED" in out
    assert called["n"] == 0


def test_adapter_middle_modes_and_fail_fast(tmp_path):
    from universal_sdd.adapters.base import assert_writable_command
    from universal_sdd.adapters.copilot import CopilotAdapter
    from universal_sdd.adapters.gemini import GeminiAdapter

    gem = GeminiAdapter(tmp_path).build_command("hello", writable=True)
    assert gem[gem.index("--approval-mode") + 1] == "auto_edit"
    cop = CopilotAdapter(tmp_path).build_command("hello", writable=True)
    assert "--no-ask-user" in cop
    assert cop[cop.index("--allow-tool") + 1] == "write"
    with pytest.raises(RuntimeError, match="cannot write"):
        assert_writable_command("gemini", ["gemini", "-p", "hello"])
    assert_writable_command("scripted-process-fixture", [sys.executable, "fixture_agent.py"])
    assert_writable_command("mock", ["mock", "hello"])


def test_brownfield_summary_prioritizes_manifests(tmp_path):
    from universal_sdd.repository import summarize_repository

    (tmp_path / "zzz.txt").write_text("noise\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# App\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print(1)\n", encoding="utf-8")
    (tmp_path / "graphify-out").mkdir()
    (tmp_path / "graphify-out" / "graph.json").write_text("{}\n", encoding="utf-8")
    text = summarize_repository(tmp_path)
    assert text.index("pyproject.toml") < text.index("zzz.txt")
    assert text.index("README.md") < text.index("zzz.txt")
    assert "Graphify graph: present" in text
    assert "sha256=" in text
    assert "Evidence excerpts" in text
    assert "Pre-init Graphify query" in text

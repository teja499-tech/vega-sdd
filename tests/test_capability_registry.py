import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from universal_sdd.agent_guard import guarded_run
from universal_sdd.artifacts import recover_projection_transaction
from universal_sdd.cli import app
from universal_sdd.context_pack import build_context_pack, skills_for_phase
from universal_sdd.models import AgentCapabilities, AgentResult, Task
from universal_sdd.prompts import spec_bundle_prompt
from universal_sdd.status import load_features
from universal_sdd.storage import SDDPaths
from universal_sdd.workspace import configure, load_workspace


@pytest.fixture
def initialized(demo_repo):
    result = CliRunner().invoke(app, ["init", "--root", str(demo_repo), "--agent", "mock", "--yes"])
    assert result.exit_code == 0, result.output
    return SDDPaths(demo_repo)


def test_task_can_route_an_explicit_project_skill(initialized):
    local = initialized.skills / "healthcare-compliance" / "SKILL.md"
    local.parent.mkdir(parents=True)
    local.write_text(
        "---\nname: healthcare-compliance\n"
        "description: Verify healthcare privacy boundaries.\n---\n\n# Healthcare\n",
        encoding="utf-8",
    )
    features = load_features(initialized)
    task, feature = features[0].tasks[0], features[0]
    task.skills = ["healthcare-compliance"]
    pack = build_context_pack(initialized, task, feature)
    assert "healthcare-compliance" in pack.extra_skills
    assert ".agents/skills/healthcare-compliance/SKILL.md" in pack.files
    assert "Verify healthcare privacy boundaries" in pack.render()


def test_missing_explicit_project_skill_fails_closed(initialized):
    features = load_features(initialized)
    task, feature = features[0].tasks[0], features[0]
    task.skills = ["missing-domain-skill"]
    with pytest.raises(RuntimeError, match="missing-domain-skill"):
        build_context_pack(initialized, task, feature)


def test_risk_routing_uses_triggered_specialists(initialized):
    task = Task(
        id="TASK-RISK-001",
        feature_id="F001",
        title="Harden LLM tool retries and latency",
        description="Add timeout, circuit breaker, prompt injection checks, and load tests for MCP tool calls.",
        verification=["Run an end-to-end browser journey and performance benchmark"],
    )
    primary, extras = skills_for_phase("review", task, initialized.root)
    assert primary == "review-task"
    assert {"security-review", "threat-model", "reliability-review", "performance-review", "agent-system-review", "e2e-testing"} <= set(extras)


def test_context_pack_routes_roles_by_phase(initialized):
    features = load_features(initialized)
    task, feature = features[0].tasks[0], features[0]
    task.description += " Add an authenticated API route and database migration."
    implement = build_context_pack(initialized, task, feature, phase="implement")
    review = build_context_pack(initialized, task, feature, phase="review")
    assert implement.role == "developer"
    assert review.role == "qa-engineer"
    assert "security-reviewer" in review.extra_roles
    assert "integration-reviewer" in review.extra_roles
    assert ".agents/roles/qa-engineer.md" in review.files
    assert "Role contract" in review.render()
    oversized = review.model_copy(update={"spec_excerpt": "spec " * 10000, "graph_excerpt": "graph " * 10000})
    assert "qa-engineer" in oversized.render()


def test_spec_prompt_exposes_task_skill_contract(initialized):
    prompt = spec_bundle_prompt("prd", [], skill_root=initialized.root)
    assert '"skills":["task-relevant-skill"]' in prompt
    assert "Available task skills" in prompt
    assert "agent-system-review" in prompt


def test_real_agent_init_prints_complete_next_steps(demo_repo, monkeypatch):
    monkeypatch.setattr("universal_sdd.cli.get_adapter", lambda name, root: __import__("universal_sdd.adapters.mock", fromlist=["MockAdapter"]).MockAdapter(root))
    result = CliRunner().invoke(app, ["init", "--root", str(demo_repo), "--agent", "cursor", "--yes"])
    assert result.exit_code == 0, result.output
    assert "sdd project setup" in result.output
    assert "sdd repo" in result.output and "branch <scope>" in result.output
    assert "sdd start --max-tasks 1" in result.output


def test_task_skill_names_reject_path_traversal():
    with pytest.raises(ValueError):
        Task(id="T", feature_id="F", title="x", description="x", skills=["../../escape"])


def test_projection_recovery_rejects_absolute_snapshot_paths(initialized, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("owner\n", encoding="utf-8")
    tx = initialized.runtime / "projection-tx"
    (tx / "files").mkdir(parents=True)
    (tx / "active.json").write_text(
        json.dumps({"active": True, "files": [str(outside)]}),
        encoding="utf-8",
    )
    assert recover_projection_transaction(initialized) is False
    assert outside.read_text(encoding="utf-8") == "owner\n"


def test_agent_cannot_mutate_controller_runtime(initialized):
    baseline = initialized.runtime / "task-baselines" / "TASK-1.json"
    baseline.parent.mkdir(parents=True, exist_ok=True)
    baseline.write_text('{"safe": true}\n', encoding="utf-8")

    class Mutating:
        def capabilities(self):
            return AgentCapabilities(installed=True)

        def interrupt(self):
            return True

        def run(self, prompt, **kwargs):
            baseline.write_text('{"safe": false}\n', encoding="utf-8")
            return AgentResult(success=True, text="ok")

    with pytest.raises(RuntimeError, match="protected controller files"):
        guarded_run(Mutating(), "work", initialized.root, writable=True, mode="agent")
    assert json.loads(baseline.read_text(encoding="utf-8")) == {"safe": True}


def test_workspace_approval_binds_agent_capabilities(initialized):
    configure(
        initialized.root,
        {
            "schema_version": 1,
            "components": [
                {
                    "id": "app",
                    "path": ".",
                    "kind": "custom",
                    "checks": {"test": {"argv": ["python", "-m", "pytest"]}},
                }
            ],
        },
    )
    load_workspace(initialized.root)
    role = initialized.roles / "developer.md"
    role.write_text(role.read_text(encoding="utf-8") + "\nChanged after approval.\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="roles, or skills changed"):
        load_workspace(initialized.root)


def test_git_restore_does_not_rewrite_branch_agent_switched_to(initialized):
    root = initialized.root
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.test"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
    base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    subprocess.run(["git", "checkout", "-qb", "agent-branch"], cwd=root, check=True)
    (root / "agent-only.txt").write_text("agent\n", encoding="utf-8")
    subprocess.run(["git", "add", "agent-only.txt"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "agent commit"], cwd=root, check=True)
    agent_tip = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    subprocess.run(["git", "checkout", "-q", "main"], cwd=root, check=True)

    class Switching:
        def run(self, prompt, **kwargs):
            subprocess.run(["git", "checkout", "-q", "agent-branch"], cwd=root, check=True)
            return AgentResult(success=True, text="ok")

    with pytest.raises(RuntimeError, match="Git HEAD"):
        guarded_run(Switching(), "peek", root, writable=False, mode="ask")
    assert subprocess.check_output(["git", "branch", "--show-current"], cwd=root, text=True).strip() == "main"
    assert subprocess.check_output(["git", "rev-parse", "main"], cwd=root, text=True).strip() == base
    assert subprocess.check_output(["git", "rev-parse", "agent-branch"], cwd=root, text=True).strip() == agent_tip

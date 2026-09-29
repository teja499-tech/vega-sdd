"""Slice reconcile, prompt size, nested Cursor warning, change token ledger."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from universal_sdd.adapters.base import AgentAdapter
from universal_sdd.artifacts import write_architecture, write_spec_bundle
from universal_sdd.cli import app
from universal_sdd.models import (
    AgentCapabilities,
    AgentResult,
    ArchitectureDecision,
    ChangeRequest,
    ItemStatus,
    SpecBundle,
)
from universal_sdd.orchestrator import apply_change, ask_project
from universal_sdd.prompts import reconcile_change_prompt
from universal_sdd.reconcile import merge_reconcile_slices, nested_cursor_agent, stage_reconcile_inputs
from universal_sdd.status import load_features
from universal_sdd.storage import SDDPaths, dump_yaml, load_yaml


runner = CliRunner()


@pytest.fixture
def initialized(demo_repo: Path) -> SDDPaths:
    result = runner.invoke(
        app,
        ["init", "--root", str(demo_repo), "--agent", "mock", "--project-kind", "new", "--yes"],
    )
    assert result.exit_code == 0, result.output
    return SDDPaths(demo_repo)


class _SliceReconciler(AgentAdapter):
    name = "mock"

    def __init__(self, root: Path, payload: dict):
        super().__init__(root)
        self.payload = payload
        self.prompts: list[str] = []

    def capabilities(self) -> AgentCapabilities:
        return AgentCapabilities(installed=True)

    def build_command(self, prompt: str, *, writable: bool, mode: str = "agent") -> list[str]:
        return ["mock", prompt]

    def run(self, prompt: str, *, writable: bool = False, mode: str = "agent", on_event=None, env=None):
        self.prompts.append(prompt)
        text = json.dumps(self.payload)
        if on_event:
            from universal_sdd.models import AgentEvent
            on_event(AgentEvent(type="mock", message="reconciling"))
        return AgentResult(success=True, text=text)


def test_reconcile_prompt_uses_stage_dir_not_full_bundle():
    prompt = reconcile_change_prompt(
        "hostinger appliance",
        "architecture_change",
        stage_dir=".sdd/runtime/reconcile/CR-9DFB74",
        affected_requirements=["REQ-OPS-003", "REQ-AI-016"],
        affected_features=["F001", "F004"],
        affected_tasks=["TASK-F001-004"],
        proposed_changes=["Add web+vLLM compose stack"],
    )
    assert "RECONCILE_CHANGE_JSON" in prompt
    assert ".sdd/runtime/reconcile/CR-9DFB74" in prompt
    assert "REQ-OPS-003" in prompt
    assert "<CURRENT_SPEC_BUNDLE>" not in prompt
    assert "requirement_updates" in prompt
    assert len(prompt) < 8_000


def test_merge_reconcile_slices_updates_requirement(initialized):
    paths = SDDPaths(initialized.root)
    bundle = SpecBundle.model_validate(load_yaml(paths.spec_bundle_file))
    decisions = [ArchitectureDecision.model_validate(x) for x in (load_yaml(paths.architecture_decisions_file, []) or [])]
    merged, _ = merge_reconcile_slices(
        bundle,
        decisions,
        {
            "requirement_updates": [
                {"id": "REQ-001", "statement": "The system shall support the updated core workflow."}
            ],
            "invalidate_tasks": ["TASK-F001-001"],
        },
    )
    assert merged.requirements[0].statement.endswith("updated core workflow.")
    assert merged.features[0].tasks[0].id == "TASK-F001-001"


def test_merge_rejects_full_bundle_payload(initialized):
    paths = SDDPaths(initialized.root)
    bundle = SpecBundle.model_validate(load_yaml(paths.spec_bundle_file))
    with pytest.raises(RuntimeError, match="slice updates"):
        merge_reconcile_slices(bundle, [], {"bundle": load_yaml(paths.spec_bundle_file)})


def test_merge_rejects_controller_owned_status(initialized):
    paths = SDDPaths(initialized.root)
    bundle = SpecBundle.model_validate(load_yaml(paths.spec_bundle_file))
    cr = ChangeRequest(
        id="CR-SCOPE",
        description="update core req",
        classification="requirement_change",
        affected_requirements=["REQ-001"],
        approved=True,
    )
    with pytest.raises(RuntimeError, match="controller-owned fields: status"):
        merge_reconcile_slices(
            bundle,
            [],
            {"requirement_updates": [{"id": "REQ-001", "status": "verified"}]},
            cr,
        )


def test_merge_rejects_updates_outside_approved_scope(initialized):
    paths = SDDPaths(initialized.root)
    bundle = SpecBundle.model_validate(load_yaml(paths.spec_bundle_file))
    cr = ChangeRequest(
        id="CR-SCOPE",
        description="update one requirement",
        classification="requirement_change",
        affected_requirements=[],
        approved=True,
    )
    with pytest.raises(RuntimeError, match="outside the approved change scope"):
        merge_reconcile_slices(
            bundle,
            [],
            {"requirement_updates": [{"id": "REQ-001", "statement": "Unapproved rewrite."}]},
            cr,
        )


def test_merge_rejects_unapproved_new_ids_and_global_fields(initialized):
    paths = SDDPaths(initialized.root)
    bundle = SpecBundle.model_validate(load_yaml(paths.spec_bundle_file))
    cr = ChangeRequest(
        id="CR-SCOPE",
        description="clarify one requirement",
        classification="requirement_change",
        affected_requirements=["REQ-001"],
        approved=True,
    )
    with pytest.raises(RuntimeError, match="Requirement update is outside"):
        merge_reconcile_slices(
            bundle,
            [],
            {"requirement_updates": [{"id": "REQ-NEW", "title": "Unapproved", "statement": "An unrelated new requirement."}]},
            cr,
        )
    with pytest.raises(RuntimeError, match="Global update is outside"):
        merge_reconcile_slices(
            bundle,
            [],
            {"security_principles": ["Disable authentication controls in every environment."]},
            cr,
        )


def test_merge_supports_scoped_explicit_deletion(initialized):
    paths = SDDPaths(initialized.root)
    bundle = SpecBundle.model_validate(load_yaml(paths.spec_bundle_file))
    target = bundle.features[0].tasks[0].id
    cr = ChangeRequest(
        id="CR-DELETE",
        description="remove obsolete task",
        classification="requirement_change",
        affected_features=[bundle.features[0].id],
        affected_tasks=[target],
        approved=True,
    )
    merged, _ = merge_reconcile_slices(bundle, [], {"remove_task_ids": [target]}, cr)
    assert target not in {task.id for feature in merged.features for task in feature.tasks}
    assert target in {task.id for feature in bundle.features for task in feature.tasks}


def test_merge_rejects_quality_regression_in_top_level_contract(initialized):
    paths = SDDPaths(initialized.root)
    bundle = SpecBundle.model_validate(load_yaml(paths.spec_bundle_file))
    merged, _ = merge_reconcile_slices(bundle, [], {"test_strategy": []})
    from universal_sdd.spec_quality import assert_reconcile_slice_quality
    with pytest.raises(ValueError, match="test_strategy"):
        assert_reconcile_slice_quality(bundle, merged, {"test_strategy": []})


def test_change_request_id_cannot_escape_runtime_directory():
    with pytest.raises(ValueError, match="Unsafe change request identifier"):
        ChangeRequest(id="../../outside", description="unsafe")


def test_apply_change_stages_files_and_records_tokens(initialized):
    payload = {
        "requirement_updates": [
            {"id": "REQ-001", "statement": "The system shall support the staged reconcile workflow."}
        ],
        "invalidate_tasks": ["TASK-F001-001"],
        "notes": ["slice apply"],
    }
    adapter = _SliceReconciler(initialized.root, payload)
    fs = load_features(initialized)
    fs[0].tasks[0].status = ItemStatus.verified
    from universal_sdd.storage import dump_yaml
    dump_yaml(initialized.features_file, fs)
    cr = ChangeRequest(
        id="CR-SLICE",
        description="update core req",
        classification="requirement_change",
        affected_requirements=["REQ-001"],
        affected_features=["F001"],
        affected_tasks=["TASK-F001-001"],
        approved=True,
    )
    with patch("universal_sdd.orchestrator.get_adapter", return_value=adapter):
        apply_change(initialized.root, cr)
    stage = initialized.root / ".sdd/runtime/reconcile/CR-SLICE"
    assert not stage.exists()
    assert adapter.prompts
    assert "CURRENT_SPEC_BUNDLE" not in adapter.prompts[0]
    assert "CR-SLICE" in adapter.prompts[0]
    assert load_features(initialized)[0].tasks[0].status == ItemStatus.invalidated
    ledger = load_yaml(initialized.state / "token-ledger.yaml", []) or []
    reconcile_rows = [row for row in ledger if row.get("phase") == "change-reconcile"]
    assert reconcile_rows
    assert reconcile_rows[-1]["estimate_basis"] == "prompt+staged-input"


def test_apply_change_rejects_noop_and_cleans_stage(initialized):
    adapter = _SliceReconciler(initialized.root, {})
    cr = ChangeRequest(
        id="CR-NOOP",
        description="update core req",
        classification="requirement_change",
        affected_requirements=["REQ-001"],
        affected_features=["F001"],
        affected_tasks=["TASK-F001-001"],
        approved=True,
    )
    with patch("universal_sdd.orchestrator.get_adapter", return_value=adapter):
        with pytest.raises(RuntimeError, match="no canonical specification changes"):
            apply_change(initialized.root, cr)
    assert not (initialized.root / ".sdd/runtime/reconcile/CR-NOOP").exists()


def test_apply_change_keeps_new_scoped_tasks_pending(initialized):
    payload = {
        "requirement_updates": [
            {
                "id": "REQ-NEW",
                "title": "Export activity",
                "statement": "The system shall let users export their activity in a portable format.",
                "acceptance_criteria": ["A user can download a valid JSON activity export."],
            }
        ],
        "feature_updates": [
            {
                "id": "FNEW",
                "name": "Portable activity export",
                "summary": "Provide a deterministic export workflow so users can retain and move their activity data.",
                "requirements": ["REQ-NEW"],
                "invariants": ["Exports contain only the requesting user's activity."],
                "non_goals": ["Importing data from third-party systems."],
                "test_matrix": ["Generate an export and validate its JSON schema."],
                "tasks": [
                    {
                        "id": "TASK-FNEW-001",
                        "feature_id": "FNEW",
                        "title": "Implement activity export",
                        "description": "Implement a scoped JSON export endpoint with deterministic serialization and ownership checks.",
                        "implements": ["REQ-NEW"],
                        "verification": ["Acceptance test downloads and validates the export."],
                    }
                ],
            }
        ],
        "invalidate_tasks": ["TASK-FNEW-001"],
    }
    adapter = _SliceReconciler(initialized.root, payload)
    cr = ChangeRequest(
        id="CR-NEW-TASK",
        description="Add portable activity export",
        classification="requirement_change",
        affected_requirements=["REQ-NEW"],
        affected_features=["FNEW"],
        affected_tasks=["TASK-FNEW-001"],
        approved=True,
    )
    with patch("universal_sdd.orchestrator.get_adapter", return_value=adapter):
        apply_change(initialized.root, cr)

    feature = next(item for item in load_features(initialized) if item.id == "FNEW")
    assert feature.status == ItemStatus.pending
    assert feature.tasks[0].status == ItemStatus.pending


def test_apply_change_cleans_stage_when_adapter_setup_fails(initialized):
    cr = ChangeRequest(
        id="CR-EARLYFAIL",
        description="update core req",
        classification="requirement_change",
        affected_requirements=["REQ-001"],
        approved=True,
    )
    with patch("universal_sdd.orchestrator.get_adapter", side_effect=RuntimeError("adapter unavailable")):
        with pytest.raises(RuntimeError, match="adapter unavailable"):
            apply_change(initialized.root, cr)
    assert not (initialized.root / ".sdd/runtime/reconcile/CR-EARLYFAIL").exists()


def test_stage_adds_consumer_git_exclude(initialized):
    subprocess.run(["git", "init", "-q"], cwd=initialized.root, check=True)
    stage = stage_reconcile_inputs(initialized, "CR-IGNORE", {"product": {}}, [])
    try:
        relative = stage.relative_to(initialized.root)
        ignored = subprocess.run(["git", "check-ignore", "--quiet", str(relative)], cwd=initialized.root)
        assert ignored.returncode == 0
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def test_projection_prunes_renamed_generated_feature_and_adr(initialized):
    paths = SDDPaths(initialized.root)
    bundle = SpecBundle.model_validate(load_yaml(paths.spec_bundle_file))
    decisions = [ArchitectureDecision.model_validate(x) for x in (load_yaml(paths.architecture_decisions_file, []) or [])]
    old_feature_dir = next(paths.specs.iterdir())
    old_adr = next(paths.decisions.glob("*.md"))
    manual_notes = old_feature_dir / "MANUAL-NOTES.md"
    manual_notes.write_text("Keep this user-authored file.\n", encoding="utf-8")

    bundle.features[0].name = "Renamed generated feature"
    decisions[0].category = "renamed_category"
    write_architecture(paths, decisions)
    write_spec_bundle(paths, bundle, preserve_verification=True, enforce_quality=False)

    assert old_feature_dir.exists()
    assert manual_notes.exists()
    assert not (old_feature_dir / "spec.md").exists()
    assert not (old_feature_dir / "tasks.md").exists()
    assert not (old_feature_dir / "state.yaml").exists()
    assert not old_adr.exists()
    assert any(path.name.startswith("F001-renamed-generated-feature") for path in paths.specs.iterdir())
    assert (paths.decisions / "arch-001-renamed-category.md").exists()


def test_ask_records_token_usage(initialized):
    class AskAdapter(AgentAdapter):
        name = "mock"

        def capabilities(self):
            return AgentCapabilities(installed=True)

        def build_command(self, prompt, *, writable, mode="agent"):
            return ["mock", prompt]

        def run(self, prompt, *, writable=False, mode="agent", on_event=None, env=None):
            return AgentResult(success=True, text="Architect answer grounded in specs.")

    with patch("universal_sdd.orchestrator.get_adapter", return_value=AskAdapter(initialized.root)):
        text = ask_project(initialized.root, "How do I run tests?")
    assert "Architect" in text
    ledger = load_yaml(initialized.state / "token-ledger.yaml", []) or []
    assert any(row.get("phase") == "ask" for row in ledger)


def test_nested_cursor_detection(monkeypatch):
    monkeypatch.delenv("CURSOR_AGENT", raising=False)
    monkeypatch.delenv("CURSOR_TRACE_ID", raising=False)
    monkeypatch.delenv("CURSOR_SESSION_ID", raising=False)
    monkeypatch.delenv("COMPOSER_SESSION", raising=False)
    assert nested_cursor_agent() is False
    monkeypatch.setenv("CURSOR_AGENT", "1")
    assert nested_cursor_agent() is True


def test_nested_cursor_block_env(initialized, monkeypatch):
    monkeypatch.setenv("CURSOR_AGENT", "1")
    monkeypatch.setenv("SDD_BLOCK_NESTED_CURSOR", "1")
    adapter = _SliceReconciler(initialized.root, {"requirement_updates": [], "invalidate_tasks": []})
    cr = ChangeRequest(
        id="CR-NEST",
        description="x",
        classification="requirement_change",
        approved=True,
    )
    with patch("universal_sdd.orchestrator.get_adapter", return_value=adapter):
        with pytest.raises(RuntimeError, match="Nested Cursor"):
            apply_change(initialized.root, cr)


def test_doctor_warns_on_missing_token_tools(initialized):
    result = runner.invoke(app, ["doctor", "--root", str(initialized.root)])
    assert result.exit_code == 0
    assert "Token efficiency" in result.output or "Graphify" in result.output

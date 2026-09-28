"""Slice reconcile, prompt size, nested Cursor warning, change token ledger."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from universal_sdd.adapters.base import AgentAdapter
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
from universal_sdd.reconcile import merge_reconcile_slices, nested_cursor_agent
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
    assert (stage / "bundle.yaml").exists()
    assert (stage / "decisions.yaml").exists()
    assert adapter.prompts
    assert "CURRENT_SPEC_BUNDLE" not in adapter.prompts[0]
    assert "CR-SLICE" in adapter.prompts[0]
    assert load_features(initialized)[0].tasks[0].status == ItemStatus.invalidated
    ledger = load_yaml(initialized.state / "token-ledger.yaml", []) or []
    assert any(row.get("phase") == "change-reconcile" for row in ledger)


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

import json
import sys
from unittest.mock import patch

import pytest
from typer.testing import CliRunner
from universal_sdd.cli import app
from universal_sdd.models import AgentCapabilities, AgentResult, ItemStatus, RunStatus
from universal_sdd.orchestrator import retry_task, run_development
from universal_sdd.review_policy import apply_review_policy, finding_blocks, review_allows_progress
from universal_sdd.status import load_features
from universal_sdd.storage import SDDPaths, dump_yaml, load_config, save_config


@pytest.fixture
def initialized(demo_repo):
    result = CliRunner().invoke(app, ["init", "--root", str(demo_repo), "--agent", "mock", "--yes"])
    assert result.exit_code == 0, result.output
    return SDDPaths(demo_repo)


def test_low_nits_do_not_block():
    data = apply_review_policy({
        "status": "fail",
        "findings": [{"severity": "low", "summary": "nit", "violates_ac": False}],
        "summary": "nits",
    })
    assert data["status"] == "warning"
    assert review_allows_progress(data)
    assert not finding_blocks(data["warnings"][0])


def test_critical_cannot_be_waived_by_violates_ac_false():
    data = apply_review_policy({
        "status": "pass",
        "findings": [{"severity": "critical", "violates_ac": False, "summary": "auth bypass"}],
    })
    assert data["status"] == "fail"
    assert not review_allows_progress(data)
    assert finding_blocks(data["findings"][0])


def test_medium_ac_break_blocks():
    data = apply_review_policy({
        "status": "pass",
        "findings": [{"severity": "medium", "summary": "AC broken", "violates_ac": True}],
    })
    assert data["status"] == "fail"
    assert not review_allows_progress(data)


def test_low_review_does_not_fail_task(initialized):
    p = initialized
    cfg = load_config(p)
    cfg.test_command = f'{sys.executable} -c "pass"'
    save_config(p, cfg)

    class Reviewer:
        def capabilities(self):
            return AgentCapabilities(installed=True)
        def interrupt(self):
            return True
        def run(self, prompt, **kwargs):
            if "TASK_REVIEW_JSON" in prompt:
                return AgentResult(success=True, text=json.dumps({
                    "status": "fail",
                    "findings": [{"severity": "low", "violates_ac": False, "summary": "optional polish"}],
                    "summary": "AC met",
                }))
            return AgentResult(success=True, text="done")

    with patch("universal_sdd.orchestrator.get_adapter", return_value=Reviewer()):
        state = run_development(p.root)
    assert state.run_status == RunStatus.completed
    assert load_features(p)[0].tasks[0].status == ItemStatus.verified


def test_failed_task_skipped_until_retry(initialized):
    p = initialized
    fs = load_features(p)
    fs[0].tasks[0].status = ItemStatus.failed
    dump_yaml(p.features_file, fs)

    class Idle:
        def capabilities(self):
            return AgentCapabilities(installed=True)
        def interrupt(self):
            return True
        def run(self, *args, **kwargs):
            raise AssertionError("failed tasks must be retried before an agent runs")

    with patch("universal_sdd.orchestrator.get_adapter", return_value=Idle()):
        state = run_development(p.root)
    assert state.run_status == RunStatus.blocked
    retry_task(p.root, fs[0].tasks[0].id, keep_code=True)
    assert load_features(p)[0].tasks[0].status == ItemStatus.implemented
    result = CliRunner().invoke(app, ["task", "retry", fs[0].tasks[0].id, "--keep-code", "--root", str(p.root)])
    assert result.exit_code == 0, result.output

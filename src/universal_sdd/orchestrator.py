from __future__ import annotations

import shlex
import subprocess
import uuid
import tempfile
import os
import signal
from pathlib import Path
from typing import Callable

from .adapters import get_adapter
from .artifacts import project_context, write_architecture, write_spec_bundle
from .journal import Journal
from .json_utils import extract_json, parse_structured
from .models import (
    AgentEvent,
    ChangeRequest,
    Feature,
    ItemStatus,
    ProjectState,
    RunStatus,
    Task,
    VerificationResult,
    ArchitectureDecision,
    AgentName,
    SpecBundle,
)
from .clarifications import assert_start_ready
from .context_pack import build_context_pack, persist_working_set
from .project_graph import refresh_graph
from .prompts import change_analysis_prompt, implement_task_prompt, repair_task_prompt, review_task_prompt, reconcile_change_prompt
from .review_policy import apply_review_policy, review_allows_progress
from .status import load_features, publish_status
from .storage import single_writer, SDDPaths, dump_yaml, load_config, load_project_state, load_yaml, save_project_state
from .task_checks import commands_for_task, compact_output, infer_check_paths, owner_command_argv
from .compress import compress_for_prompt
from .tokens import record_usage
from .traceability import validate_traceability


def _feature_ready(feature: Feature, features_by_id: dict[str, Feature]) -> bool:
    return all(features_by_id.get(dep) and features_by_id[dep].status == ItemStatus.verified for dep in feature.depends_on)


def _task_ready(task: Task, task_by_id: dict[str, Task]) -> bool:
    return all(task_by_id.get(dep) and task_by_id[dep].status == ItemStatus.verified for dep in task.depends_on)


def select_next(features: list[Feature]) -> tuple[Feature, Task] | None:
    fmap = {f.id: f for f in features}
    tmap = {t.id: t for f in features for t in f.tasks}
    for feature in features:
        if feature.status == ItemStatus.verified:
            continue
        if not _feature_ready(feature, fmap):
            continue
        for task in feature.tasks:
            if task.status == ItemStatus.verified:
                continue
            if task.status in {ItemStatus.blocked, ItemStatus.failed}:
                continue
            if _task_ready(task, tmap):
                return feature, task
    return None


def _save_features(paths: SDDPaths, features: list[Feature]) -> None:
    dump_yaml(paths.features_file, features)
    for feature in features:
        candidates = list(paths.specs.glob(f"{feature.id}-*"))
        if candidates:
            dump_yaml(candidates[0] / "state.yaml", feature)


def _run_check(command: str | list[str], root: Path, task_id: str, kind: str = "test") -> VerificationResult:
    argv = command if isinstance(command, list) else owner_command_argv(command)
    display = shlex.join(argv) if argv else ""
    process = subprocess.Popen(argv, cwd=root, shell=False, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, start_new_session=(os.name != "nt"))
    try:
        stdout, stderr = process.communicate(timeout=300)
    except (subprocess.TimeoutExpired, KeyboardInterrupt):
        if os.name != "nt":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.communicate()
        raise
    raw = (stdout + "\n" + stderr).strip()
    summary = compact_output(raw)
    return VerificationResult(
        id=f"VER-{uuid.uuid4().hex[:8].upper()}",
        task_id=task_id,
        kind=kind,
        status="pass" if process.returncode == 0 else "fail",
        command=display,
        summary=summary,
    )


def _agent_call(adapter, prompt: str, *, paths: SDDPaths, state: ProjectState, task_id: str | None, phase: str, root: Path, protected, writable: bool, mode: str, on_event):
    from .agent_guard import guarded_run
    result = guarded_run(adapter, prompt, root, protected, writable=writable, mode=mode, on_event=on_event)
    record_usage(paths, state, task_id=task_id, phase=phase, prompt=prompt, result=result)
    return result


def _append_verification(paths: SDDPaths, result: VerificationResult) -> None:
    rows = load_yaml(paths.verification_file, []) or []
    rows.append(result.model_dump(mode="json"))
    dump_yaml(paths.verification_file, rows)


@single_writer
def run_development(
    root: Path,
    *,
    max_tasks: int | None = None,
    on_event: Callable[[AgentEvent], None] | None = None,
    accept_deferred: bool = False,
) -> ProjectState:
    paths = SDDPaths(root)
    config = load_config(paths)
    state = load_project_state(paths)
    journal = Journal(paths.event_log)
    if not state.initialized:
        raise RuntimeError("Initialization is incomplete. Run `sdd init` to finish product, architecture, and spec generation.")
    assert_start_ready(paths, accept_deferred=accept_deferred)
    adapter = get_adapter(config.primary_agent, root)
    caps = adapter.capabilities()
    if not caps.installed:
        raise RuntimeError(f"Selected agent `{config.primary_agent.value}` is not installed. Run `sdd doctor`.")

    trace = validate_traceability(paths)
    if not trace.ok:
        state.run_status = RunStatus.blocked
        save_project_state(paths, state)
        raise RuntimeError("Traceability validation failed:\n- " + "\n- ".join(trace.errors))

    if config.primary_agent != AgentName.mock and not config.test_command and not (root / ".sdd/workspace.yaml").exists():
        raise RuntimeError("Configure test_command in .sdd/config.yaml before development; review alone cannot verify code.")

    from .workspace import policy_path,load_workspace,run_checks
    from .delivery import guard
    workspace=None
    if policy_path(root).exists():
        workspace=load_workspace(root);guard(root)
        adapter.timeout_seconds=workspace.agent_timeout
        max_tasks=min(max_tasks or workspace.max_tasks_per_run,workspace.max_tasks_per_run)
    elif config.primary_agent!=AgentName.mock:
        raise RuntimeError('Approve a project policy before real-agent execution: sdd project setup')

    pause_file = paths.runtime / "pause-requested"
    pause_file.unlink(missing_ok=True)
    state.run_status = RunStatus.running
    state.pause_requested = False
    state.stop_requested = False
    state.tokens_this_run = 0
    state.active_run_id = f"RUN-{uuid.uuid4().hex[:10].upper()}"
    save_project_state(paths, state)
    journal.append("run_started", run_id=state.active_run_id, agent=config.primary_agent.value)

    completed_this_run = 0
    try:
        while True:
            state = load_project_state(paths)
            if state.pause_requested or state.stop_requested or pause_file.exists():
                state.run_status = RunStatus.paused if (state.pause_requested or pause_file.exists()) else RunStatus.blocked
                save_project_state(paths, state)
                journal.append("run_paused", reason="requested")
                break
            features = load_features(paths)
            selected = select_next(features)
            if not selected:
                # If nothing is runnable, complete only when all tasks are verified.
                all_tasks = [t for f in features for t in f.tasks]
                if all_tasks and all(t.status == ItemStatus.verified for t in all_tasks):
                    for f in features:
                        f.status = ItemStatus.verified
                    _save_features(paths, features)
                    state.run_status = RunStatus.completed
                    state.current_feature = None
                    state.current_task = None
                    save_project_state(paths, state)
                    journal.append("run_completed", run_id=state.active_run_id)
                else:
                    state.run_status = RunStatus.blocked
                    save_project_state(paths, state)
                    journal.append("run_blocked", reason="no_ready_task")
                break

            feature, task = selected
            state.current_feature, state.current_task = feature.id, task.id
            save_project_state(paths, state)
            already_implemented = task.status == ItemStatus.implemented
            task.status = ItemStatus.implemented if already_implemented else ItemStatus.in_progress
            feature.status = ItemStatus.in_progress
            _save_features(paths, features)
            journal.append("task_started", feature=feature.id, task=task.id)

            if not task.check_paths:
                task.check_paths = infer_check_paths(root, task, feature)
            pack = build_context_pack(paths, task, feature)
            pack.spec_excerpt = compress_for_prompt(paths, pack.spec_excerpt, label=f"{task.id}-spec")
            pack.contracts = compress_for_prompt(paths, pack.contracts, label=f"{task.id}-contracts")
            pack.graph_excerpt = compress_for_prompt(paths, pack.graph_excerpt, label=f"{task.id}-graph")
            persist_working_set(task, pack)
            protected = workspace.protected_paths if workspace else []

            if not already_implemented:
                prompt = implement_task_prompt(task, feature, root, pack)
                result = _agent_call(
                    adapter, prompt, paths=paths, state=state, task_id=task.id, phase="implement",
                    root=root, protected=protected, writable=True, mode="agent", on_event=on_event,
                )
                task.attempts += 1
                if not result.success:
                    task.status = ItemStatus.failed
                    _save_features(paths, features)
                    state.run_status = RunStatus.blocked
                    save_project_state(paths, state)
                    journal.append("task_failed", task=task.id, exit_code=result.exit_code, output=result.text[-2000:])
                    break

                task.status = ItemStatus.implemented
                _save_features(paths, features)
                journal.append("task_implemented", task=task.id)
            else:
                journal.append("task_recovered_for_verification", task=task.id)

            repair_count = 0
            check_evidence = []
            while True:
                findings = []
                check_evidence = []
                for kind, command in commands_for_task(root, config, task):
                    display = shlex.join(command)
                    try:
                        vr = _run_check(command, root, task.id, kind)
                    except subprocess.TimeoutExpired:
                        vr = VerificationResult(id=f"VER-{uuid.uuid4().hex[:8].upper()}", task_id=task.id,
                            kind=kind, status="fail", command=display, summary="Check exceeded 300 seconds")
                    _append_verification(paths, vr)
                    journal.append("deterministic_check", task=task.id, command=display, status=vr.status)
                    check_evidence.append(vr.id)
                    if vr.status == "fail":
                        evidence = compress_for_prompt(paths, vr.summary, label=f"{task.id}-{kind}-failure")
                        findings.append({"summary": f"{kind} failed", "severity": "high", "violates_ac": True, "evidence": evidence, "repair": "Fix code and rerun checks"})
                        break
                if workspace and not findings:
                    result=run_checks(root,phase='task')
                    check_evidence.append(result['id'])
                    if not result['passed']:
                        findings.append({'summary':'Workspace check failed','severity':'high','violates_ac':True,'evidence':compact_output(str(result)),'repair':'Fix code and rerun checks'})
                if findings:
                    review_data = apply_review_policy({"status": "fail", "findings": findings, "summary": "Deterministic checks failed"})
                else:
                    review_prompt = review_task_prompt(task, feature, pack)
                    review = _agent_call(
                        adapter, review_prompt, paths=paths, state=state, task_id=task.id, phase="review",
                        root=root, protected=protected, writable=False, mode="plan", on_event=on_event,
                    )
                    try:
                        if not review.success:
                            raise ValueError("Reviewer failed")
                        def _validate_review(value):
                            if not isinstance(value, dict) or value.get("status") not in {"pass", "fail", "warning"}:
                                raise ValueError("Invalid review schema")
                            return value
                        review_data = apply_review_policy(parse_structured(review.text, _validate_review))
                    except (ValueError, TypeError):
                        review_data = {"status": "fail", "findings": [{"summary": "Reviewer returned invalid output", "severity": "high"}], "summary": "Invalid review"}
                    if review_allows_progress(review_data):
                        break
                if review_allows_progress(review_data):
                    break
                if repair_count >= config.max_repair_attempts:
                    break
                findings = review_data.get("findings", [])
                task.last_findings = [f for f in findings if isinstance(f, dict)]
                pack = pack.model_copy(update={"last_findings": task.last_findings})
                journal.append("review_failed", task=task.id, findings=findings)
                repair_count += 1
                journal.append("repair_started", task=task.id, attempt=repair_count)
                repair_prompt = repair_task_prompt(task, findings, pack)
                repair = _agent_call(
                    adapter, repair_prompt, paths=paths, state=state, task_id=task.id, phase="repair",
                    root=root, protected=protected, writable=True, mode="agent", on_event=on_event,
                )
                if not repair.success:
                    review_data = {"status": "fail", "summary": "Repair agent failed", "findings": findings}
                    break
                # Every mutation must pass fresh deterministic checks before review.

            review_status = "pass" if review_allows_progress(review_data) else "fail"
            if review_data.get("status") == "warning":
                review_status = "warning"
            review_result = VerificationResult(
                id=f"VER-{uuid.uuid4().hex[:8].upper()}",
                task_id=task.id,
                feature_id=feature.id,
                kind="review",
                status=review_status,
                summary=review_data.get("summary", ""),
                evidence=[str(f) for f in review_data.get("findings", [])] + [str(f) for f in review_data.get("warnings", [])],
            )
            _append_verification(paths, review_result)
            if not review_allows_progress(review_data):
                task.status = ItemStatus.failed
                task.last_findings = [f for f in review_data.get("findings", []) if isinstance(f, dict)]
                _save_features(paths, features)
                state.run_status = RunStatus.blocked
                save_project_state(paths, state)
                journal.append("task_blocked_after_review", task=task.id)
                break

            task.status = ItemStatus.verified
            task.evidence.extend([*check_evidence, review_result.id])
            if all(t.status == ItemStatus.verified for t in feature.tasks):
                feature.status = ItemStatus.verified
                if config.test_command:
                    suite = _run_check(owner_command_argv(config.test_command), root, task.id, "test")
                    _append_verification(paths, suite)
                    journal.append("feature_suite", feature=feature.id, status=suite.status)
                    if suite.status == "fail":
                        task.status = ItemStatus.failed
                        feature.status = ItemStatus.in_progress
                        _save_features(paths, features)
                        state.run_status = RunStatus.blocked
                        save_project_state(paths, state)
                        journal.append("feature_suite_failed", feature=feature.id, evidence=suite.summary)
                        break
                if workspace:
                    release = run_checks(root, phase="feature")
                    if not release.get("passed"):
                        task.status = ItemStatus.failed
                        feature.status = ItemStatus.in_progress
                        _save_features(paths, features)
                        state.run_status = RunStatus.blocked
                        save_project_state(paths, state)
                        journal.append("feature_suite_failed", feature=feature.id, evidence=release)
                        break
            _save_features(paths, features)
            refresh_graph(paths)
            journal.append("task_verified", task=task.id, evidence=review_result.id)
            from .recovery import checkpoint
            saved=checkpoint(root)
            state=load_project_state(paths);state.last_checkpoint=saved['id'];save_project_state(paths,state)
            publish_status(paths)
            completed_this_run += 1
            if max_tasks is not None and completed_this_run >= max_tasks:
                latest = load_features(paths)
                all_tasks = [t for f in latest for t in f.tasks]
                state = load_project_state(paths)
                if all_tasks and all(t.status == ItemStatus.verified for t in all_tasks):
                    for f in latest:
                        f.status = ItemStatus.verified
                    _save_features(paths, latest)
                    state.run_status = RunStatus.completed
                    state.current_feature = None
                    state.current_task = None
                    journal.append("run_completed", run_id=state.active_run_id)
                else:
                    state.run_status = RunStatus.paused
                    journal.append("run_paused", reason="max_tasks")
                save_project_state(paths, state)
                break
    except KeyboardInterrupt:
        adapter.interrupt()
        state = load_project_state(paths)
        state.run_status = RunStatus.paused
        state.pause_requested = False
        save_project_state(paths, state)
        journal.append("run_paused", reason="keyboard_interrupt")
    except Exception as exc:
        adapter.interrupt()
        state = load_project_state(paths)
        state.run_status = RunStatus.failed
        save_project_state(paths, state)
        journal.append("run_failed", error=str(exc))
        publish_status(paths)
        raise
    publish_status(paths)
    return load_project_state(paths)


@single_writer
def retry_task(root: Path, task_id: str, *, keep_code: bool = True) -> Task:
    paths = SDDPaths(root)
    features = load_features(paths)
    target: Task | None = None
    parent: Feature | None = None
    for feature in features:
        for task in feature.tasks:
            if task.id == task_id:
                target, parent = task, feature
                break
    if target is None or parent is None:
        raise RuntimeError(f"Unknown task: {task_id}")
    target.status = ItemStatus.implemented if keep_code else ItemStatus.pending
    if not keep_code:
        target.last_findings = []
    parent.status = ItemStatus.in_progress
    _save_features(paths, features)
    state = load_project_state(paths)
    if state.run_status in {RunStatus.blocked, RunStatus.failed, RunStatus.paused}:
        state.run_status = RunStatus.ready
        state.current_task = target.id
        state.current_feature = parent.id
        save_project_state(paths, state)
    Journal(paths.event_log).append("task_retry_requested", task=task_id, keep_code=keep_code)
    publish_status(paths)
    return target


def ask_project(root: Path, question: str) -> str:
    paths = SDDPaths(root)
    config = load_config(paths)
    adapter = get_adapter(config.primary_agent, root)
    from .artifacts import project_context
    from .compress import compress_for_prompt
    from .project_graph import graph_context
    from .prompts import ask_architect_prompt
    context = compress_for_prompt(
        paths,
        project_context(paths) + "\n\n" + graph_context(paths, question),
        label="ask-context",
    )
    result = adapter.run(ask_architect_prompt(question, context), writable=False, mode="ask")
    if not result.success:
        raise RuntimeError(result.text or "Ask agent failed")
    Journal(paths.event_log).append("project_asked", question=question[:200])
    return result.text


def request_pause(root: Path) -> ProjectState:
    paths = SDDPaths(root)
    state = load_project_state(paths)
    paths.runtime.mkdir(parents=True, exist_ok=True)
    (paths.runtime / "pause-requested").touch()
    state.pause_requested = True
    Journal(paths.event_log).append("pause_requested")
    return state


_CHANGE_JSON_KEYS = {
    "classification",
    "affected_requirements",
    "affected_features",
    "affected_tasks",
    "proposed_changes",
    "requires_approval",
}


def _change_analysis_json(adapter, paths: SDDPaths, prompt: str) -> dict:
    """Ask mode returns JSON more reliably than plan mode. Retry once."""
    current = prompt
    last = ""
    for attempt in range(2):
        result = adapter.run(current, writable=False, mode="ask")
        last = result.text or ""
        if not result.success:
            raise RuntimeError(last or "Change analysis agent failed")
        try:
            data = extract_json(last)
        except ValueError:
            paths.runtime.mkdir(parents=True, exist_ok=True)
            (paths.runtime / "change-analysis.txt").write_text(last, encoding="utf-8")
            current = (
                "CRITICAL CONTROLLER RETRY: Your previous reply was not valid JSON. "
                "Do not explain. Do not use markdown fences. The first character must be '{'. "
                "Return ONLY the required JSON value.\n\n" + prompt
            )
            continue
        if isinstance(data, dict):
            return {key: value for key, value in data.items() if key in _CHANGE_JSON_KEYS}
        break
    raise RuntimeError("Change analysis did not return JSON. See .sdd/runtime/change-analysis.txt")


def analyze_change(root: Path, description: str) -> ChangeRequest:
    paths = SDDPaths(root)
    config = load_config(paths)
    adapter = get_adapter(config.primary_agent, root)
    data = _change_analysis_json(adapter, paths, change_analysis_prompt(description, project_context(paths)))
    cr = ChangeRequest(
        id=f"CR-{uuid.uuid4().hex[:6].upper()}",
        description=description,
        **data,
    )
    cr.requires_approval = cr.classification != "implementation_defect"
    dump_yaml(paths.changes / f"{cr.id}.yaml", cr)
    Journal(paths.event_log).append("change_analyzed", change_id=cr.id, classification=cr.classification)
    return cr


@single_writer
def apply_change(root: Path, cr: ChangeRequest) -> ChangeRequest:
    paths = SDDPaths(root)
    config = load_config(paths)
    journal = Journal(paths.event_log)
    features = load_features(paths)
    stored = load_yaml(paths.changes / f"{cr.id}.yaml", {}) or {}
    if stored.get("status") == "applied":
        return ChangeRequest.model_validate(stored)

    if cr.classification == "implementation_defect":
        target = None
        for f in features:
            if f.id in cr.affected_features:
                target = f
                break
        if target is None:
            raise RuntimeError("Could not map implementation defect to an affected feature.")
        repair_index = 1 + sum(1 for t in target.tasks if "-R" in t.id)
        task_id = f"TASK-{target.id}-R{repair_index:03d}"
        target.tasks.append(Task(
            id=task_id,
            feature_id=target.id,
            title=f"Repair {cr.id}",
            description="; ".join(cr.proposed_changes) or cr.description,
            implements=cr.affected_requirements,
            verification=["Re-run affected acceptance criteria and independent review"],
        ))
        target.status = ItemStatus.in_progress
        _save_features(paths, features)
        cr.approved = True
        cr.status = "applied"
        dump_yaml(paths.changes / f"{cr.id}.yaml", cr)
        journal.append("implementation_repair_created", change_id=cr.id, task=task_id)
        publish_status(paths)
        return cr

    if not cr.approved:
        raise RuntimeError("This change mutates approved specifications/architecture and requires explicit approval.")

    bundle_data = load_yaml(paths.spec_bundle_file)
    decision_data = load_yaml(paths.architecture_decisions_file, []) or []
    if not bundle_data:
        raise RuntimeError("Structured spec bundle is missing; cannot safely reconcile change.")
    old_features = {f.id: f for f in load_features(paths)}
    old_tasks = {t.id: t for f in old_features.values() for t in f.tasks}

    adapter = get_adapter(config.primary_agent, root)
    result = adapter.run(
        reconcile_change_prompt(cr.description, cr.classification, str(bundle_data), str(decision_data)),
        writable=False,
        mode="plan",
    )
    if not result.success:
        raise RuntimeError(result.text)
    data = extract_json(result.text)
    from .spec_quality import assert_spec_quality
    bundle = SpecBundle.model_validate(data["bundle"])
    assert_spec_quality(bundle)
    decisions = [ArchitectureDecision.model_validate(x) for x in data.get("architecture_decisions", decision_data)]
    invalidated = set(data.get("invalidate_tasks", [])) | set(cr.affected_tasks)
    old_bundle = SpecBundle.model_validate(bundle_data)
    old_reqs = {r.id: r.model_dump(exclude={"status"}) for r in old_bundle.requirements}
    changed_reqs = set(cr.affected_requirements) | {r.id for r in bundle.requirements
        if old_reqs.get(r.id) != r.model_dump(exclude={"status"})}
    for feature in bundle.features:
        for task in feature.tasks:
            old = old_tasks.get(task.id)
            runtime = {"status", "attempts", "evidence", "working_set", "last_findings", "check_paths", "check_command"}
            if feature.id in cr.affected_features or changed_reqs.intersection(task.implements) or (
                old and old.model_dump(exclude=runtime) != task.model_dump(exclude=runtime)):
                invalidated.add(task.id)
    # Conservative transitive invalidation across task and feature dependencies.
    while True:
        previous = set(invalidated)
        affected_features = {f.id for f in bundle.features if any(t.id in invalidated for t in f.tasks)}
        for feature in bundle.features:
            for task in feature.tasks:
                if invalidated.intersection(task.depends_on) or affected_features.intersection(feature.depends_on):
                    invalidated.add(task.id)
        if previous == invalidated:
            break

    # Controller, not the agent, carries forward execution status for stable unaffected task IDs.
    for feature in bundle.features:
        old_feature = old_features.get(feature.id)
        if old_feature and feature.id not in cr.affected_features:
            feature.status = old_feature.status
        for task in feature.tasks:
            old = old_tasks.get(task.id)
            if old and task.id not in invalidated:
                task.status = old.status
                task.attempts = old.attempts
                task.evidence = old.evidence
            elif task.id in invalidated:
                task.status = ItemStatus.invalidated
                task.evidence = []
            elif not old:
                task.status = ItemStatus.pending
                task.attempts = 0
                task.evidence = []
        if any(t.status != ItemStatus.verified for t in feature.tasks):
            feature.status = ItemStatus.in_progress if any(t.status != ItemStatus.pending for t in feature.tasks) else ItemStatus.pending

    # Reject invalid agent proposals before touching approved project files.
    with tempfile.TemporaryDirectory() as temporary:
        staged = SDDPaths(Path(temporary))
        staged.ensure()
        dump_yaml(staged.requirements_file, bundle.requirements)
        dump_yaml(staged.features_file, bundle.features)
        report = validate_traceability(staged)
        if not report.ok:
            raise RuntimeError("Change rejected before mutation: " + "; ".join(report.errors))
    write_architecture(paths, decisions)
    write_spec_bundle(paths, bundle, preserve_verification=True)
    state = load_project_state(paths)
    state.run_status = RunStatus.ready
    state.current_feature = None
    state.current_task = None
    save_project_state(paths, state)
    cr.status = "applied"
    dump_yaml(paths.changes / f"{cr.id}.yaml", cr)
    trace = validate_traceability(paths)
    if not trace.ok:
        state.run_status = RunStatus.blocked
        save_project_state(paths, state)
        raise RuntimeError("Change was written but traceability is invalid:\n- " + "\n- ".join(trace.errors))
    journal.append("change_applied", change_id=cr.id, invalidated_tasks=sorted(invalidated), notes=data.get("notes", []))
    publish_status(paths)
    return cr

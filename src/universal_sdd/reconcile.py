"""Slice-based change reconcile: stage inputs on disk, merge agent updates, detect nested Cursor."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .models import (
    ArchitectureDecision,
    ChangeRequest,
    DesignDocument,
    Feature,
    ProductModel,
    Requirement,
    SpecBundle,
    Task,
)
from .storage import SDDPaths, atomic_write, dump_yaml

RECONCILE_TIMEOUT_SECONDS = 300

_ALLOWED_KEYS = {
    "requirement_updates",
    "remove_requirement_ids",
    "architecture_decision_updates",
    "remove_architecture_decision_ids",
    "feature_updates",
    "remove_feature_ids",
    "remove_task_ids",
    "design_document_updates",
    "product_update",
    "architecture_summary",
    "test_strategy",
    "security_principles",
    "release_criteria",
    "invalidate_tasks",
    "notes",
}
_TASK_RUNTIME_FIELDS = {
    "status",
    "attempts",
    "evidence",
    "working_set",
    "last_findings",
    "check_paths",
    "check_command",
}


def nested_cursor_agent() -> bool:
    """True when SDD is already running under a Cursor agent session (nested spawn is unsafe)."""
    markers = (
        "CURSOR_AGENT",
        "CURSOR_AGENT_ID",
        "CURSOR_SESSION_ID",
        "COMPOSER_SESSION",
        "CURSOR_WORKTREE_WORKSPACE",
    )
    if any(os.environ.get(name) for name in markers):
        return True
    # Cursor tool shells often set these when an agent is driving the terminal.
    if os.environ.get("CURSOR_RECORD_SESSION") == "1" and os.environ.get("TERM_PROGRAM") == "vscode":
        # Not definitive alone; require an agent-ish cue.
        if os.environ.get("VSCODE_AGENT_FOLDER") or os.environ.get("CURSOR_TRACE_ID"):
            return True
    return bool(os.environ.get("CURSOR_TRACE_ID"))


def stage_reconcile_inputs(
    paths: SDDPaths,
    cr_id: str,
    bundle_data: dict[str, Any],
    decision_data: list[Any],
) -> Path:
    """Write bundle/ADRs for the agent to read; keep the prompt small."""
    folder = paths.runtime / "reconcile" / cr_id
    try:
        folder.mkdir(parents=True, exist_ok=True)
        dump_yaml(folder / "bundle.yaml", bundle_data)
        dump_yaml(folder / "decisions.yaml", decision_data)
        _ignore_reconcile_runtime(paths.root)
    except BaseException:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    return folder


def _ignore_reconcile_runtime(root: Path) -> None:
    """Keep crash leftovers out of Git without modifying the owner's tracked .gitignore."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-path", "info/exclude"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return
    if result.returncode != 0 or not result.stdout.strip():
        return
    exclude = Path(result.stdout.strip())
    if not exclude.is_absolute():
        exclude = (root / exclude).resolve()
    exclude.parent.mkdir(parents=True, exist_ok=True)
    current = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    entry = "/.sdd/runtime/reconcile/"
    if entry not in {line.strip() for line in current.splitlines()}:
        prefix = current if not current or current.endswith("\n") else current + "\n"
        atomic_write(exclude, prefix + entry + "\n")


def _reject_fields(raw: dict[str, Any], forbidden: set[str], label: str) -> None:
    found = sorted(forbidden.intersection(raw))
    if found:
        raise RuntimeError(f"{label} may not set controller-owned fields: {', '.join(found)}")


def _id_list(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key) or []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RuntimeError(f"{key} must be a list of IDs")
    return value


def validate_reconcile_payload(
    bundle: SpecBundle,
    decisions: list[ArchitectureDecision],
    data: dict[str, Any],
    change: ChangeRequest | None = None,
) -> None:
    """Reject authority and approved-scope violations before merging agent output."""
    if not isinstance(data, dict):
        raise RuntimeError("Reconcile output must be a JSON object")
    if "bundle" in data or "architecture_decisions" in data:
        raise RuntimeError(
            "Reconcile must return slice updates, not a full bundle. "
            "Use requirement_updates / architecture_decision_updates / feature_updates / design_document_updates."
        )
    unexpected = sorted(set(data).difference(_ALLOWED_KEYS))
    if unexpected:
        raise RuntimeError(f"Unsupported reconcile fields: {', '.join(unexpected)}")

    req_updates = data.get("requirement_updates") or []
    feature_updates = data.get("feature_updates") or []
    decision_updates = data.get("architecture_decision_updates") or []
    doc_updates = data.get("design_document_updates") or {}
    remove_requirements = _id_list(data, "remove_requirement_ids")
    remove_features = _id_list(data, "remove_feature_ids")
    remove_tasks = _id_list(data, "remove_task_ids")
    remove_decisions = _id_list(data, "remove_architecture_decision_ids")
    invalidations = _id_list(data, "invalidate_tasks")
    if not isinstance(req_updates, list):
        raise RuntimeError("requirement_updates must be a list")
    if not isinstance(feature_updates, list):
        raise RuntimeError("feature_updates must be a list")
    if not isinstance(decision_updates, list):
        raise RuntimeError("architecture_decision_updates must be a list")
    if not isinstance(doc_updates, dict):
        raise RuntimeError("design_document_updates must be an object")
    from .documentation import CONTRACT
    unsupported_docs = sorted(set(doc_updates).difference(set(CONTRACT) | set(bundle.design_documents)))
    if unsupported_docs:
        raise RuntimeError(f"Unsupported design document keys: {', '.join(unsupported_docs)}")

    existing_requirements = {item.id for item in bundle.requirements}
    existing_features = {item.id for item in bundle.features}
    existing_decisions = {item.id for item in decisions}
    task_to_feature = {task.id: feature.id for feature in bundle.features for task in feature.tasks}
    existing_tasks = set(task_to_feature)
    affected_requirements = set(change.affected_requirements) if change else set()
    affected_features = set(change.affected_features) if change else set()
    affected_tasks = set(change.affected_tasks) if change else set()
    affected_decisions = set(change.affected_decisions) if change else set()
    affected_documents = set(change.affected_design_documents) if change else set()
    affected_globals = set(change.affected_global_fields) if change else set()

    for raw in req_updates:
        if not isinstance(raw, dict) or "id" not in raw:
            raise ValueError("requirement_updates entries require an id")
        _reject_fields(raw, {"status"}, f"requirement {raw['id']}")
        rid = str(raw["id"])
        if change and rid not in affected_requirements:
            raise RuntimeError(f"Requirement update is outside the approved change scope: {rid}")
    outside = sorted(set(remove_requirements).difference(existing_requirements & affected_requirements)) if change else []
    if outside:
        raise RuntimeError(f"Requirement removal is outside the approved change scope: {', '.join(outside)}")

    for raw in feature_updates:
        if not isinstance(raw, dict) or "id" not in raw:
            raise ValueError("feature_updates entries require an id")
        _reject_fields(raw, {"status"}, f"feature {raw['id']}")
        fid = str(raw["id"])
        if change and fid not in affected_features:
            raise RuntimeError(f"Feature update is outside the approved change scope: {fid}")
        tasks = raw.get("tasks") or []
        if not isinstance(tasks, list):
            raise RuntimeError(f"feature {fid} tasks must be a list")
        for task in tasks:
            if not isinstance(task, dict) or "id" not in task:
                raise ValueError("feature task updates require an id")
            _reject_fields(task, _TASK_RUNTIME_FIELDS, f"task {task['id']}")
            if change and str(task["id"]) not in affected_tasks:
                raise RuntimeError(f"Task update is outside the approved change scope: {task['id']}")
    outside = sorted(set(remove_features).difference(existing_features & affected_features)) if change else []
    if outside:
        raise RuntimeError(f"Feature removal is outside the approved change scope: {', '.join(outside)}")
    if change:
        removable_tasks = affected_tasks | {
            task_id for task_id, feature_id in task_to_feature.items() if feature_id in affected_features
        }
        outside = sorted(set(remove_tasks).difference(existing_tasks & removable_tasks))
        if outside:
            raise RuntimeError(f"Task removal is outside the approved change scope: {', '.join(outside)}")

    if (decision_updates or remove_decisions) and change and change.classification != "architecture_change":
        raise RuntimeError("Architecture decisions may only change in an approved architecture change")
    for raw in decision_updates:
        if not isinstance(raw, dict) or "id" not in raw:
            raise ValueError("architecture_decision_updates entries require an id")
        if change and str(raw["id"]) not in affected_decisions:
            raise RuntimeError(f"Architecture decision update is outside the approved change scope: {raw['id']}")
    if change:
        outside = sorted(set(remove_decisions).difference(existing_decisions & affected_decisions))
        if outside:
            raise RuntimeError(f"Architecture decision removal is outside the approved change scope: {', '.join(outside)}")

        outside = sorted(set(doc_updates).difference(affected_documents))
        if outside:
            raise RuntimeError(f"Design document update is outside the approved change scope: {', '.join(outside)}")

    for key in ("test_strategy", "security_principles", "release_criteria"):
        if key in data and not isinstance(data[key], list):
            raise RuntimeError(f"{key} must be a list")
    if "architecture_summary" in data and not isinstance(data["architecture_summary"], str):
        raise RuntimeError("architecture_summary must be a string")
    if data.get("product_update") is not None and not isinstance(data["product_update"], dict):
        raise RuntimeError("product_update must be an object")
    global_updates = {
        key
        for key in ("architecture_summary", "test_strategy", "security_principles", "release_criteria")
        if key in data
    }
    if data.get("product_update") is not None:
        global_updates.add("product")
    if change:
        outside = sorted(global_updates.difference(affected_globals))
        if outside:
            raise RuntimeError(f"Global update is outside the approved change scope: {', '.join(outside)}")

    if change:
        outside = sorted(set(invalidations).difference(affected_tasks))
        if outside:
            raise RuntimeError(f"Task invalidation is outside the approved change scope: {', '.join(outside)}")


def _index_by_id(items: list[Any]) -> dict[str, Any]:
    return {item.id: item for item in items}


def _merge_requirement(existing: Requirement | None, update: dict[str, Any]) -> Requirement:
    if existing is None:
        return Requirement.model_validate(update)
    data = existing.model_dump()
    data.update(update)
    return Requirement.model_validate(data)


def _merge_task(existing: Task | None, update: dict[str, Any], feature_id: str) -> Task:
    if existing is None:
        payload = dict(update)
        payload.setdefault("feature_id", feature_id)
        return Task.model_validate(payload)
    data = existing.model_dump()
    data.update(update)
    data["feature_id"] = feature_id
    return Task.model_validate(data)


def _merge_feature(existing: Feature | None, update: dict[str, Any]) -> Feature:
    payload = dict(update)
    task_updates = payload.pop("tasks", None)
    if existing is None:
        if task_updates is None:
            return Feature.model_validate(payload)
        payload["tasks"] = task_updates
        return Feature.model_validate(payload)
    data = existing.model_dump(exclude={"tasks"})
    data.update(payload)
    by_id = _index_by_id(existing.tasks)
    if task_updates is None:
        return Feature.model_validate({**data, "tasks": [t.model_dump() for t in existing.tasks]})
    merged_tasks: list[Task] = []
    seen: set[str] = set()
    for raw in task_updates:
        if not isinstance(raw, dict) or "id" not in raw:
            raise ValueError("feature task updates require an id")
        tid = str(raw["id"])
        seen.add(tid)
        merged_tasks.append(_merge_task(by_id.get(tid), raw, str(data["id"])))
    for task in existing.tasks:
        if task.id not in seen:
            merged_tasks.append(task)
    return Feature.model_validate({**data, "tasks": [t.model_dump() for t in merged_tasks]})


def _merge_decision(existing: ArchitectureDecision | None, update: dict[str, Any]) -> ArchitectureDecision:
    if existing is None:
        return ArchitectureDecision.model_validate(update)
    data = existing.model_dump(mode="json")
    data.update(update)
    return ArchitectureDecision.model_validate(data)


def merge_reconcile_slices(
    bundle: SpecBundle,
    decisions: list[ArchitectureDecision],
    data: dict[str, Any],
    change: ChangeRequest | None = None,
) -> tuple[SpecBundle, list[ArchitectureDecision]]:
    """Overlay agent slice updates onto the current approved bundle/ADRs."""
    validate_reconcile_payload(bundle, decisions, data, change)

    req_updates = data.get("requirement_updates") or []
    feature_updates = data.get("feature_updates") or []
    doc_updates = data.get("design_document_updates") or {}
    decision_updates = data.get("architecture_decision_updates") or []
    product_update = data.get("product_update")
    architecture_summary = data.get("architecture_summary")
    test_strategy = data.get("test_strategy")
    security_principles = data.get("security_principles")
    release_criteria = data.get("release_criteria")

    reqs = _index_by_id(bundle.requirements)
    for rid in data.get("remove_requirement_ids") or []:
        reqs.pop(rid, None)
    for raw in req_updates:
        if not isinstance(raw, dict) or "id" not in raw:
            raise ValueError("requirement_updates entries require an id")
        rid = str(raw["id"])
        reqs[rid] = _merge_requirement(reqs.get(rid), raw)

    features = _index_by_id([feature.model_copy(deep=True) for feature in bundle.features])
    remove_tasks = set(data.get("remove_task_ids") or [])
    if remove_tasks:
        for feature in features.values():
            feature.tasks = [task for task in feature.tasks if task.id not in remove_tasks]
    for fid in data.get("remove_feature_ids") or []:
        features.pop(fid, None)
    for raw in feature_updates:
        if not isinstance(raw, dict) or "id" not in raw:
            raise ValueError("feature_updates entries require an id")
        # copy so pop in _merge_feature does not mutate caller data unexpectedly
        payload = dict(raw)
        fid = str(payload["id"])
        features[fid] = _merge_feature(features.get(fid), payload)

    docs = dict(bundle.design_documents)
    for key, raw in doc_updates.items():
        if not isinstance(raw, dict):
            raise ValueError("design_document_updates values must be objects")
        existing = docs.get(key)
        base = existing.model_dump() if existing is not None else {}
        payload = dict(raw)
        section_updates = payload.pop("sections", None)
        base.update(payload)
        if section_updates is not None:
            if not isinstance(section_updates, dict):
                raise ValueError("design document sections must be an object")
            sections = dict(existing.sections) if existing is not None else {}
            sections.update(section_updates)
            base["sections"] = sections
        docs[key] = DesignDocument.model_validate(base)

    product = bundle.product
    if product_update is not None:
        if not isinstance(product_update, dict):
            raise RuntimeError("product_update must be an object")
        pdata = product.model_dump()
        pdata.update(product_update)
        product = ProductModel.model_validate(pdata)

    adr_by_id = _index_by_id(decisions)
    for did in data.get("remove_architecture_decision_ids") or []:
        adr_by_id.pop(did, None)
    for raw in decision_updates:
        if not isinstance(raw, dict) or "id" not in raw:
            raise ValueError("architecture_decision_updates entries require an id")
        did = str(raw["id"])
        adr_by_id[did] = _merge_decision(adr_by_id.get(did), raw)

    # Preserve original order, append new ids at the end.
    req_order = [r.id for r in bundle.requirements if r.id in reqs] + [r for r in reqs if r not in {x.id for x in bundle.requirements}]
    feature_order = [f.id for f in bundle.features if f.id in features] + [f for f in features if f not in {x.id for x in bundle.features}]
    decision_order = [d.id for d in decisions if d.id in adr_by_id] + [d for d in adr_by_id if d not in {x.id for x in decisions}]

    merged = SpecBundle(
        product=product,
        requirements=[reqs[i] for i in req_order if i in reqs],
        architecture_summary=architecture_summary if isinstance(architecture_summary, str) else bundle.architecture_summary,
        design_documents=docs,
        features=[features[i] for i in feature_order if i in features],
        test_strategy=test_strategy if isinstance(test_strategy, list) else bundle.test_strategy,
        security_principles=security_principles if isinstance(security_principles, list) else bundle.security_principles,
        release_criteria=release_criteria if isinstance(release_criteria, list) else bundle.release_criteria,
    )
    merged_decisions = [adr_by_id[i] for i in decision_order if i in adr_by_id]
    return merged, merged_decisions

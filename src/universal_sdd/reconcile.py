"""Slice-based change reconcile: stage inputs on disk, merge agent updates, detect nested Cursor."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .models import (
    ArchitectureDecision,
    DesignDocument,
    Feature,
    ProductModel,
    Requirement,
    SpecBundle,
    Task,
)
from .storage import SDDPaths, dump_yaml

RECONCILE_TIMEOUT_SECONDS = 300


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
    folder.mkdir(parents=True, exist_ok=True)
    dump_yaml(folder / "bundle.yaml", bundle_data)
    dump_yaml(folder / "decisions.yaml", decision_data)
    return folder


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
) -> tuple[SpecBundle, list[ArchitectureDecision]]:
    """Overlay agent slice updates onto the current approved bundle/ADRs."""
    if "bundle" in data or "architecture_decisions" in data:
        raise RuntimeError(
            "Reconcile must return slice updates, not a full bundle. "
            "Use requirement_updates / architecture_decision_updates / feature_updates / design_document_updates."
        )

    req_updates = data.get("requirement_updates") or []
    feature_updates = data.get("feature_updates") or []
    doc_updates = data.get("design_document_updates") or {}
    decision_updates = data.get("architecture_decision_updates") or []
    product_update = data.get("product_update")
    architecture_summary = data.get("architecture_summary")
    test_strategy = data.get("test_strategy")
    security_principles = data.get("security_principles")
    release_criteria = data.get("release_criteria")

    if not isinstance(req_updates, list):
        raise RuntimeError("requirement_updates must be a list")
    if not isinstance(feature_updates, list):
        raise RuntimeError("feature_updates must be a list")
    if not isinstance(decision_updates, list):
        raise RuntimeError("architecture_decision_updates must be a list")
    if not isinstance(doc_updates, dict):
        raise RuntimeError("design_document_updates must be an object")

    reqs = _index_by_id(bundle.requirements)
    for raw in req_updates:
        if not isinstance(raw, dict) or "id" not in raw:
            raise ValueError("requirement_updates entries require an id")
        rid = str(raw["id"])
        reqs[rid] = _merge_requirement(reqs.get(rid), raw)

    features = _index_by_id(bundle.features)
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
        base.update(raw)
        docs[key] = DesignDocument.model_validate(base)

    product = bundle.product
    if product_update is not None:
        if not isinstance(product_update, dict):
            raise RuntimeError("product_update must be an object")
        pdata = product.model_dump()
        pdata.update(product_update)
        product = ProductModel.model_validate(pdata)

    adr_by_id = _index_by_id(decisions)
    for raw in decision_updates:
        if not isinstance(raw, dict) or "id" not in raw:
            raise ValueError("architecture_decision_updates entries require an id")
        did = str(raw["id"])
        adr_by_id[did] = _merge_decision(adr_by_id.get(did), raw)

    # Preserve original order, append new ids at the end.
    req_order = [r.id for r in bundle.requirements] + [r for r in reqs if r not in {x.id for x in bundle.requirements}]
    feature_order = [f.id for f in bundle.features] + [f for f in features if f not in {x.id for x in bundle.features}]
    decision_order = [d.id for d in decisions] + [d for d in adr_by_id if d not in {x.id for x in decisions}]

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

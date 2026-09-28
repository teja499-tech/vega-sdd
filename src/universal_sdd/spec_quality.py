"""Reject title-only specifications that force coding agents to invent design."""
from __future__ import annotations

from .models import Feature, Requirement, SpecBundle, Task

MIN_SUMMARY = 40
MIN_DESCRIPTION = 40
MIN_STATEMENT = 20


def _too_short(value: str, minimum: int) -> bool:
    return len((value or "").strip()) < minimum


def feature_has_contracts(feature: Feature) -> bool:
    return bool(
        feature.invariants
        or feature.non_goals
        or feature.test_matrix
        or feature.api_contract.strip()
        or feature.ux_contract.strip()
    )


def spec_quality_errors(bundle: SpecBundle) -> list[str]:
    errors: list[str] = []
    if _too_short(bundle.product.summary, MIN_SUMMARY):
        errors.append("Product summary is too thin to implement against")
    if not bundle.requirements:
        errors.append("Specification bundle has no requirements")
    if not bundle.features:
        errors.append("Specification bundle has no features")
    for req in bundle.requirements:
        errors.extend(_requirement_errors(req))
    for feature in bundle.features:
        errors.extend(_feature_errors(feature))
    if not bundle.test_strategy:
        errors.append("test_strategy is required")
    return errors


def _requirement_errors(req: Requirement) -> list[str]:
    errors: list[str] = []
    if _too_short(req.statement, MIN_STATEMENT):
        errors.append(f"{req.id}: requirement statement is title-only")
    if not req.acceptance_criteria:
        errors.append(f"{req.id}: missing acceptance criteria")
    return errors


def _feature_errors(feature: Feature) -> list[str]:
    errors: list[str] = []
    if _too_short(feature.summary, MIN_SUMMARY):
        errors.append(f"{feature.id}: feature summary is title-only")
    if not feature_has_contracts(feature):
        errors.append(
            f"{feature.id}: feature needs invariants, non-goals, test matrix, or an API/UX contract"
        )
    if not feature.tasks:
        errors.append(f"{feature.id}: feature has no tasks")
    for task in feature.tasks:
        errors.extend(_task_errors(task))
    return errors


def _task_errors(task: Task) -> list[str]:
    errors: list[str] = []
    if _too_short(task.description, MIN_DESCRIPTION):
        errors.append(f"{task.id}: task description is too thin for a coding agent")
    if not task.verification:
        errors.append(f"{task.id}: task is missing verification criteria")
    if not task.implements:
        errors.append(f"{task.id}: task implements no requirements")
    return errors


def assert_spec_quality(bundle: SpecBundle) -> None:
    errors = spec_quality_errors(bundle)
    if errors:
        raise ValueError("Specification bundle is too thin:\n- " + "\n- ".join(errors))


def assert_reconcile_slice_quality(
    before: SpecBundle,
    after: SpecBundle,
    slice_data: dict,
) -> None:
    """Validate only new/updated slice items so brownfield history is not re-blocked."""
    errors: list[str] = []
    before_reqs = {r.id: r for r in before.requirements}
    before_features = {f.id: f for f in before.features}
    after_reqs = {r.id: r for r in after.requirements}
    after_features = {f.id: f for f in after.features}

    for raw in slice_data.get("requirement_updates") or []:
        if not isinstance(raw, dict) or "id" not in raw:
            continue
        rid = str(raw["id"])
        req = after_reqs.get(rid)
        if req is None:
            continue
        old = before_reqs.get(rid)
        if old is None or old.model_dump(exclude={"status"}) != req.model_dump(exclude={"status"}):
            errors.extend(_requirement_errors(req))

    for raw in slice_data.get("feature_updates") or []:
        if not isinstance(raw, dict) or "id" not in raw:
            continue
        fid = str(raw["id"])
        feature = after_features.get(fid)
        if feature is None:
            continue
        old = before_features.get(fid)
        if old is None:
            errors.extend(_feature_errors(feature))
            continue
        # Full feature replace/new tasks must meet quality; summary-only overlays on
        # historical features are allowed without rewriting contracts.
        if "tasks" in raw or old.model_dump(exclude={"status", "tasks"}) != feature.model_dump(
            exclude={"status", "tasks"}
        ):
            if not feature_has_contracts(feature) and not feature_has_contracts(old):
                # Keep historical thinness; do not invent contracts during reconcile.
                pass
            elif not feature_has_contracts(feature) and feature_has_contracts(old):
                errors.append(
                    f"{feature.id}: feature update dropped invariants/non-goals/test matrix/API/UX contract"
                )
            if _too_short(feature.summary, MIN_SUMMARY):
                errors.append(f"{feature.id}: feature summary is title-only")
        touched_task_ids = set()
        for task_raw in raw.get("tasks") or []:
            if isinstance(task_raw, dict) and "id" in task_raw:
                touched_task_ids.add(str(task_raw["id"]))
        old_tasks = {t.id: t for t in old.tasks}
        for task in feature.tasks:
            if task.id not in touched_task_ids and task.id in old_tasks:
                continue
            if task.id not in old_tasks or old_tasks[task.id].model_dump(
                exclude={"status", "attempts", "evidence", "working_set", "last_findings"}
            ) != task.model_dump(
                exclude={"status", "attempts", "evidence", "working_set", "last_findings"}
            ):
                errors.extend(_task_errors(task))

    if slice_data.get("product_update") and _too_short(after.product.summary, MIN_SUMMARY):
        errors.append("Product summary is too thin to implement against")

    if errors:
        raise ValueError("Reconcile slice is too thin:\n- " + "\n- ".join(errors))

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

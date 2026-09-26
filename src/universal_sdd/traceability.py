from __future__ import annotations

from dataclasses import dataclass, field

from .status import load_features, load_requirements
from .storage import SDDPaths


@dataclass
class TraceabilityReport:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_traceability(paths: SDDPaths) -> TraceabilityReport:
    requirements = load_requirements(paths)
    features = load_features(paths)
    errors: list[str] = []
    warnings: list[str] = []

    if not requirements or not features or not any(f.tasks for f in features):
        errors.append("Project requires nonempty requirements, features, and tasks")
    for label, ids in [("requirement", [r.id for r in requirements]),
                       ("feature", [f.id for f in features]),
                       ("task", [t.id for f in features for t in f.tasks])]:
        if len(ids) != len(set(ids)):
            errors.append(f"Duplicate {label} IDs")
    graphs = [({f.id: f.depends_on for f in features}, "feature"),
              ({t.id: t.depends_on for f in features for t in f.tasks}, "task")]
    # Feature dependencies also impose task dependencies; catch mixed deadlocks.
    combined = {t.id: list(t.depends_on) + [dt.id for df in features
                if df.id in f.depends_on for dt in df.tasks]
                for f in features for t in f.tasks}
    graphs.append((combined, "execution"))
    for graph, label in graphs:
        pending = set(graph)
        while pending:
            ready = {node for node in pending if not (set(graph[node]) & pending)}
            if not ready:
                errors.append(f"Dependency cycle in {label} graph: {sorted(pending)}")
                break
            pending -= ready

    req_ids = {r.id for r in requirements}
    feature_ids = {f.id for f in features}
    task_ids = {t.id for f in features for t in f.tasks}

    referenced_reqs: set[str] = set()
    implemented_reqs: set[str] = set()
    for feature in features:
        if not feature.tasks:
            errors.append(f"{feature.id} has no tasks")
        for dep in feature.depends_on:
            if dep not in feature_ids:
                errors.append(f"{feature.id} depends on missing feature {dep}")
        for rid in feature.requirements:
            referenced_reqs.add(rid)
            if rid not in req_ids:
                errors.append(f"{feature.id} references missing requirement {rid}")
        for task in feature.tasks:
            if task.feature_id != feature.id:
                errors.append(f"{task.id} feature_id is {task.feature_id}, expected {feature.id}")
            for dep in task.depends_on:
                if dep not in task_ids:
                    errors.append(f"{task.id} depends on missing task {dep}")
            for rid in task.implements:
                implemented_reqs.add(rid)
                if rid not in req_ids:
                    errors.append(f"{task.id} implements missing requirement {rid}")
            if not task.verification:
                warnings.append(f"{task.id} has no explicit verification criteria")

    for req in requirements:
        if req.priority == "must" and req.id not in referenced_reqs:
            errors.append(f"MUST requirement {req.id} is not assigned to a feature")
        if req.priority == "must" and req.id not in implemented_reqs:
            errors.append(f"MUST requirement {req.id} is not mapped to any task")
        if not req.acceptance_criteria:
            errors.append(f"{req.id} has no acceptance criteria")

    return TraceabilityReport(ok=not errors, errors=errors, warnings=warnings)

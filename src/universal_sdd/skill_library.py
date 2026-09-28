"""Discover and route operational runbooks without loading the whole catalog."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

ROLE_FILES = {
    "planner.md": """# Planner

Turn approved requirements and architecture into bounded, dependency-aware work. Do not invent product intent.

## Workflow
1. Trace every task to requirement and acceptance criteria.
2. Keep tasks independently reviewable and small enough for one agent pass.
3. Name required skills and deterministic checks.
4. Surface ambiguity as a clarification instead of burying it in a task.

## Failure modes
- Title-only tasks with no behavioral contract.
- One task spanning unrelated subsystems.
- Tests deferred to a later cleanup task.
""",
    "architect.md": """# Architect

Protect approved product intent and architecture. You classify concerns; you do not silently rewrite specs.

## Authority
- Facts: PRD, `.sdd/product/`, ADRs, current implementation evidence.
- Decisions: only those recorded as selected in `.sdd/architecture/`.
- Changes: requirement or architecture mutations need `sdd change` plus explicit approval.

## Workflow
1. Restate the question against current specs and ADRs.
2. Separate fact, approved decision, assumption, and proposal.
3. If the user wants a mutation, list affected requirements, features, and tasks before editing anything.
4. Never mark tasks complete. The controller owns `.sdd/state/`.

## Failure modes
- Inventing a missing product rule instead of opening a clarification.
- Matching the spec to incorrect code.
- Answering from repository folklore when an ADR already decided the question.
""",
    "developer.md": """# Developer

Implement exactly one bounded SDD task.

## Authority
- Input: the controller context pack (task card, AC, working set, last findings).
- Output: working-tree edits plus tests. No git commits. No `.sdd/` edits.

## Workflow
1. Load only the skill named in the pack. Do not walk the repository first.
2. Query Graphify before Read or Grep when `graphify-out/graph.json` exists.
3. Read the working-set files and the feature contracts.
4. Make the smallest cohesive change that satisfies verification.
5. Run the narrowest check command from the pack.

## Failure modes
- Editing specs to hide an implementation defect.
- Broad refactors outside the task boundary.
- Weakening tests so a failing implementation passes.
""",
    "qa-engineer.md": """# QA Engineer

Independently verify acceptance criteria. Developer claims are not evidence.

## Workflow
1. Diff first, then the listed tests, then only the working-set files.
2. Map each acceptance criterion to a test or explicit gap.
3. Severity: `critical`/`high`/`medium` only when AC, security, or data integrity is broken.
4. `low`/`warning` nits must not fail the task.

## Output
Return JSON only. No file writes. No speculative redesign.
""",
    "security-reviewer.md": """# Security Reviewer

Review trust boundaries for the bounded change only.

## Checklist
- Authn/authz on every new route or tool.
- Secrets stay in env / secret manager; never in git or logs.
- Input validation, injection, SSRF, path traversal.
- Least privilege for new dependencies and jobs.
- Data exposure in errors, traces, and exports.

Return findings with severity and a concrete repair. Do not invent a threat model that contradicts `.sdd/docs/SECURITY.md`.
""",
    "spec-reviewer.md": """# Spec Reviewer

Trace requirement → acceptance criterion → feature → task → test → evidence.

## Fail when
- A MUST requirement has no task.
- A task has no testable verification.
- Implementation invents product behavior not in the spec.
- Spec text is title-only (no invariants, contracts, or test matrix).

Do not approve thin specs. Send them back through `sdd change` or spec regeneration.
""",
    "integration-reviewer.md": """# Integration Reviewer

Check contracts across modules, migrations, compatibility, and operations.

## Checklist
- Request/response and event schemas match the API contract.
- Migrations are forward-safe and have a rollback note.
- Feature flags or compatibility windows exist for breaking changes.
- Runbooks mention the new failure mode.
""",
    "reliability-reviewer.md": """# Reliability Reviewer

Review retries, timeouts, idempotency, cancellation, concurrency, and degraded modes for the bounded change.

## Checklist
- Every external operation has an explicit timeout and bounded retry policy.
- Retried mutations are idempotent or carry a stable operation key.
- Cancellation and partial failure leave durable state recoverable.
- Fallbacks are observable and do not silently weaken correctness.

Return evidence-backed findings only. Do not redesign unrelated components.
""",
    "performance-reviewer.md": """# Performance Reviewer

Review performance claims and resource bounds for the bounded change.

## Checklist
- A representative benchmark or load test supports material latency/throughput claims.
- Queries, loops, queues, payloads, and caches have explicit bounds.
- Optimizations preserve correctness and include a regression test where practical.
- Report measurements with environment and workload; never invent results.
""",
    "agent-system-reviewer.md": """# Agent System Reviewer

Review LLM and agent boundaries from prompt assembly through tools, memory, retries, evaluation, and rendering.

## Checklist
- Tool authority is controller-enforced, least-privilege, and independent of model claims.
- Structured output is validated before state changes.
- Memory and retrieval preserve tenant/session boundaries and resist prompt injection.
- Retry/repair loops are bounded, observable, and do not hide failures.
- Deterministic and adversarial evals cover the changed behavior.
""",
    "e2e-runner.md": """# End-to-End Reviewer

Verify critical user journeys at the system boundary using the project's approved E2E tooling.

## Workflow
1. Map acceptance criteria to user journeys and stable assertions.
2. Prefer semantic selectors and condition-based waits.
3. Keep tests isolated and capture useful failure artifacts.
4. Treat flaky tests as defects; do not hide them with unbounded retries.

Do not claim a journey passed unless the configured command produced evidence.
""",
}


def _load_skills() -> dict[str, str]:
    root = Path(__file__).resolve().parent / "skill_texts"
    loaded: dict[str, str] = {}
    for path in sorted(root.glob("*/SKILL.md")):
        loaded[f"{path.parent.name}/SKILL.md"] = path.read_text(encoding="utf-8")
    if not loaded:
        raise RuntimeError(f"No skill runbooks found under {root}")
    return loaded


SKILLS = _load_skills()


@dataclass(frozen=True)
class SkillInfo:
    name: str
    description: str
    text: str
    path: Path | None
    phases: tuple[str, ...] = ()
    triggers: tuple[str, ...] = ()
    excludes: tuple[str, ...] = ()


_SAFE_CAPABILITY = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def _metadata(text: str) -> dict:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end < 0:
        return {}
    try:
        value = yaml.safe_load(text[4:end]) or {}
    except yaml.YAMLError:
        return {}
    return value if isinstance(value, dict) else {}


def _skill_info(name: str, text: str, path: Path | None) -> SkillInfo:
    meta = _metadata(text)
    declared = str(meta.get("name") or name).strip()
    if not _SAFE_CAPABILITY.fullmatch(declared):
        declared = name
    routing = meta.get("routing") or {}
    if not isinstance(routing, dict):
        routing = {}
    description = re.sub(r"\s+", " ", str(meta.get("description") or "Load this skill when the task matches its name.")).strip()
    return SkillInfo(
        name=declared,
        description=description[:400],
        text=text,
        path=path,
        phases=tuple(str(x) for x in (routing.get("phases") or [])),
        triggers=tuple(str(x).lower() for x in (routing.get("any") or [])),
        excludes=tuple(str(x).lower() for x in (routing.get("exclude") or [])),
    )


def discover_skills(root: Path | None = None) -> dict[str, SkillInfo]:
    """Merge packaged skills with project-local skills; local files are authoritative."""
    result = {
        rel.split("/", 1)[0]: _skill_info(rel.split("/", 1)[0], text, None)
        for rel, text in SKILLS.items()
    }
    if root is not None:
        local = Path(root) / ".agents" / "skills"
        if local.exists():
            for path in sorted(local.glob("*/SKILL.md")):
                name = path.parent.name
                if not _SAFE_CAPABILITY.fullmatch(name):
                    continue
                text = path.read_text(encoding="utf-8")
                info = _skill_info(name, text, path)
                if info.name == name:
                    result[name] = info
    return result


def _triggered(info: SkillInfo, blob: str, phase: str) -> bool:
    if not info.phases or phase not in info.phases or not info.triggers:
        return False
    if any(term and term in blob for term in info.excludes):
        return False
    for term in info.triggers:
        if not term:
            continue
        if re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", blob):
            return True
    return False


def routed_skills(root: Path | None, phase: str, text: str) -> list[str]:
    catalog = discover_skills(root)
    blob = text.lower()
    return [name for name, info in catalog.items() if _triggered(info, blob, phase)]

LIFECYCLE_SKILLS = {
    "implement": "implement-task",
    "review": "review-task",
    "repair": "implement-task",
    "architecture": "architecture-design",
    "spec": "create-feature-spec",
    "reconcile": "reconcile",
    "change": "spec-drift",
    "verify": "verify-feature",
}


def lifecycle_skill(phase: str) -> str:
    return LIFECYCLE_SKILLS[phase]


def skill_summary(name: str, root: Path | None = None) -> str:
    """Frontmatter description only. Full runbooks stay on disk until the agent loads them."""
    info = discover_skills(root).get(name)
    return info.description if info else "Missing skill: controller must fail before agent execution."


def skill_catalog(*names: str, root: Path | None = None) -> str:
    catalog = discover_skills(root)
    lines = []
    for name in names:
        if not name:
            continue
        lines.append(
            f"- {name}: {catalog.get(name).description if name in catalog else 'Missing skill: controller must fail before agent execution.'} "
            f"— read `.agents/skills/{name}/SKILL.md` only if this phase matches."
        )
    return "\n".join(lines)


def available_task_skills(root: Path | None = None) -> str:
    """Safe init-time catalog; project-local bodies are not injected before approval."""
    lifecycle = set(LIFECYCLE_SKILLS.values())
    packaged = {
        rel.split("/", 1)[0]: _skill_info(rel.split("/", 1)[0], text, None)
        for rel, text in SKILLS.items()
    }
    lines = [
        f"- {name}: {info.description} — use only when the task materially matches."
        for name, info in packaged.items()
        if name not in lifecycle
    ]
    if root is not None:
        local_names = sorted(set(discover_skills(root)) - set(packaged))
        lines.extend(
            f"- {name}: project-local runbook; select only when the PRD explicitly names it. "
            "Its body is intentionally withheld until capability approval."
            for name in local_names
        )
    return "\n".join(lines)


def roles_for_phase(phase: str, skills: list[str]) -> tuple[str, list[str]]:
    primary = "qa-engineer" if phase == "review" else "developer"
    if phase in {"architecture", "change", "reconcile"}:
        primary = "architect"
    elif phase == "spec":
        primary = "planner"
    extras: list[str] = []
    selected = set(skills)
    if selected & {"api-design", "data-model", "migration-safety", "e2e-testing"} and phase == "review":
        extras.append("integration-reviewer")
    mapping = {
        "security-review": "security-reviewer",
        "threat-model": "security-reviewer",
        "reliability-review": "reliability-reviewer",
        "performance-review": "performance-reviewer",
        "agent-system-review": "agent-system-reviewer",
        "e2e-testing": "e2e-runner",
    }
    if phase == "review":
        extras.extend(mapping[name] for name in skills if name in mapping)
    return primary, list(dict.fromkeys(extras))


def role_catalog(primary: str, extras: list[str] = ()) -> str:
    names = [primary, *extras]
    lines = []
    for name in names:
        text = ROLE_FILES.get(f"{name}.md", "")
        summary = next((line.strip() for line in text.splitlines()[2:] if line.strip()), "Repository role contract")
        lines.append(f"- {name}: {summary} — read `.agents/roles/{name}.md`.")
    return "\n".join(lines)

from __future__ import annotations

from pathlib import Path

from .skill_library import ROLE_FILES, SKILLS
from .storage import SDDPaths

AGENTS_MD = """<!-- UNIVERSAL_SDD_START -->
# Vega SDD Project Instructions

This repository uses Spec Driven Development (SDD).

## Sources of truth
- Product intent: `.sdd/product/`
- Architecture and ADRs: `.sdd/architecture/` and `.sdd/decisions/`
- Feature specifications: `.sdd/specs/`
- Canonical execution state: `.sdd/state/`
- Reusable workflows: `.agents/skills/`

## Non-negotiable agent rules
1. Never invent product requirements.
2. Never silently change approved requirements or architecture.
3. Implement only the bounded task supplied by the SDD controller.
4. Acceptance criteria must map to deterministic verification wherever practical.
5. Do not mark SDD tasks complete yourself; the controller owns canonical state.
6. If implementation exposes a requirement or architecture ambiguity, surface it as a blocker/escalation.
7. Do not weaken tests to make a failing implementation pass.
8. Significant architecture changes require an ADR and explicit user approval.
9. Prefer repository skills for established workflows. Load only the skill named in the controller context pack.
10. Leave the repository in a recoverable state.
11. Ask project questions with `sdd ask`. Mutate the plan with `sdd change`. Do not invent product rules.
<!-- UNIVERSAL_SDD_END -->
"""

TEMPLATES = {
    "feature-spec.md": "# {feature_id} — {feature_name}\n\n## Summary\n\n## Invariants\n\n## Non-goals\n\n## Requirements\n\n## Acceptance Criteria\n\n## API contract\n\n## UX contract\n\n## Test matrix\n\n## Target files\n\n## Dependencies\n\n## Tasks\n",
    "adr.md": "# {adr_id} — {title}\n\n## Status\nAccepted\n\n## Context\n\n## Options Considered\n\n## Decision\n\n## Consequences\n",
    "evidence.md": "# Verification Evidence\n\n## Requirement / Acceptance Criterion\n\n## Evidence\n\n## Result\n",
}


CURSOR_COMMANDS = {
    "sdd-ask.md": "# SDD Ask\n\nAnswer a project question using approved specs, ADRs, and `graphify query` when `graphify-out/graph.json` exists.\nRun `sdd ask \"<question>\"` in the project root. Do not mutate files.\n",
    "sdd-change.md": "# SDD Change\n\nTurn an ad-hoc request into a classified change with an invalidation preview.\nRun `sdd change \"<request>\"` and approve only after reviewing affected tasks.\n",
}

CURSOR_RULE = "---\ndescription: Vega SDD repository contract\nalwaysApply: true\n---\nFollow `AGENTS.md`. Treat `.sdd/state/` as canonical execution state and `.sdd/specs/` as approved feature intent. Load only task-relevant skills from `.agents/skills/`.\nAsk project questions with `sdd ask`. Propose plan changes with `sdd change`.\n"


def _is_stub(path: Path) -> bool:
    if not path.exists():
        return True
    text = path.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line.strip() and not line.startswith("---") and "name:" not in line and "description:" not in line]
    return len(lines) <= 8


def _is_previous_checklist(path: Path, content: str) -> bool:
    """Upgrade framework skills that predate the failure-mode runbooks.

    Files without the shipped YAML frontmatter are treated as local customizations.
    """
    if path.name != "SKILL.md" or "## Failure modes" not in content:
        return False
    current = path.read_text(encoding="utf-8")
    if "## Failure modes" in current or not current.startswith("---\n"):
        return False
    return True


def _write_if_needed(path: Path, content: str, *, overwrite: bool) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(content, encoding="utf-8")
        return "added"
    if overwrite or _is_stub(path) or _is_previous_checklist(path, content):
        if path.read_text(encoding="utf-8") == content:
            return "unchanged"
        path.write_text(content, encoding="utf-8")
        return "updated"
    return "kept"


def write_scaffold(root: Path, *, refresh: bool = False, force: bool = False) -> SDDPaths:
    refresh_scaffold(root, refresh=refresh, force=force)
    return SDDPaths(root)


def refresh_scaffold(root: Path, *, refresh: bool = False, force: bool = False) -> dict[str, list[str]]:
    paths = SDDPaths(root)
    paths.ensure()
    report = {"added": [], "updated": [], "kept": [], "unchanged": []}

    def note(rel: str, action: str) -> None:
        report[action].append(rel)

    agents_file = root / "AGENTS.md"
    if not agents_file.exists():
        agents_file.write_text(AGENTS_MD, encoding="utf-8")
        note("AGENTS.md", "added")
    else:
        current = agents_file.read_text(encoding="utf-8")
        if "<!-- UNIVERSAL_SDD_START -->" not in current:
            agents_file.write_text(current.rstrip() + "\n\n" + AGENTS_MD, encoding="utf-8")
            note("AGENTS.md", "updated")
        elif refresh and "sdd ask" not in current:
            start = current.find("<!-- UNIVERSAL_SDD_START -->")
            end = current.find("<!-- UNIVERSAL_SDD_END -->")
            if start >= 0 and end >= start:
                agents_file.write_text(current[:start] + AGENTS_MD + current[end + len("<!-- UNIVERSAL_SDD_END -->"):], encoding="utf-8")
                note("AGENTS.md", "updated")

    for name, content in ROLE_FILES.items():
        rel = f".agents/roles/{name}"
        note(rel, _write_if_needed(paths.roles / name, content, overwrite=force))
        for vendor in (".cursor", ".claude", ".codex"):
            adapter = root / vendor / "agents" / name
            vendor_text = content + "\nCanonical SDD sources: `AGENTS.md`, `.sdd/`, and `.agents/`.\n"
            note(f"{vendor}/agents/{name}", _write_if_needed(adapter, vendor_text, overwrite=force))

    claude_md = root / "CLAUDE.md"
    if not claude_md.exists():
        claude_md.write_text("# Claude Code SDD Adapter\n\nFollow `AGENTS.md`. Canonical product/spec/state lives under `.sdd/`; reusable workflows live under `.agents/skills/`. Do not create Claude-only product requirements.\n", encoding="utf-8")
        note("CLAUDE.md", "added")
    cursor_rule = root / ".cursor" / "rules" / "vega-sdd.mdc"
    note(".cursor/rules/vega-sdd.mdc", _write_if_needed(cursor_rule, CURSOR_RULE, overwrite=refresh or force))
    for name, content in CURSOR_COMMANDS.items():
        note(f".cursor/commands/{name}", _write_if_needed(root / ".cursor" / "commands" / name, content, overwrite=refresh or force))

    for rel, content in SKILLS.items():
        note(f".agents/skills/{rel}", _write_if_needed(paths.skills / rel, content, overwrite=force))
    for name, content in TEMPLATES.items():
        note(f".sdd/templates/{name}", _write_if_needed(paths.templates / name, content, overwrite=force))
    return {key: value for key, value in report.items() if value}

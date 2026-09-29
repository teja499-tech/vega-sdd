from __future__ import annotations

import json
import os
import re
import shutil
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from .models import ArchitectureDecision, Feature, SpecBundle
from .storage import SDDPaths, dump_json, dump_yaml, load_yaml

_PROJECTION_TX = ContextVar("sdd_projection_tx", default=False)

_SKIP_SDD_DIRS = {"runtime", "journal", "evidence", "recovery", "artifacts"}
_SKIP_STATE_FILES = {"project.yaml"}


def _md_list(items: list[str]) -> str:
    return "\n".join(f"- {x}" for x in items) if items else "- None"


def _tx_root(paths: SDDPaths) -> Path:
    return paths.runtime / "projection-tx"


def _canonical_files(paths: SDDPaths) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    roots = [paths.sdd]
    corpus = paths.root / "graphify-corpus"
    if corpus.exists():
        roots.append(corpus)
    for base in roots:
        for folder, dirs, names in os.walk(base):
            dirs[:] = [d for d in dirs if d not in _SKIP_SDD_DIRS and d != ".git"]
            for name in names:
                if name in _SKIP_STATE_FILES and Path(folder).name == "state":
                    continue
                path = Path(folder) / name
                if not path.is_file():
                    continue
                rel = path.relative_to(paths.root).as_posix()
                files[rel] = path.read_bytes()
    return files


def _restore_canonical(paths: SDDPaths, snapshot: dict[str, bytes]) -> None:
    current = _canonical_files(paths)
    for rel, content in snapshot.items():
        path = paths.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    for rel in current:
        if rel in snapshot:
            continue
        path = paths.root / rel
        if path.is_file():
            path.unlink()


def _persist_tx(paths: SDDPaths, snapshot: dict[str, bytes]) -> None:
    base = _tx_root(paths)
    if base.exists():
        shutil.rmtree(base)
    files_dir = base / "files"
    files_dir.mkdir(parents=True, exist_ok=True)
    for rel, content in snapshot.items():
        dest = files_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
    dump_json(base / "active.json", {"active": True, "files": sorted(snapshot)})


def _load_persisted_tx(paths: SDDPaths) -> dict[str, bytes] | None:
    marker = _tx_root(paths) / "active.json"
    if not marker.exists():
        return None
    if marker.is_symlink():
        raise ValueError("Projection transaction marker must not be a symlink")
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("Projection transaction marker is corrupt") from exc
    if not isinstance(data, dict):
        raise ValueError("Projection transaction marker must be an object")
    if not data.get("active"):
        return None
    snapshot: dict[str, bytes] = {}
    files_dir = _tx_root(paths) / "files"
    for rel in data.get("files") or []:
        if not isinstance(rel, str):
            raise ValueError("Projection transaction contains a non-string path")
        relative = Path(rel)
        allowed_root = relative.parts[:1] in {(".sdd",), ("graphify-corpus",)}
        excluded = rel == ".sdd/state/project.yaml" or any(
            rel.startswith(f".sdd/{name}/") for name in _SKIP_SDD_DIRS
        )
        if relative.is_absolute() or ".." in relative.parts or not allowed_root or excluded:
            raise ValueError(f"Unsafe projection transaction path: {rel}")
        path = files_dir
        for part in relative.parts:
            path = path / part
            if path.is_symlink():
                raise ValueError(f"Projection transaction path is a symlink: {rel}")
        if not path.is_file():
            raise ValueError(f"Projection transaction snapshot is incomplete: {rel}")
        snapshot[rel] = path.read_bytes()
    return snapshot


def _clear_tx(paths: SDDPaths) -> None:
    base = _tx_root(paths)
    if base.exists():
        shutil.rmtree(base)


def recover_projection_transaction(paths: SDDPaths) -> bool:
    """Restore a crashed projection write if a durable transaction marker remains."""
    if not paths.sdd.exists():
        return False
    try:
        snapshot = _load_persisted_tx(paths)
    except (OSError, ValueError, TypeError) as exc:
        # Preserve the only rollback evidence. An owner must inspect/remove the
        # transaction rather than letting later writes compound partial state.
        raise RuntimeError(f"Projection recovery blocked: {exc}") from exc
    if snapshot is None:
        return False
    _restore_canonical(paths, snapshot)
    _clear_tx(paths)
    return True


@contextmanager
def projection_transaction(paths: SDDPaths):
    """Durable stage-or-rollback journal for every canonical projection."""
    if _PROJECTION_TX.get():
        yield
        return
    recover_projection_transaction(paths)
    snapshot = _canonical_files(paths)
    _persist_tx(paths, snapshot)
    token = _PROJECTION_TX.set(True)
    try:
        yield
    except BaseException:
        _restore_canonical(paths, snapshot)
        _clear_tx(paths)
        raise
    else:
        _clear_tx(paths)
    finally:
        _PROJECTION_TX.reset(token)


def _decision_projection_path(paths: SDDPaths, decision: ArchitectureDecision) -> Path:
    return paths.decisions / f"{decision.id.lower()}-{decision.category.replace('_','-')}.md"


def _feature_projection_path(paths: SDDPaths, feature: Feature) -> Path:
    slug = re.sub(r"[^a-z0-9_-]+", "-", feature.name.lower())
    return paths.specs / f"{feature.id}-{slug}"


def _remove_generated_projection(path: Path, parent: Path) -> None:
    """Remove known generated content without deleting unexpected user-authored files."""
    if path.parent.resolve() != parent.resolve():
        raise ValueError(f"Unsafe generated projection path: {path}")
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        for name in ("spec.md", "tasks.md", "state.yaml"):
            generated = path / name
            if generated.is_symlink() or generated.is_file():
                generated.unlink()
        try:
            path.rmdir()
        except OSError:
            # Preserve the directory when it contains anything the projection
            # renderer does not explicitly own.
            pass


def _render_architecture(paths: SDDPaths, decisions: list[ArchitectureDecision]) -> None:
    prior = [
        ArchitectureDecision.model_validate(item)
        for item in (load_yaml(paths.architecture_decisions_file, []) or [])
    ]
    expected = {_decision_projection_path(paths, item) for item in decisions}
    for item in prior:
        old_path = _decision_projection_path(paths, item)
        if old_path not in expected:
            _remove_generated_projection(old_path, paths.decisions)
    dump_yaml(paths.architecture_decisions_file, decisions)
    index_lines = ["# Architecture Decisions", ""]
    for decision in decisions:
        selected = decision.selected or decision.recommendation or "Deferred"
        index_lines.append(f"- **{decision.id} — {decision.category}:** {selected}")
        adr = _decision_projection_path(paths, decision)
        option_text = []
        for option in decision.options:
            option_text.append(
                f"### {option.name}\n{option.summary}\n\n**Strengths**\n{_md_list(option.strengths)}\n\n**Tradeoffs**\n{_md_list(option.tradeoffs)}\n\nFit: {option.fit or 'not rated'}"
            )
        options_markdown = "\n\n".join(option_text)
        adr.write_text(
            f"# {decision.id} — {decision.category.replace('_',' ').title()}\n\n"
            f"## Status\n{decision.status.value}\n\n"
            f"## Context\n{decision.rationale}\n\n"
            f"## Decision Question\n{decision.question}\n\n"
            f"## Options Considered\n\n{options_markdown}\n\n"
            f"## Recommendation\n{decision.recommendation or 'None'}\n\n{decision.recommendation_reason}\n\n"
            f"## Approved Decision\n{decision.selected or 'Deferred'}\n\n"
            f"## Decision Reason\n{decision.selected_reason or 'Not recorded'}\n",
            encoding="utf-8",
        )
    (paths.architecture / "decisions.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")


def write_architecture(paths: SDDPaths, decisions: list[ArchitectureDecision]) -> None:
    with projection_transaction(paths):
        _render_architecture(paths, decisions)


def _render_spec_bundle(
    paths: SDDPaths,
    bundle: SpecBundle,
    *,
    preserve_verification: bool = False,
    enforce_quality: bool = True,
) -> None:
    from .spec_quality import assert_spec_quality
    if enforce_quality:
        assert_spec_quality(bundle)
    previous_data = load_yaml(paths.spec_bundle_file, {}) or {}
    prior_features = [Feature.model_validate(item) for item in previous_data.get("features", [])]
    expected_feature_dirs = {_feature_projection_path(paths, item) for item in bundle.features}
    for item in prior_features:
        old_path = _feature_projection_path(paths, item)
        if old_path not in expected_feature_dirs:
            _remove_generated_projection(old_path, paths.specs)
    product = bundle.product
    (paths.product / "vision.md").write_text(
        f"# {product.name}\n\n{product.summary}\n\n## Users\n{_md_list(product.users)}\n\n## Capabilities\n{_md_list(product.capabilities)}\n",
        encoding="utf-8",
    )
    (paths.product / "workflows.md").write_text("# Workflows\n\n" + _md_list(product.workflows) + "\n", encoding="utf-8")
    (paths.product / "constraints.md").write_text(
        "# Constraints\n\n" + _md_list(product.constraints) + "\n\n# Assumptions\n\n" + _md_list(product.assumptions) + "\n",
        encoding="utf-8",
    )
    (paths.product / "open-questions.md").write_text("# Open Questions\n\n" + _md_list(product.open_questions) + "\n", encoding="utf-8")

    req_lines = ["# Requirements", ""]
    for r in bundle.requirements:
        req_lines += [
            f"## {r.id} — {r.title}",
            "",
            r.statement,
            "",
            f"- Type: {r.kind}",
            f"- Priority: {r.priority}",
            f"- Source: {r.source}",
            "",
            "### Acceptance Criteria",
            _md_list(r.acceptance_criteria),
            "",
        ]
    (paths.product / "requirements.md").write_text("\n".join(req_lines), encoding="utf-8")

    (paths.architecture / "system.md").write_text(
        "# System Architecture\n\n" + bundle.architecture_summary + "\n\n## Security Principles\n" + _md_list(bundle.security_principles) + "\n",
        encoding="utf-8",
    )
    (paths.sdd / "test-strategy.md").write_text("# Test Strategy\n\n" + _md_list(bundle.test_strategy) + "\n", encoding="utf-8")
    (paths.sdd / "release-criteria.md").write_text("# Release Criteria\n\n" + _md_list(bundle.release_criteria) + "\n", encoding="utf-8")

    roadmap = ["# Roadmap", ""]
    for feature in bundle.features:
        feature_dir = _feature_projection_path(paths, feature)
        feature_dir.mkdir(parents=True, exist_ok=True)
        roadmap.append(f"- [ ] {feature.id} — {feature.name} (depends on: {', '.join(feature.depends_on) or 'none'})")
        task_lines = ["# Tasks", ""]
        for task in feature.tasks:
            task_lines += [
                f"## {task.id} — {task.title}",
                "",
                task.description,
                "",
                f"- Implements: {', '.join(task.implements) or 'none'}",
                f"- Depends on: {', '.join(task.depends_on) or 'none'}",
                f"- Skills: {', '.join(task.skills) or 'controller-routed defaults'}",
                f"- Verification: {', '.join(task.verification) or 'not specified'}",
                "",
            ]
        (feature_dir / "spec.md").write_text(
            f"# {feature.id} — {feature.name}\n\n{feature.summary}\n\n"
            f"## Invariants\n{_md_list(feature.invariants)}\n\n"
            f"## Non-goals\n{_md_list(feature.non_goals)}\n\n"
            f"## Requirements\n{_md_list(feature.requirements)}\n\n"
            f"## API contract\n\n{feature.api_contract or 'Not applicable'}\n\n"
            f"## UX contract\n\n{feature.ux_contract or 'Not applicable'}\n\n"
            f"## Test matrix\n{_md_list(feature.test_matrix)}\n\n"
            f"## Target files\n{_md_list(feature.target_files)}\n\n"
            f"## Dependencies\n{_md_list(feature.depends_on)}\n",
            encoding="utf-8",
        )
        (feature_dir / "tasks.md").write_text("\n".join(task_lines), encoding="utf-8")
        dump_yaml(feature_dir / "state.yaml", feature)
    (paths.sdd / "roadmap.md").write_text("\n".join(roadmap) + "\n", encoding="utf-8")

    from .project_graph import refresh_graph
    dump_yaml(paths.requirements_file, bundle.requirements)
    dump_yaml(paths.features_file, bundle.features)
    dump_yaml(paths.spec_bundle_file, bundle)
    refresh_graph(paths)
    if not preserve_verification or not paths.verification_file.exists():
        dump_yaml(paths.verification_file, [])
    from .documentation import render_docs
    from .history import snapshot_specs, render_history
    snapshot_specs(paths)
    render_docs(paths)
    render_history(paths)


def write_spec_bundle(
    paths: SDDPaths,
    bundle: SpecBundle,
    *,
    preserve_verification: bool = False,
    enforce_quality: bool = True,
) -> None:
    with projection_transaction(paths):
        _render_spec_bundle(
            paths,
            bundle,
            preserve_verification=preserve_verification,
            enforce_quality=enforce_quality,
        )


def project_context(paths: SDDPaths, max_chars: int = 30000) -> str:
    chunks: list[str] = []
    candidates = [
        paths.product / "vision.md",
        paths.product / "requirements.md",
        paths.architecture / "system.md",
        paths.architecture / "decisions.md",
        paths.sdd / "roadmap.md",
        paths.status_file,
    ]
    for path in candidates:
        if path.exists():
            chunks.append(f"\n## {path.relative_to(paths.root)}\n{path.read_text(encoding='utf-8')}")
    text = "\n".join(chunks)
    return text[:max_chars]

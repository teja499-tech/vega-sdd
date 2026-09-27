"""Material questions must be resolved or explicitly accepted before start."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .models import ArchitectureDecision, DecisionStatus, ProductModel
from .storage import SDDPaths, dump_yaml, load_yaml


class Clarification(BaseModel):
    id: str
    question: str
    answer: str = ""
    status: Literal["open", "answered", "deferred", "accepted_default"] = "open"
    source: Literal["product", "architecture"] = "product"


def clarifications_file(paths: SDDPaths):
    return paths.product / "clarifications.yaml"


def load_clarifications(paths: SDDPaths) -> list[Clarification]:
    rows = load_yaml(clarifications_file(paths), []) or []
    return [Clarification.model_validate(row) for row in rows]


def save_clarifications(paths: SDDPaths, items: list[Clarification]) -> None:
    dump_yaml(clarifications_file(paths), items)
    lines = ["# PRD Clarifications", ""]
    for item in items:
        lines += [f"## {item.id}", "", item.question, "", f"**Status:** {item.status}", "", item.answer or "_No answer recorded._", ""]
    (paths.product / "clarifications.md").write_text("\n".join(lines), encoding="utf-8")


def record_product_questions(paths: SDDPaths, product: ProductModel, answers: list[tuple[str, str]]) -> list[Clarification]:
    items: list[Clarification] = []
    for index, (question, answer) in enumerate(answers, 1):
        text = (answer or "").strip()
        lowered = text.lower()
        if not text or lowered in {"defer", "deferred"}:
            status: Literal["open", "answered", "deferred", "accepted_default"] = "deferred"
            text = text or "Deferred"
        else:
            status = "answered"
        items.append(Clarification(id=f"Q{index}", question=question, answer=text, status=status, source="product"))
    remaining = product.open_questions[len(answers):]
    for offset, question in enumerate(remaining, len(items) + 1):
        items.append(Clarification(id=f"Q{offset}", question=question, status="open", source="product"))
    save_clarifications(paths, items)
    return items


def record_architecture_decisions(paths: SDDPaths, decisions: list[ArchitectureDecision]) -> list[Clarification]:
    items = [c for c in load_clarifications(paths) if c.source != "architecture"]
    for decision in decisions:
        if decision.status != DecisionStatus.deferred:
            continue
        items.append(
            Clarification(
                id=decision.id,
                question=decision.question,
                answer="Deferred during architecture workshop",
                status="deferred",
                source="architecture",
            )
        )
    save_clarifications(paths, items)
    return items


def unresolved_material(paths: SDDPaths) -> list[Clarification]:
    return [item for item in load_clarifications(paths) if item.status in {"open", "deferred"}]


def answer_clarification(paths: SDDPaths, clarification_id: str, answer: str) -> Clarification:
    items = load_clarifications(paths)
    target = None
    for item in items:
        if item.id == clarification_id:
            item.answer = answer
            item.status = "answered"
            target = item
            break
    if target is None:
        raise ValueError(f"Unknown clarification: {clarification_id}")
    save_clarifications(paths, items)
    return target


def assert_start_ready(paths: SDDPaths, *, accept_deferred: bool = False) -> None:
    from .storage import load_config

    config = load_config(paths)
    if not config.require_resolved_clarifications:
        return
    unresolved = unresolved_material(paths)
    if not unresolved:
        return
    if accept_deferred:
        updated: list[Clarification] = []
        for item in load_clarifications(paths):
            if item.status == "deferred":
                item = item.model_copy(
                    update={
                        "status": "accepted_default",
                        "answer": item.answer or "Accepted deferred default at start",
                    }
                )
            updated.append(item)
        save_clarifications(paths, updated)
        leftover = unresolved_material(paths)
        if leftover:
            raise RuntimeError(_block_message(leftover) + "\nOpen questions still need answers.")
        return
    raise RuntimeError(_block_message(unresolved))


def _block_message(items: list[Clarification]) -> str:
    lines = [
        "Material clarifications are unresolved. Answer them with `sdd clarify` "
        "or pass `--accept-deferred` to start with signed defaults:",
    ]
    for item in items:
        lines.append(f"- {item.id} ({item.source}/{item.status}): {item.question}")
    return "\n".join(lines)

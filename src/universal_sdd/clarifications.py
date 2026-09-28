"""Material questions must be resolved or explicitly accepted before start."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .models import ArchitectureDecision, DecisionStatus, ProductModel
from .storage import SDDPaths, dump_yaml, load_yaml


PLACEHOLDER_ANSWERS = {
    "",
    "defer",
    "deferred",
    "deferred during architecture workshop",
    "accepted deferred default at start",
}


class Clarification(BaseModel):
    id: str
    question: str
    answer: str = ""
    status: Literal["open", "answered", "deferred", "accepted_default"] = "open"
    source: Literal["product", "architecture"] = "product"
    default_option: str = ""


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


def load_decisions(paths: SDDPaths) -> list[ArchitectureDecision]:
    rows = load_yaml(paths.architecture_decisions_file, []) or []
    return [ArchitectureDecision.model_validate(row) for row in rows]


def default_option_for(decision: ArchitectureDecision) -> str | None:
    if decision.selected:
        return decision.selected
    if decision.recommendation:
        return decision.recommendation
    if decision.options:
        return decision.options[0].name
    return None


def _placeholder(text: str) -> bool:
    return (text or "").strip().lower() in PLACEHOLDER_ANSWERS


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
                default_option=default_option_for(decision) or "",
            )
        )
    save_clarifications(paths, items)
    return items


def merge_open_questions(paths: SDDPaths, questions: list[str], *, source: Literal["product", "architecture"] = "product") -> list[Clarification]:
    """Deduplicate later-phase questions into the canonical clarification store."""
    items = load_clarifications(paths)
    existing = {item.question.strip().lower() for item in items if item.question.strip()}
    used_ids = {item.id for item in items}

    def next_product_id() -> str:
        nums = []
        for item in items:
            if item.id.startswith("Q"):
                try:
                    nums.append(int(item.id[1:]))
                except ValueError:
                    continue
        candidate = (max(nums) if nums else 0) + 1
        while f"Q{candidate}" in used_ids:
            candidate += 1
        return f"Q{candidate}"

    changed = False
    for question in questions:
        text = (question or "").strip()
        if not text or text.lower() in existing:
            continue
        ident = next_product_id() if source == "product" else text.split()[0]
        if ident in used_ids:
            ident = next_product_id()
        items.append(Clarification(id=ident, question=text, status="open", source=source))
        used_ids.add(ident)
        existing.add(text.lower())
        changed = True
    if changed:
        save_clarifications(paths, items)
    return items


def unresolved_material(paths: SDDPaths) -> list[Clarification]:
    return [item for item in load_clarifications(paths) if item.status in {"open", "deferred"}]


def _write_decision(paths: SDDPaths, decision_id: str, selected: str, reason: str) -> ArchitectureDecision:
    from .artifacts import write_architecture

    decisions = load_decisions(paths)
    target = None
    for decision in decisions:
        if decision.id == decision_id:
            decision.selected = selected
            decision.selected_reason = reason
            decision.status = DecisionStatus.selected
            target = decision
            break
    if target is None:
        raise ValueError(f"Unknown architecture decision: {decision_id}")
    write_architecture(paths, decisions)
    return target


def answer_clarification(paths: SDDPaths, clarification_id: str, answer: str) -> Clarification:
    items = load_clarifications(paths)
    target = None
    for item in items:
        if item.id == clarification_id:
            item.answer = answer
            item.status = "answered"
            if not _placeholder(answer):
                item.default_option = item.default_option or answer.strip()
            target = item
            break
    if target is None:
        raise ValueError(f"Unknown clarification: {clarification_id}")
    if target.source == "architecture":
        _write_decision(paths, target.id, answer.strip(), "Answered via sdd clarify")
    save_clarifications(paths, items)
    return target


def accept_deferred_defaults(paths: SDDPaths) -> list[Clarification]:
    """Sign deferred items only when an explicit default/option exists. Updates ADRs atomically."""
    decisions = {d.id: d for d in load_decisions(paths)}
    updated: list[Clarification] = []
    rejected: list[Clarification] = []
    for item in load_clarifications(paths):
        if item.status != "deferred":
            updated.append(item)
            continue
        if item.source == "architecture":
            decision = decisions.get(item.id)
            chosen = (item.default_option or "").strip() or (default_option_for(decision) if decision else None)
            if not chosen:
                rejected.append(item)
                updated.append(item)
                continue
            _write_decision(paths, item.id, chosen, "Accepted deferred default at start")
            item = item.model_copy(
                update={
                    "status": "accepted_default",
                    "answer": f"Accepted default: {chosen}",
                    "default_option": chosen,
                }
            )
            updated.append(item)
            continue
        if _placeholder(item.answer) and not item.default_option:
            rejected.append(item)
            updated.append(item)
            continue
        chosen = item.default_option or item.answer.strip()
        item = item.model_copy(
            update={
                "status": "accepted_default",
                "answer": f"Accepted default: {chosen}",
                "default_option": chosen,
            }
        )
        updated.append(item)
    save_clarifications(paths, updated)
    if rejected:
        raise RuntimeError(
            _block_message(rejected)
            + "\n`--accept-deferred` requires an explicit default or option ID; none was recorded."
        )
    leftover = [d for d in load_decisions(paths) if d.status == DecisionStatus.deferred or not d.selected]
    if leftover:
        raise RuntimeError(
            "Architecture remains unresolved after `--accept-deferred`:\n"
            + "\n".join(f"- {d.id}: selected={d.selected!r} status={d.status.value}" for d in leftover)
        )
    return updated


def assert_start_ready(paths: SDDPaths, *, accept_deferred: bool = False) -> None:
    from .storage import load_config

    config = load_config(paths)
    if not config.require_resolved_clarifications:
        return
    unresolved = unresolved_material(paths)
    deferred_decisions = [
        d for d in load_decisions(paths)
        if d.status == DecisionStatus.deferred or not d.selected
    ]
    if not unresolved and not deferred_decisions:
        return
    if accept_deferred:
        accept_deferred_defaults(paths)
        leftover = unresolved_material(paths)
        still_open = [
            d for d in load_decisions(paths)
            if d.status == DecisionStatus.deferred or not d.selected
        ]
        if leftover or still_open:
            raise RuntimeError(_block_message(leftover) + "\nOpen questions still need answers.")
        return
    raise RuntimeError(_block_message(unresolved or [
        Clarification(id=d.id, question=d.question, status="deferred", source="architecture")
        for d in deferred_decisions
    ]))


def _block_message(items: list[Clarification]) -> str:
    lines = [
        "Material clarifications are unresolved. Answer them with `sdd clarify` "
        "or pass `--accept-deferred` to start with signed defaults:",
    ]
    for item in items:
        lines.append(f"- {item.id} ({item.source}/{item.status}): {item.question}")
    return "\n".join(lines)

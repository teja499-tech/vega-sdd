"""Usage and compression savings. Never a reason to stop a run."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .journal import Journal
from .models import AgentResult, ProjectState, utcnow
from .storage import SDDPaths, dump_yaml, load_yaml, save_project_state


def estimate_tokens(text: str | None) -> int:
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def usage_from_result(prompt: str, result: AgentResult, additional_context: str = "") -> tuple[int, int]:
    prompt_tokens = result.prompt_tokens or estimate_tokens(prompt + additional_context)
    completion_tokens = result.completion_tokens or estimate_tokens(result.text)
    return prompt_tokens, completion_tokens


def token_ledger_path(paths: SDDPaths) -> Path:
    return paths.state / "token-ledger.yaml"


def savings_ledger_path(paths: SDDPaths) -> Path:
    return paths.state / "compression-ledger.yaml"


def record_usage(
    paths: SDDPaths,
    state: ProjectState,
    *,
    task_id: str | None,
    phase: str,
    prompt: str,
    result: AgentResult,
    additional_context: str = "",
    estimate_basis: str = "prompt",
) -> dict[str, Any]:
    provider_prompt = bool(result.prompt_tokens)
    provider_completion = bool(result.completion_tokens)
    prompt_tokens, completion_tokens = usage_from_result(prompt, result, additional_context)
    total = prompt_tokens + completion_tokens
    result.prompt_tokens = prompt_tokens
    result.completion_tokens = completion_tokens
    state.tokens_used += total
    state.tokens_this_run += total
    save_project_state(paths, state)
    row = {
        "timestamp": utcnow(),
        "task_id": task_id,
        "phase": phase,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total": total,
        "run_total": state.tokens_this_run,
        "project_total": state.tokens_used,
        "usage_source": "provider" if provider_prompt and provider_completion else "mixed" if provider_prompt or provider_completion else "estimate",
        "estimate_basis": "provider-reported" if provider_prompt and provider_completion else estimate_basis,
    }
    ledger = load_yaml(token_ledger_path(paths), []) or []
    ledger.append(row)
    dump_yaml(token_ledger_path(paths), ledger)
    Journal(paths.event_log).append(
        "token_usage",
        task=task_id,
        phase=phase,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total=total,
    )
    return row


def record_savings(
    paths: SDDPaths,
    *,
    label: str,
    raw_chars: int,
    compressed_chars: int,
    engine: str,
    original_path: str = "",
) -> dict[str, Any]:
    saved = max(0, raw_chars - compressed_chars)
    row = {
        "timestamp": utcnow(),
        "label": label,
        "engine": engine,
        "raw_chars": raw_chars,
        "compressed_chars": compressed_chars,
        "saved_chars": saved,
        "original": original_path,
    }
    ledger = load_yaml(savings_ledger_path(paths), []) or []
    ledger.append(row)
    dump_yaml(savings_ledger_path(paths), ledger)
    Journal(paths.event_log).append("context_compressed", **{k: v for k, v in row.items() if k != "timestamp"})
    return row


def savings_summary(paths: SDDPaths) -> dict[str, int]:
    rows = load_yaml(savings_ledger_path(paths), []) or []
    raw = sum(int(row.get("raw_chars") or 0) for row in rows)
    compressed = sum(int(row.get("compressed_chars") or 0) for row in rows)
    return {"events": len(rows), "raw_chars": raw, "compressed_chars": compressed, "saved_chars": max(0, raw - compressed)}

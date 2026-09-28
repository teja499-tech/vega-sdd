"""Headroom compression for text the controller sends to an agent.

Originals stay on disk. A missing or hung Headroom install does not stop the run.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from typing import Any

from .storage import SDDPaths
from .tokens import record_savings

HEADROOM_TIMEOUT = 8
HEADROOM_MAX_CHARS = 200_000
HEADROOM_FAILURE_LIMIT = 3
DISABLE_ENV = "SDD_DISABLE_HEADROOM"

_FAILURES = 0
_CIRCUIT_OPEN = False


def headroom_enabled(paths: SDDPaths | None = None) -> bool:
    flag = os.environ.get(DISABLE_ENV, "")
    if flag.strip().lower() in {"1", "true", "yes"}:
        return False
    if _CIRCUIT_OPEN:
        return False
    if paths is None:
        return True
    try:
        from .storage import load_config
        return bool(load_config(paths).enable_headroom)
    except Exception:
        return True


def _store_original(paths: SDDPaths, label: str, text: str) -> str:
    digest = hashlib.sha256(text.encode()).hexdigest()[:16]
    folder = paths.runtime / "originals"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{digest}.txt"
    if not target.exists():
        target.write_text(text, encoding="utf-8")
    index = folder / "index.txt"
    with index.open("a", encoding="utf-8") as handle:
        handle.write(f"{digest}\t{label}\t{target.name}\n")
    return str(target.relative_to(paths.root))


def _unwrap(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("text", "content", "compressed", "output"):
            inner = value.get(key)
            if isinstance(inner, str):
                return inner
        messages = value.get("messages")
        if isinstance(messages, list):
            return _unwrap(messages)
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                content = item.get("content")
                if isinstance(content, str):
                    parts.append(content)
        if parts:
            return "\n".join(parts)
    return None


def _trip_circuit() -> None:
    global _FAILURES, _CIRCUIT_OPEN
    _FAILURES += 1
    if _FAILURES >= HEADROOM_FAILURE_LIMIT:
        _CIRCUIT_OPEN = True


def _reset_circuit() -> None:
    global _FAILURES, _CIRCUIT_OPEN
    _FAILURES = 0
    _CIRCUIT_OPEN = False


def _headroom_importable() -> bool:
    try:
        import headroom  # noqa: F401
    except ImportError:
        return False
    return True


def _worker() -> None:
    from headroom import compress

    text = sys.stdin.read()
    result = compress(
        [{"role": "tool", "content": text}],
        compress_user_messages=True,
        target_ratio=0.5,
        protect_recent=0,
    )
    messages = getattr(result, "messages", None)
    if isinstance(messages, list) and messages:
        content = messages[0].get("content") if isinstance(messages[0], dict) else None
        if isinstance(content, str) and content.strip():
            sys.stdout.write(json.dumps(content))
            return
    produced = _unwrap(result)
    sys.stdout.write(json.dumps(produced))


def _run_headroom_subprocess(text: str, *, timeout: float = HEADROOM_TIMEOUT) -> str | None:
    try:
        completed = subprocess.run(
            [sys.executable, "-c", "from universal_sdd.compress import _worker; _worker()"],
            input=text,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        _trip_circuit()
        return None
    except OSError:
        _trip_circuit()
        return None
    if completed.returncode != 0:
        _trip_circuit()
        return None
    try:
        produced = json.loads(completed.stdout or "null")
    except json.JSONDecodeError:
        _trip_circuit()
        return None
    if isinstance(produced, str) and produced.strip():
        _reset_circuit()
        return produced
    _trip_circuit()
    return None


def headroom_compress(text: str, *, timeout: float = HEADROOM_TIMEOUT) -> str | None:
    """Return Headroom's compressed text, or None when Headroom is unavailable."""
    if _CIRCUIT_OPEN:
        return None
    if len(text or "") > HEADROOM_MAX_CHARS:
        return None
    if not _headroom_importable():
        return None
    return _run_headroom_subprocess(text, timeout=timeout)


def compress_for_prompt(paths: SDDPaths, text: str, *, label: str) -> str:
    raw = text or ""
    if not raw.strip():
        return raw
    original = _store_original(paths, label, raw)
    produced = headroom_compress(raw) if headroom_enabled(paths) else None
    pointer = f"\n\nFull original: `{original}`\n" if original else ""
    if produced and len(produced.rstrip()) + len(pointer) < len(raw):
        compressed = produced.rstrip() + pointer
        engine = "headroom"
    elif produced is not None:
        compressed = raw
        engine = "headroom-noop"
    else:
        compressed = raw
        engine = "passthrough"
    record_savings(
        paths,
        label=label,
        raw_chars=len(raw),
        compressed_chars=len(compressed),
        engine=engine,
        original_path=original,
    )
    return compressed

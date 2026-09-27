"""Headroom compression for text the controller sends to an agent.

Originals stay on disk. A missing Headroom install does not stop the run.
"""
from __future__ import annotations

import hashlib
from typing import Any

from .storage import SDDPaths
from .tokens import record_savings


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


def headroom_compress(text: str) -> str | None:
    """Return Headroom's compressed text, or None when Headroom is unavailable."""
    try:
        from headroom import compress
    except ImportError:
        return None
    try:
        result = compress(
            [{"role": "tool", "content": text}],
            compress_user_messages=True,
            target_ratio=0.5,
            protect_recent=0,
        )
    except Exception:
        return None
    messages = getattr(result, "messages", None)
    if isinstance(messages, list) and messages:
        content = messages[0].get("content") if isinstance(messages[0], dict) else None
        if isinstance(content, str) and content.strip():
            return content
    return _unwrap(result)


def compress_for_prompt(paths: SDDPaths, text: str, *, label: str) -> str:
    raw = text or ""
    if not raw.strip():
        return raw
    original = _store_original(paths, label, raw)
    produced = headroom_compress(raw)
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

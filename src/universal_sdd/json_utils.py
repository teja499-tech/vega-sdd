from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator
from typing import Any


def _unwrap_encoded(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def iter_json_values(text: str) -> Iterator[Any]:
    """Yield every JSON value embedded in agent output, first to last."""
    stripped = text.strip()
    try:
        yield _unwrap_encoded(json.loads(stripped))
    except json.JSONDecodeError:
        pass

    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        try:
            yield _unwrap_encoded(json.loads(fence.group(1).strip()))
        except json.JSONDecodeError:
            pass

    decoder = json.JSONDecoder()
    for idx, ch in enumerate(text):
        if ch not in "[{":
            continue
        try:
            value, _ = decoder.raw_decode(text[idx:])
        except json.JSONDecodeError:
            continue
        yield _unwrap_encoded(value)


def extract_json(text: str) -> Any:
    """Extract the first JSON object/array from agent output.

    Handles raw JSON, fenced code blocks, and prose surrounding a JSON payload.
    """
    for value in iter_json_values(text):
        return value
    raise ValueError("Agent response did not contain valid JSON")


def parse_structured(text: str, validate: Callable[[Any], Any]) -> Any:
    """Return the first embedded JSON value that passes ``validate``.

    Cursor plan/ask replies often include an earlier inner object (for example
    the product model) before the complete specification bundle.
    """
    last_error: Exception | None = None
    seen: list[int] = []
    for value in iter_json_values(text):
        marker = id(value) if not isinstance(value, (dict, list, str, int, float, bool, type(None))) else hash(repr(value)[:2000])
        if marker in seen:
            continue
        seen.append(marker)
        try:
            return validate(value)
        except Exception as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise ValueError("Agent response did not contain valid JSON")

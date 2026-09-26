from __future__ import annotations

import json
import re
from typing import Any


def extract_json(text: str) -> Any:
    """Extract the first JSON object/array from agent output.

    Handles raw JSON, fenced code blocks, and prose surrounding a JSON payload.
    """
    stripped = text.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        try:
            return json.loads(fence.group(1).strip())
        except json.JSONDecodeError:
            pass

    decoder = json.JSONDecoder()
    for idx, ch in enumerate(text):
        if ch not in "[{":
            continue
        try:
            value, _ = decoder.raw_decode(text[idx:])
            return value
        except json.JSONDecodeError:
            continue
    raise ValueError("Agent response did not contain valid JSON")

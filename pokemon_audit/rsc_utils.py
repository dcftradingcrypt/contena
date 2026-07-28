from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

_RSC_RE = re.compile(r'self\.__next_f\.push\(\[1,("(?:\\.|[^"\\])*")\]\)')


def decode_rsc_text(html: str) -> str:
    chunks: list[str] = []
    for match in _RSC_RE.finditer(html):
        try:
            chunks.append(json.loads(match.group(1)))
        except json.JSONDecodeError:
            continue
    if not chunks:
        raise ValueError("Next.js RSC payload not found")
    return "".join(chunks)


def extract_json_after_key(text: str, key: str, start_at: int = 0) -> Any:
    needle = f'"{key}"'
    idx = text.find(needle, start_at)
    if idx < 0:
        raise KeyError(key)
    colon = text.find(":", idx + len(needle))
    if colon < 0:
        raise ValueError(f"missing colon after {key}")
    pos = colon + 1
    while pos < len(text) and text[pos].isspace():
        pos += 1
    if pos >= len(text):
        raise ValueError(f"missing value after {key}")
    opener = text[pos]
    if opener not in "[{":
        return json.JSONDecoder().raw_decode(text[pos:])[0]
    closer = "}" if opener == "{" else "]"
    depth = 0
    in_string = False
    escaped = False
    for i in range(pos, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return json.loads(text[pos : i + 1])
    raise ValueError(f"unterminated JSON value for {key}")


def extract_string_after_key(text: str, key: str, start_at: int = 0) -> str:
    needle = f'"{key}"'
    idx = text.find(needle, start_at)
    if idx < 0:
        raise KeyError(key)
    colon = text.find(":", idx + len(needle))
    if colon < 0:
        raise ValueError(f"missing colon after {key}")
    pos = colon + 1
    while pos < len(text) and text[pos].isspace():
        pos += 1
    value, _ = json.JSONDecoder().raw_decode(text[pos:])
    if not isinstance(value, str):
        raise TypeError(f"{key} is not a string")
    return value


def parse_en_timestamp(value: str) -> datetime:
    return datetime.strptime(value.strip(), "%b %d, %Y, %I:%M %p")


def parse_ja_timestamp(value: str) -> datetime:
    return datetime.strptime(value.strip(), "%Y年%m月%d日 %H:%M")

"""Shared HTML/text normalization for site-specific parsers."""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\u00a0]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")
_LIST_ITEM_RE = re.compile(r"<li[^>]*>(.*?)</li>", re.IGNORECASE | re.DOTALL)


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data:
            self._parts.append(data)

    def get_text(self) -> str:
        return "".join(self._parts)


def strip_html(value: str) -> str:
    if not value:
        return ""
    text = html.unescape(value)
    text = _LIST_ITEM_RE.sub(lambda m: f"\n- {strip_html(m.group(1))}", text)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</h[1-6]>", "\n", text, flags=re.IGNORECASE)
    parser = _HTMLTextExtractor()
    parser.feed(text)
    parser.close()
    cleaned = parser.get_text() or _TAG_RE.sub(" ", text)
    return normalize_whitespace(cleaned)


def normalize_whitespace(value: str) -> str:
    if not value:
        return ""
    lines = []
    for line in value.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = _WS_RE.sub(" ", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def decode_entities(value: str) -> str:
    if not value:
        return ""
    return html.unescape(value)


def clean_text(value: str) -> str:
    return normalize_whitespace(strip_html(decode_entities(value)))

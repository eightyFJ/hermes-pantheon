"""Tab title text: cleaning untrusted labels and composing ``<frame> <label>``."""

from __future__ import annotations

import re
import unicodedata

DEFAULT_LABEL = "Hermes"
MAX_LABEL = 28

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_INVISIBLE_RANGES = ((0x200B, 0x200F), (0x202A, 0x202E), (0x2060, 0x2069), (0xFEFF, 0xFEFF), (0xFFF9, 0xFFFC))
_INVISIBLE_RE = re.compile("[" + "".join(f"{chr(a)}-{chr(b)}" for a, b in _INVISIBLE_RANGES) + "]")
_SPACE_RE = re.compile(r"\s+")


def clean_label(text: object, max_len: int = MAX_LABEL) -> str:
    """One printable line, cut to ``max_len`` characters with an ellipsis (0 means no limit)."""
    if not isinstance(text, str):
        return ""
    text = unicodedata.normalize("NFC", text)
    text = _SPACE_RE.sub(" ", _INVISIBLE_RE.sub("", _CONTROL_RE.sub(" ", text))).strip()
    if 0 < max_len < len(text):
        text = text[: max(1, max_len - 1)].rstrip() + "…"
    return text


def compose(frame: str, label: str) -> str:
    frame = _INVISIBLE_RE.sub("", _CONTROL_RE.sub("", frame or "")).strip()
    label = clean_label(label, 0) or DEFAULT_LABEL
    return f"{frame} {label}" if frame else label

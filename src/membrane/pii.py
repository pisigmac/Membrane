"""Basic PII scanning for governance."""

from __future__ import annotations

import re
from dataclasses import dataclass

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CC_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")


@dataclass
class PIIResult:
    has_pii: bool
    redacted: str
    matches: list[str]


def scan_pii(text: str, mode: str = "basic") -> PIIResult:
    if mode == "none":
        return PIIResult(has_pii=False, redacted=text, matches=[])

    matches: list[str] = []
    redacted = text
    for name, pattern in (
        ("email", EMAIL_RE),
        ("phone", PHONE_RE),
        ("ssn", SSN_RE),
    ):
        found = pattern.findall(redacted)
        if found:
            matches.extend(f"{name}:{m}" for m in found)
            redacted = pattern.sub(f"[REDACTED_{name.upper()}]", redacted)

    if mode == "advanced":
        found = CC_RE.findall(redacted)
        if found:
            matches.extend(f"cc:{m}" for m in found)
            redacted = CC_RE.sub("[REDACTED_CC]", redacted)

    return PIIResult(has_pii=bool(matches), redacted=redacted, matches=matches)

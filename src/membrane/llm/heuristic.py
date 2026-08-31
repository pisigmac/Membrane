"""Heuristic memory extractor — runs offline without an API key."""

from __future__ import annotations

import re

from membrane.llm.base import MemoryExtractor
from membrane.models import (
    Confidence,
    MemoryRecord,
    MemoryType,
    Provenance,
    Stability,
)

PREFER_RE = re.compile(
    r"(?i)\b(?:i\s+)?(?:prefer|like|want|always\s+want)\b(.{5,120})",
)
NEVER_RE = re.compile(
    r"(?i)\b(?:never|do\s+not|don't|must\s+not)\b(.{5,120})",
)
WHEN_RE = re.compile(
    r"(?i)\bwhen\b(.{5,80})\b(?:then|,)\s*(.{5,80})",
)
FACT_RE = re.compile(
    r"(?i)\b(?:my\s+name\s+is|i\s+am|i'm|we\s+use|deploy(?:s|ed|ing)?|runs?\s+on)\b(.{5,120})",
)
EPHEMERAL_HINTS = re.compile(r"(?i)\b(today|tomorrow|this\s+week|temporary|asap|right\s+now)\b")


def _trim(s: str, limit: int = 160) -> str:
    s = re.sub(r"\s+", " ", s).strip(" .,:;")
    return s[:limit]


class HeuristicExtractor(MemoryExtractor):
    def extract(self, chunk_id: str, chunk_text: str) -> list[MemoryRecord]:
        records: list[MemoryRecord] = []
        seen: set[str] = set()

        for match in PREFER_RE.finditer(chunk_text):
            content = f"User prefers {_trim(match.group(1))}"
            records.append(
                self._make(
                    MemoryType.PREFERENCE,
                    content,
                    chunk_id,
                    Confidence.HIGH,
                    Provenance.DIRECT,
                )
            )

        for match in NEVER_RE.finditer(chunk_text):
            content = f"Never {_trim(match.group(1))}"
            records.append(
                self._make(
                    MemoryType.CONSTRAINT,
                    content,
                    chunk_id,
                    Confidence.HIGH,
                    Provenance.DIRECT,
                )
            )

        for match in WHEN_RE.finditer(chunk_text):
            content = f"When {_trim(match.group(1))}, {_trim(match.group(2))}"
            records.append(
                self._make(
                    MemoryType.SKILL,
                    content,
                    chunk_id,
                    Confidence.MEDIUM,
                    Provenance.INFERRED,
                )
            )

        for match in FACT_RE.finditer(chunk_text):
            content = _trim(match.group(0))
            records.append(
                self._make(
                    MemoryType.FACT,
                    content,
                    chunk_id,
                    Confidence.MEDIUM,
                    Provenance.DIRECT,
                )
            )

        # Deduplicate by normalized content
        unique: list[MemoryRecord] = []
        for rec in records:
            key = rec.content.lower()
            if key in seen:
                continue
            seen.add(key)
            if EPHEMERAL_HINTS.search(rec.content):
                rec.stability = Stability.EPHEMERAL
                rec.confidence = Confidence.LOW
            unique.append(rec)
        return unique

    def _make(
        self,
        mtype: MemoryType,
        content: str,
        chunk_id: str,
        confidence: Confidence,
        provenance: Provenance,
    ) -> MemoryRecord:
        tokens = max(8, len(content.split()))
        return MemoryRecord(
            type=mtype,
            content=content,
            confidence=confidence,
            stability=Stability.STABLE,
            source_chunks=[chunk_id],
            provenance=provenance,
            estimated_tokens=tokens,
        )

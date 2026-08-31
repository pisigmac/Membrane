"""Phase 1: Construction — segment, extract, validate, score."""

from __future__ import annotations

import re
from typing import Iterable

from membrane.config import MembraneConfig, load_config
from membrane.llm.base import MemoryExtractor, get_extractor
from membrane.models import (
    Confidence,
    ConstructionBatch,
    MemoryRecord,
    MemoryType,
    Session,
    new_id,
)
from membrane.safety import is_session_safe

VAGUE = re.compile(
    r"(?i)^(ok|okay|thanks|thank you|hi|hello|yes|no|sure|got it)[.!]?$"
)
EPHEMERAL = re.compile(
    r"(?i)\b(today|tomorrow|this (morning|afternoon|evening|week)|asap|temporary|right now)\b"
)


def estimate_tokens(text: str) -> int:
    return max(1, len(text.split()))


def segment_history(sessions: Iterable[Session], max_chunk_tokens: int) -> list[tuple[str, str]]:
    """Break sessions into topical chunks capped at max_chunk_tokens."""
    chunks: list[tuple[str, str]] = []
    buf: list[str] = []
    buf_tokens = 0
    chunk_idx = 0

    def flush(session_id: str) -> None:
        nonlocal chunk_idx, buf, buf_tokens
        if not buf:
            return
        chunk_id = f"{session_id}-chunk-{chunk_idx}"
        chunks.append((chunk_id, "\n".join(buf)))
        chunk_idx += 1
        buf = []
        buf_tokens = 0

    for session in sessions:
        chunk_idx = 0
        for msg in session.messages:
            line = f"{msg.role}: {msg.content}"
            if msg.tool_name:
                line = f"{msg.role}/{msg.tool_name}: {msg.content}"
            t = estimate_tokens(line)
            if buf and buf_tokens + t > max_chunk_tokens:
                flush(session.id)
            buf.append(line)
            buf_tokens += t
        flush(session.id)
    return chunks


def specificity_ok(content: str) -> bool:
    if len(content.split()) < 4:
        return False
    if VAGUE.match(content.strip()):
        return False
    return True


def actionability_ok(record: MemoryRecord) -> bool:
    text = record.content.lower()
    if record.type == MemoryType.CONSTRAINT:
        return any(w in text for w in ("never", "must", "don't", "do not", "avoid", "only"))
    if record.type == MemoryType.SKILL:
        return "when" in text or "if " in text
    if record.type == MemoryType.PREFERENCE:
        return any(w in text for w in ("prefer", "like", "want", "favor", "concise", "detailed"))
    # facts: must mention a concrete noun-ish token
    return len(text.split()) >= 4


def validate_and_score(record: MemoryRecord) -> MemoryRecord | None:
    if not specificity_ok(record.content):
        return None
    if not actionability_ok(record):
        return None
    if EPHEMERAL.search(record.content):
        from membrane.models import Stability

        record.stability = Stability.EPHEMERAL
        if record.confidence == Confidence.HIGH:
            record.confidence = Confidence.MEDIUM
    record.estimated_tokens = estimate_tokens(record.content)
    return record


def construct(
    sessions: list[Session],
    *,
    config: MembraneConfig | None = None,
    extractor: MemoryExtractor | None = None,
) -> ConstructionBatch:
    cfg = config or load_config()
    ext = extractor or get_extractor(cfg)
    safe_sessions = [s for s in sessions if is_session_safe(s, cfg)]
    chunks = segment_history(safe_sessions, cfg.construction.max_chunk_tokens)

    batch = ConstructionBatch(batch_id=new_id())
    for chunk_id, chunk_text in chunks:
        for candidate in ext.extract(chunk_id, chunk_text):
            validated = validate_and_score(candidate)
            if validated is None:
                continue
            validated.batch_id = batch.batch_id
            batch.records.append(validated)
    return batch

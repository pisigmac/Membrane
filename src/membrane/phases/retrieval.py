"""Phase 3: Retrieval — load, rank, select, format, touch."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from membrane.config import MembraneConfig, load_config
from membrane.embeddings.base import EmbeddingProvider, cosine_similarity, get_embedding_provider
from membrane.models import (
    CONFIDENCE_WEIGHTS,
    Confidence,
    MemoryRecord,
    MemoryType,
    RetrievalResult,
    utcnow,
)
from membrane.store.checksum import append_audit
from membrane.store.index import MemoryStore


def recency_bonus(record: MemoryRecord, half_life_days: float) -> float:
    """log(1 + days_since_accessed) dampened by half-life — higher for recently used."""
    now = utcnow()
    ref = record.last_accessed_at or record.created_at
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    days = max(0.0, (now - ref).total_seconds() / 86400.0)
    # Spec: log(1 + days_since_accessed) — but as bonus we invert so recent scores higher
    raw = math.log1p(days)
    # Convert to [0,1]-ish decay using half-life
    decay = 0.5 ** (days / max(half_life_days, 1e-6))
    return float(decay * (1.0 / (1.0 + raw * 0.1)))


def composite_score(
    similarity: float,
    record: MemoryRecord,
    half_life_days: float,
) -> float:
    conf_w = CONFIDENCE_WEIGHTS.get(record.confidence, 0.4)
    return (0.5 * similarity) + (0.3 * recency_bonus(record, half_life_days)) + (0.2 * conf_w)


def format_memory_block(records: list[MemoryRecord]) -> str:
    buckets: dict[MemoryType, list[str]] = {
        MemoryType.CONSTRAINT: [],
        MemoryType.SKILL: [],
        MemoryType.FACT: [],
        MemoryType.PREFERENCE: [],
    }
    for rec in records:
        buckets[rec.type].append(f"- {rec.content}")

    lines = ["=== AGENT MEMORY ==="]
    for label, mtype in (
        ("Constraints", MemoryType.CONSTRAINT),
        ("Skills", MemoryType.SKILL),
        ("Facts", MemoryType.FACT),
        ("Preferences", MemoryType.PREFERENCE),
    ):
        lines.append(f"[{label}]")
        if buckets[mtype]:
            lines.extend(buckets[mtype])
        else:
            lines.append("- (none)")
    lines.append("=== END MEMORY ===")
    return "\n".join(lines)


def retrieve(
    root: Path,
    current_task: str,
    agent_scope: str,
    context_budget: int,
    *,
    config: MembraneConfig | None = None,
    embeddings: EmbeddingProvider | None = None,
    include_archived: bool = False,
) -> RetrievalResult:
    cfg = config or load_config()
    store = MemoryStore(root)
    emb = embeddings or get_embedding_provider(cfg)

    memories: list[tuple[str, MemoryRecord]] = []
    for scope in {agent_scope, "org"}:
        for rec in store.load_active(scope):
            memories.append((scope, rec))
        if include_archived:
            for rec in store.load_archived(scope):
                memories.append((scope, rec))

    if not memories:
        empty = format_memory_block([])
        return RetrievalResult(prompt_block=empty, selected=[], total_tokens=0)

    task_vec = emb.embed_one(current_task)
    scored: list[tuple[float, str, MemoryRecord]] = []
    for scope, rec in memories:
        if rec.embedding:
            sim = cosine_similarity(task_vec, np.asarray(rec.embedding, dtype=float))
        else:
            sim = cosine_similarity(task_vec, emb.embed_one(rec.content))
        score = composite_score(sim, rec, cfg.retrieval.recency_half_life_days)
        scored.append((score, scope, rec))

    scored.sort(key=lambda x: x[0], reverse=True)

    fill_limit = int(context_budget * cfg.retrieval.fill_ratio)
    selected: list[MemoryRecord] = []
    scores: dict[str, float] = {}
    used = 0
    for score, scope, rec in scored[: cfg.retrieval.max_memories_per_query]:
        cost = rec.estimated_tokens or max(8, len(rec.content.split()))
        if selected and used + cost > fill_limit:
            continue
        selected.append(rec)
        scores[rec.id] = score
        used += cost
        store.touch(scope, rec)
        append_audit(
            root,
            batch_id=rec.batch_id or "retrieve",
            record_id=rec.id,
            action="touch",
            scope=scope,
            size_bytes=0,
        )

    block = format_memory_block(selected)
    return RetrievalResult(
        prompt_block=block,
        selected=selected,
        total_tokens=used,
        scores=scores,
    )

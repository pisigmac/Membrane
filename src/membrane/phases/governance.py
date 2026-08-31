"""Phase 2: Governance — scope, contradict, audit, persist."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

from membrane.config import MembraneConfig, load_config
from membrane.embeddings.base import EmbeddingProvider, cosine_similarity, get_embedding_provider
from membrane.models import (
    ConstructionBatch,
    Contradiction,
    GovernanceResult,
    MemoryRecord,
    MemoryType,
    RecordState,
    Stability,
    new_id,
    utcnow,
)
from membrane.paths import contradictions_dir
from membrane.pii import scan_pii
from membrane.store.checksum import append_audit
from membrane.store.index import MemoryStore


def route_scope(
    record: MemoryRecord,
    *,
    user_id: str | None,
    session_id: str | None,
) -> str:
    if record.stability == Stability.EPHEMERAL:
        sid = session_id or "unknown"
        return f"session-{sid}"
    if record.type == MemoryType.CONSTRAINT and not user_id:
        return "org"
    # org-wide patterns: constraints without user binding, or explicit org marker
    content_l = record.content.lower()
    if record.type == MemoryType.CONSTRAINT and "org-wide" in content_l:
        return "org"
    if user_id:
        return f"user-{user_id}"
    if session_id:
        return f"session-{session_id}"
    return "org"


def content_diverges(a: str, b: str) -> bool:
    """True if texts are not near-duplicates (contradiction vs duplicate)."""
    na = " ".join(a.lower().split())
    nb = " ".join(b.lower().split())
    if na == nb:
        return False
    if na in nb or nb in na:
        return False
    ta, tb = set(na.split()), set(nb.split())
    if not ta or not tb:
        return True
    jaccard = len(ta & tb) / len(ta | tb)
    return jaccard < 0.75


def govern(
    batch: ConstructionBatch,
    root: Path,
    *,
    user_id: str | None = None,
    session_id: str | None = None,
    config: MembraneConfig | None = None,
    embeddings: EmbeddingProvider | None = None,
) -> GovernanceResult:
    cfg = config or load_config()
    store = MemoryStore(root)
    emb = embeddings or get_embedding_provider(cfg)
    result = GovernanceResult()
    grace = timedelta(hours=cfg.governance.contradiction_grace_period_hours)
    threshold = cfg.governance.contradiction_similarity_threshold

    for record in batch.records:
        # PII scan
        pii = scan_pii(record.content, cfg.governance.pii_scan)
        if pii.has_pii:
            record.content = pii.redacted

        scope = route_scope(record, user_id=user_id, session_id=session_id)
        record.scope = scope
        record.batch_id = batch.batch_id

        # Embed
        vector = emb.embed_one(record.content)
        record.embedding = vector.tolist()

        existing = store.load_active(scope, include_pending=True)
        contradiction: Contradiction | None = None
        duplicate = False
        for other in existing:
            if other.embedding:
                import numpy as np

                sim = cosine_similarity(vector, np.asarray(other.embedding, dtype=float))
            else:
                other_vec = emb.embed_one(other.content)
                sim = cosine_similarity(vector, other_vec)
            if sim <= threshold:
                continue
            if not content_diverges(record.content, other.content):
                duplicate = True
                break
            contradiction = Contradiction(
                id=new_id(),
                new_id=record.id,
                existing_id=other.id,
                type=record.type.value,
                explanation=(
                    f"New memory conflicts with existing (sim={sim:.3f}): "
                    f"'{record.content}' vs '{other.content}'"
                ),
                similarity=sim,
                scope=scope,
            )
            record.contradicted_by.append(other.id)
            break

        if duplicate:
            record.state = RecordState.REJECTED
            result.rejected.append(record)
            continue

        if contradiction:
            record.state = RecordState.PENDING
            record.pending_until = utcnow() + grace
            _write_contradiction(root, contradiction)
            result.contradictions.append(contradiction)
            result.pending.append(record)
            size = store.append(scope, record)
            append_audit(
                root,
                batch_id=batch.batch_id,
                record_id=record.id,
                action="pending",
                scope=scope,
                size_bytes=size,
            )
            continue

        record.state = RecordState.ACTIVE
        size = store.append(scope, record)
        append_audit(
            root,
            batch_id=batch.batch_id,
            record_id=record.id,
            action="create",
            scope=scope,
            size_bytes=size,
        )
        result.approved.append(record)

    return result


def _write_contradiction(root: Path, contradiction: Contradiction) -> None:
    cdir = contradictions_dir(root)
    cdir.mkdir(parents=True, exist_ok=True)
    path = cdir / f"{contradiction.id}.json"
    path.write_text(
        json.dumps(contradiction.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def resolve_contradiction(
    root: Path,
    contradiction_id: str,
    keep: str,
) -> Contradiction:
    """Resolve a contradiction: keep new | existing | both-archive."""
    path = contradictions_dir(root) / f"{contradiction_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Contradiction not found: {contradiction_id}")
    contradiction = Contradiction.model_validate_json(path.read_text(encoding="utf-8"))
    store = MemoryStore(root)
    scope = contradiction.scope

    def _get(rid: str) -> MemoryRecord | None:
        for rec in store.load_all(scope):
            if rec.id == rid:
                return rec
        return None

    new_rec = _get(contradiction.new_id)
    old_rec = _get(contradiction.existing_id)

    if keep == "new":
        if old_rec:
            store.archive(scope, old_rec)
            append_audit(
                root,
                batch_id=old_rec.batch_id or "resolve",
                record_id=old_rec.id,
                action="archive",
                scope=scope,
                size_bytes=0,
            )
        if new_rec:
            activated = new_rec.model_copy(deep=True)
            activated.state = RecordState.ACTIVE
            activated.pending_until = None
            activated.contradicted_by = []
            size = store.append(scope, activated)
            append_audit(
                root,
                batch_id=activated.batch_id or "resolve",
                record_id=activated.id,
                action="create",
                scope=scope,
                size_bytes=size,
            )
    elif keep == "existing":
        if new_rec:
            store.archive(scope, new_rec)
            append_audit(
                root,
                batch_id=new_rec.batch_id or "resolve",
                record_id=new_rec.id,
                action="archive",
                scope=scope,
                size_bytes=0,
            )
    elif keep == "both-archive":
        for rec in (new_rec, old_rec):
            if rec:
                store.archive(scope, rec)
                append_audit(
                    root,
                    batch_id=rec.batch_id or "resolve",
                    record_id=rec.id,
                    action="archive",
                    scope=scope,
                    size_bytes=0,
                )
    else:
        raise ValueError("keep must be one of: new, existing, both-archive")

    contradiction.resolved = True
    contradiction.resolution = keep
    contradiction.resolved_at = utcnow()
    path.write_text(
        json.dumps(contradiction.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return contradiction

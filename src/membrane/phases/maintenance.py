"""Phase 4: Maintenance — eviction, consolidation, dedup, compaction."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from membrane.config import MembraneConfig, load_config
from membrane.embeddings.base import EmbeddingProvider, cosine_similarity, get_embedding_provider
from membrane.models import (
    Confidence,
    HealthReport,
    MemoryRecord,
    MemoryType,
    Provenance,
    RecordState,
    Stability,
    new_id,
    utcnow,
)
from membrane.paths import contradictions_dir
from membrane.store.checksum import (
    IntegrityHalt,
    append_audit,
    verify_checksums,
    write_fingerprint,
)
from membrane.store.index import MemoryStore

CONF_RANK = {Confidence.LOW: 0, Confidence.MEDIUM: 1, Confidence.HIGH: 2}


def _days_since(dt, now) -> float:
    if dt.tzinfo is None:
        from datetime import timezone

        dt = dt.replace(tzinfo=timezone.utc)
    return (now - dt).total_seconds() / 86400.0


def evict_daily(
    root: Path,
    *,
    config: MembraneConfig | None = None,
) -> list[str]:
    """Archive low-confidence unused, ephemeral aged, and unresolved contradicted facts."""
    cfg = config or load_config()
    store = MemoryStore(root)
    now = utcnow()
    archived_ids: list[str] = []

    for scope in store.list_scopes():
        for rec in store.load_active(scope, include_pending=True):
            age = _days_since(rec.created_at, now)
            last = rec.last_accessed_at or rec.created_at
            accessed_within_3d = _days_since(rec.created_at, last) < 3 and rec.access_count > 0
            # Spec: last_accessed < created_at + 3 days means never meaningfully accessed
            never_used_early = rec.access_count == 0 or (
                rec.last_accessed_at is None
                or _days_since(rec.created_at, rec.last_accessed_at) < 3
            )

            should_archive = False
            if (
                rec.confidence == Confidence.LOW
                and age > cfg.forgetting.low_confidence_ttl_days
                and never_used_early
            ):
                should_archive = True
            if (
                rec.stability == Stability.EPHEMERAL
                and age > cfg.forgetting.ephemeral_ttl_days
            ):
                should_archive = True
            if (
                rec.type == MemoryType.FACT
                and rec.contradicted_by
                and age > cfg.forgetting.unresolved_contradiction_days
            ):
                should_archive = True
                # Also archive contradicted peers if present
                for peer_id in rec.contradicted_by:
                    peer = next((r for r in store.load_all(scope) if r.id == peer_id), None)
                    if peer and peer.state != RecordState.ARCHIVED:
                        store.archive(scope, peer)
                        archived_ids.append(peer.id)
                        append_audit(
                            root,
                            batch_id="maintain-daily",
                            record_id=peer.id,
                            action="archive",
                            scope=scope,
                            size_bytes=0,
                        )

            if should_archive and rec.state != RecordState.ARCHIVED:
                store.archive(scope, rec)
                archived_ids.append(rec.id)
                append_audit(
                    root,
                    batch_id="maintain-daily",
                    record_id=rec.id,
                    action="archive",
                    scope=scope,
                    size_bytes=0,
                )
            _ = accessed_within_3d  # retained for clarity of eviction intent
    return archived_ids


def _ensure_embedding(rec: MemoryRecord, emb: EmbeddingProvider) -> np.ndarray:
    if rec.embedding:
        return np.asarray(rec.embedding, dtype=np.float32)
    return emb.embed_one(rec.content)


def consolidate_weekly(
    root: Path,
    *,
    config: MembraneConfig | None = None,
    embeddings: EmbeddingProvider | None = None,
) -> list[MemoryRecord]:
    """Cluster facts by similarity; if cluster >= N, synthesize a skill and archive facts."""
    cfg = config or load_config()
    store = MemoryStore(root)
    emb = embeddings or get_embedding_provider(cfg)
    threshold = cfg.governance.consolidation_similarity_threshold
    min_size = cfg.governance.consolidation_min_cluster_size
    created: list[MemoryRecord] = []

    for scope in store.list_scopes():
        facts = [r for r in store.load_active(scope) if r.type == MemoryType.FACT]
        if len(facts) < min_size:
            continue
        vectors = [_ensure_embedding(f, emb) for f in facts]
        used = set()
        for i, fi in enumerate(facts):
            if i in used:
                continue
            cluster = [i]
            for j in range(i + 1, len(facts)):
                if j in used:
                    continue
                if cosine_similarity(vectors[i], vectors[j]) >= threshold:
                    cluster.append(j)
            if len(cluster) < min_size:
                continue
            members = [facts[k] for k in cluster]
            for k in cluster:
                used.add(k)
            conditions = "; ".join(m.content for m in members[:3])
            skill = MemoryRecord(
                id=new_id(),
                type=MemoryType.SKILL,
                content=f"When working with related context ({conditions[:200]}...), apply consolidated guidance from prior facts.",
                confidence=max((m.confidence for m in members), key=lambda c: CONF_RANK[c]),
                stability=Stability.STABLE,
                provenance=Provenance.CONSOLIDATED,
                source_chunks=[cid for m in members for cid in m.source_chunks],
                estimated_tokens=40,
                state=RecordState.ACTIVE,
                scope=scope,
                batch_id="maintain-weekly",
                embedding=emb.embed_one(
                    f"When working with related context ({conditions[:200]})"
                ).tolist(),
            )
            size = store.append(scope, skill)
            append_audit(
                root,
                batch_id="maintain-weekly",
                record_id=skill.id,
                action="create",
                scope=scope,
                size_bytes=size,
            )
            created.append(skill)
            for m in members:
                store.archive(scope, m)
                append_audit(
                    root,
                    batch_id="maintain-weekly",
                    record_id=m.id,
                    action="archive",
                    scope=scope,
                    size_bytes=0,
                )
    return created


def deduplicate_weekly(
    root: Path,
    *,
    config: MembraneConfig | None = None,
    embeddings: EmbeddingProvider | None = None,
) -> list[str]:
    """Archive near-duplicates (sim > 0.95), keeping higher confidence and merging access."""
    cfg = config or load_config()
    store = MemoryStore(root)
    emb = embeddings or get_embedding_provider(cfg)
    threshold = cfg.governance.dedup_similarity_threshold
    archived: list[str] = []

    for scope in store.list_scopes():
        records = store.load_active(scope)
        vectors = [_ensure_embedding(r, emb) for r in records]
        drop: set[str] = set()
        for i in range(len(records)):
            if records[i].id in drop:
                continue
            for j in range(i + 1, len(records)):
                if records[j].id in drop:
                    continue
                sim = cosine_similarity(vectors[i], vectors[j])
                if sim <= threshold:
                    continue
                a, b = records[i], records[j]
                if CONF_RANK[a.confidence] >= CONF_RANK[b.confidence]:
                    keep, lose = a, b
                else:
                    keep, lose = b, a
                merged = keep.model_copy(deep=True)
                merged.access_count = keep.access_count + lose.access_count
                if lose.last_accessed_at and (
                    not keep.last_accessed_at or lose.last_accessed_at > keep.last_accessed_at
                ):
                    merged.last_accessed_at = lose.last_accessed_at
                store.append(scope, merged)
                store.archive(scope, lose)
                drop.add(lose.id)
                archived.append(lose.id)
                append_audit(
                    root,
                    batch_id="maintain-weekly",
                    record_id=lose.id,
                    action="archive",
                    scope=scope,
                    size_bytes=0,
                )
    return archived


def compact_monthly(root: Path, *, config: MembraneConfig | None = None) -> HealthReport:
    """Rewrite JSONL files, verify checksums, emit health report."""
    _ = config or load_config()
    store = MemoryStore(root)

    ok, alerts = verify_checksums(root)
    if not ok:
        raise IntegrityHalt("; ".join(alerts))

    for scope in store.list_scopes():
        store.compact_scope(scope)

    write_fingerprint(root)

    # Re-verify after compaction
    ok2, alerts2 = verify_checksums(root)
    if not ok2:
        raise IntegrityHalt("; ".join(alerts2))

    return health_report(root, alerts=alerts + alerts2)


def health_report(root: Path, alerts: list[str] | None = None) -> HealthReport:
    store = MemoryStore(root)
    record_count = 0
    archive_count = 0
    pending_count = 0
    token_sum = 0
    for scope in store.list_scopes():
        for rec in store.load_all(scope):
            if rec.state == RecordState.ARCHIVED:
                archive_count += 1
            elif rec.state == RecordState.PENDING:
                pending_count += 1
                record_count += 1
                token_sum += rec.estimated_tokens
            elif rec.state == RecordState.ACTIVE:
                record_count += 1
                token_sum += rec.estimated_tokens
        archive_count += len(store.load_archived(scope))

    cdir = contradictions_dir(root)
    contradiction_count = 0
    if cdir.exists():
        contradiction_count = len(list(cdir.glob("*.json")))

    avg_density = (token_sum / record_count) if record_count else 0.0
    ok, check_alerts = verify_checksums(root)
    all_alerts = list(alerts or []) + check_alerts
    return HealthReport(
        record_count=record_count,
        archive_count=archive_count,
        contradiction_count=contradiction_count,
        pending_count=pending_count,
        avg_density=avg_density,
        checksum_ok=ok,
        alerts=all_alerts,
    )


def maintain(
    root: Path,
    mode: str,
    *,
    config: MembraneConfig | None = None,
    embeddings: EmbeddingProvider | None = None,
) -> dict:
    cfg = config or load_config()
    emb = embeddings or get_embedding_provider(cfg)
    result: dict = {"mode": mode}

    if mode == "daily":
        result["archived"] = evict_daily(root, config=cfg)
    elif mode == "weekly":
        result["skills"] = [s.model_dump(mode="json") for s in consolidate_weekly(root, config=cfg, embeddings=emb)]
        result["dedup_archived"] = deduplicate_weekly(root, config=cfg, embeddings=emb)
    elif mode == "monthly":
        report = compact_monthly(root, config=cfg)
        result["health"] = report.model_dump(mode="json")
    else:
        raise ValueError("mode must be daily|weekly|monthly")

    result["health_snapshot"] = health_report(root).model_dump(mode="json")
    return result

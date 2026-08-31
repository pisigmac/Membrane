"""Unit tests for validation, ranking, paths, eviction."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from membrane.config import MembraneConfig
from membrane.embeddings.base import cosine_similarity
from membrane.embeddings.stub import StubEmbeddingProvider
from membrane.models import (
    Confidence,
    MemoryRecord,
    MemoryType,
    Provenance,
    Stability,
    utcnow,
)
from membrane.paths import PathTraversalError, safe_join
from membrane.phases.construction import actionability_ok, specificity_ok, validate_and_score
from membrane.phases.maintenance import evict_daily
from membrane.phases.retrieval import composite_score
from membrane.pii import scan_pii
from membrane.safety import is_session_safe
from membrane.models import Session
from membrane.paths import init_layout
from membrane.store.index import MemoryStore
from membrane.store.checksum import append_audit


def test_path_traversal_rejected(tmp_path: Path) -> None:
    with pytest.raises(PathTraversalError):
        safe_join(tmp_path, "..", "etc", "passwd")
    with pytest.raises(PathTraversalError):
        safe_join(tmp_path, "/etc/passwd")


def test_specificity_and_actionability() -> None:
    assert not specificity_ok("ok")
    assert specificity_ok("User prefers concise deployment answers")
    pref = MemoryRecord(
        type=MemoryType.PREFERENCE,
        content="User prefers concise answers",
        confidence=Confidence.HIGH,
        stability=Stability.STABLE,
    )
    assert actionability_ok(pref)
    vague = MemoryRecord(
        type=MemoryType.FACT,
        content="yes",
        confidence=Confidence.LOW,
        stability=Stability.STABLE,
    )
    assert validate_and_score(vague) is None


def test_ranking_formula() -> None:
    rec = MemoryRecord(
        type=MemoryType.SKILL,
        content="When deploying, run smoke tests",
        confidence=Confidence.HIGH,
        stability=Stability.STABLE,
        last_accessed_at=utcnow(),
    )
    score = composite_score(1.0, rec, half_life_days=14)
    assert 0.8 < score <= 1.0
    low = MemoryRecord(
        type=MemoryType.FACT,
        content="something minor",
        confidence=Confidence.LOW,
        stability=Stability.EPHEMERAL,
        created_at=utcnow() - timedelta(days=40),
    )
    low_score = composite_score(0.1, low, half_life_days=14)
    assert low_score < score


def test_stub_embeddings_stable() -> None:
    emb = StubEmbeddingProvider()
    a = emb.embed_one("prefer concise answers")
    b = emb.embed_one("prefer concise answers")
    assert cosine_similarity(a, b) > 0.99


def test_pii_basic() -> None:
    result = scan_pii("Contact me at ada@example.com please", mode="basic")
    assert result.has_pii
    assert "[REDACTED_EMAIL]" in result.redacted


def test_safety_gate() -> None:
    cfg = MembraneConfig()
    bad = Session(adversarial=True, safety_score=0.9, messages=[])
    assert not is_session_safe(bad, cfg)
    low = Session(safety_score=0.1, messages=[])
    assert not is_session_safe(low, cfg)
    good = Session(safety_score=0.9, messages=[])
    assert is_session_safe(good, cfg)


def test_eviction_low_confidence(tmp_path: Path) -> None:
    init_layout(tmp_path)
    store = MemoryStore(tmp_path)
    old = MemoryRecord(
        type=MemoryType.FACT,
        content="We use a temporary staging flag today for testing only",
        confidence=Confidence.LOW,
        stability=Stability.EPHEMERAL,
        provenance=Provenance.INFERRED,
        created_at=utcnow() - timedelta(days=40),
        access_count=0,
    )
    store.append("user-1", old)
    append_audit(
        tmp_path,
        batch_id="t",
        record_id=old.id,
        action="create",
        scope="user-1",
        size_bytes=10,
    )
    archived = evict_daily(tmp_path)
    assert old.id in archived

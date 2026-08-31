"""Tests for agent integration helpers."""

from __future__ import annotations

from pathlib import Path

from membrane.config import load_config
from membrane.embeddings.stub import StubEmbeddingProvider
from membrane.integrations import fetch_memory_block, inject_system_memory
from membrane.models import (
    Confidence,
    MemoryRecord,
    MemoryType,
    Provenance,
    Stability,
)
from membrane.paths import init_layout
from membrane.store.checksum import append_audit
from membrane.store.index import MemoryStore


def test_inject_system_memory(tmp_path: Path) -> None:
    init_layout(tmp_path)
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    emb = StubEmbeddingProvider()
    store = MemoryStore(tmp_path)
    rec = MemoryRecord(
        type=MemoryType.CONSTRAINT,
        content="Never force push to main under any condition",
        confidence=Confidence.HIGH,
        stability=Stability.STABLE,
        provenance=Provenance.DIRECT,
        embedding=emb.embed_one("Never force push to main under any condition").tolist(),
    )
    store.append("user-9", rec)
    append_audit(
        tmp_path,
        batch_id="t",
        record_id=rec.id,
        action="create",
        scope="user-9",
        size_bytes=10,
    )

    block = fetch_memory_block(
        "deploy",
        "user-9",
        root=tmp_path,
        budget=500,
        config=cfg,
        embeddings=emb,
    )
    assert "=== AGENT MEMORY ===" in block

    messages = inject_system_memory(
        [{"role": "user", "content": "deploy please"}],
        "deploy",
        "user-9",
        root=tmp_path,
        budget=500,
        config=cfg,
        embeddings=emb,
    )
    assert messages[0]["role"] == "system"
    assert "Never force push" in messages[0]["content"]

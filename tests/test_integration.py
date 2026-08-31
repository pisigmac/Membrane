"""End-to-end pipeline integration test."""

from __future__ import annotations

import json
from pathlib import Path

from membrane.config import load_config
from membrane.embeddings.stub import StubEmbeddingProvider
from membrane.models import Session
from membrane.paths import init_layout
from membrane.phases.construction import construct
from membrane.phases.governance import govern
from membrane.phases.maintenance import health_report, maintain
from membrane.phases.retrieval import retrieve
from membrane.store.index import MemoryStore


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "sessions.json"


def test_full_pipeline(tmp_path: Path) -> None:
    init_layout(tmp_path)
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    emb = StubEmbeddingProvider()

    raw = json.loads(FIXTURES.read_text(encoding="utf-8"))
    sessions = [Session.model_validate(s) for s in raw]
    batch = construct(sessions, config=cfg)
    assert batch.records, "expected heuristic extraction to find memories"
    # Jailbreak session must not contribute
    assert all("leaking secrets" not in r.content.lower() for r in batch.records)

    result = govern(
        batch,
        tmp_path,
        user_id="4821",
        session_id="demo",
        config=cfg,
        embeddings=emb,
    )
    assert result.approved or result.pending

    store = MemoryStore(tmp_path)
    active = store.load_active("user-4821")
    # Ephemeral may land in session staging
    staging = store.load_active("session-demo")
    assert active or staging

    retrieval = retrieve(
        tmp_path,
        "How do I deploy to staging?",
        "user-4821",
        context_budget=500,
        config=cfg,
        embeddings=emb,
    )
    assert "=== AGENT MEMORY ===" in retrieval.prompt_block
    assert "=== END MEMORY ===" in retrieval.prompt_block

    daily = maintain(tmp_path, "daily", config=cfg, embeddings=emb)
    assert daily["mode"] == "daily"
    weekly = maintain(tmp_path, "weekly", config=cfg, embeddings=emb)
    assert weekly["mode"] == "weekly"
    monthly = maintain(tmp_path, "monthly", config=cfg, embeddings=emb)
    assert monthly["health"]["checksum_ok"] is True

    report = health_report(tmp_path)
    assert report.checksum_ok

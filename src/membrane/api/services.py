"""Helpers for API route handlers."""

from __future__ import annotations

import json
from pathlib import Path

from membrane.api.schemas import MemoryOut
from membrane.models import MemoryRecord, MemoryType, Confidence, Stability, Provenance, RecordState
from membrane.paths import contradictions_dir
from membrane.store.index import MemoryStore


def record_to_out(rec: MemoryRecord) -> MemoryOut:
    return MemoryOut(
        id=rec.id,
        type=rec.type.value if hasattr(rec.type, "value") else str(rec.type),
        content=rec.content,
        confidence=rec.confidence.value if hasattr(rec.confidence, "value") else str(rec.confidence),
        stability=rec.stability.value if hasattr(rec.stability, "value") else str(rec.stability),
        provenance=rec.provenance.value if hasattr(rec.provenance, "value") else str(rec.provenance),
        state=rec.state.value if hasattr(rec.state, "value") else str(rec.state),
        scope=rec.scope,
        estimated_tokens=rec.estimated_tokens,
        created_at=rec.created_at.isoformat() if rec.created_at else None,
        last_accessed_at=rec.last_accessed_at.isoformat() if rec.last_accessed_at else None,
        access_count=rec.access_count,
        contradicted_by=list(rec.contradicted_by or []),
        embedding=rec.embedding,
    )


def list_contradictions(root: Path, *, unresolved_only: bool = True) -> list[dict]:
    cdir = contradictions_dir(root)
    if not cdir.exists():
        return []
    items = []
    for path in sorted(cdir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if unresolved_only and data.get("resolved"):
            continue
        items.append(data)
    return items


def get_contradiction(root: Path, cid: str) -> dict | None:
    path = contradictions_dir(root) / f"{cid}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def maintain_loop_running(root: Path) -> bool:
    pid_file = root / "run" / "maintain_loop.pid"
    if not pid_file.exists():
        return False
    try:
        pid = int(pid_file.read_text().strip())
        Path(f"/proc/{pid}").stat()
        return True
    except Exception:
        return False


def filter_memories(
    store: MemoryStore,
    *,
    scope: str | None,
    state: str | None,
    mtype: str | None,
    include_archived: bool = False,
) -> list[MemoryRecord]:
    scopes = [scope] if scope else store.list_scopes()
    out: list[MemoryRecord] = []
    for sc in scopes:
        records = store.load_all(sc)
        if include_archived:
            records = records + store.load_archived(sc)
        for rec in records:
            if state and (rec.state.value if hasattr(rec.state, "value") else str(rec.state)) != state:
                continue
            if mtype and (rec.type.value if hasattr(rec.type, "value") else str(rec.type)) != mtype:
                continue
            out.append(rec)
    return out


def build_record(
    *,
    content: str,
    type_: str,
    confidence: str,
    stability: str,
    scope: str,
) -> MemoryRecord:
    return MemoryRecord(
        type=MemoryType(type_),
        content=content,
        confidence=Confidence(confidence),
        stability=Stability(stability),
        provenance=Provenance.DIRECT,
        state=RecordState.ACTIVE,
        scope=scope,
    )

"""API route handlers."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from membrane.api.deps import Principal, assert_role, assert_scope, can_access_scope, get_principal
from membrane.api.schemas import (
    HealthOut,
    IngestRequest,
    MaintainRequest,
    MemoryCreate,
    MemoryOut,
    MemoryPatch,
    QueryRequest,
    ResolveRequest,
)
from membrane.api.services import (
    build_record,
    filter_memories,
    get_contradiction,
    list_contradictions,
    maintain_loop_running,
    record_to_out,
)
from membrane.api.settings import get_api_settings
from membrane.config import load_config
from membrane.models import Confidence, MemoryType, RecordState, Session, Stability
from membrane.paths import init_layout
from membrane.phases.construction import construct
from membrane.phases.governance import govern, resolve_contradiction
from membrane.phases.maintenance import health_report, maintain
from membrane.phases.retrieval import retrieve
from membrane.store.checksum import append_audit
from membrane.store.index import MemoryStore

router = APIRouter()


def _root() -> Path:
    settings = get_api_settings()
    root = settings.root_path()
    init_layout(root)
    return root


def _config(root: Path):
    candidate = root / "config.yaml"
    if candidate.exists():
        return load_config(candidate)
    return load_config()


@router.get("/health", response_model=HealthOut)
def health(principal: Principal = Depends(get_principal)) -> HealthOut:
    root = _root()
    report = health_report(root)
    pending = list_contradictions(root, unresolved_only=True)
    return HealthOut(
        health=report.model_dump(mode="json"),
        unresolved_contradictions=len(pending),
        maintain_loop_running=maintain_loop_running(root),
    )


@router.get("/scopes")
def scopes(principal: Principal = Depends(get_principal)) -> list[str]:
    store = MemoryStore(_root())
    all_scopes = store.list_scopes()
    return [s for s in all_scopes if can_access_scope(principal, s)]


@router.get("/memories", response_model=list[MemoryOut])
def list_memories(
    scope: str | None = None,
    state: str | None = None,
    type: str | None = None,
    include_archived: bool = False,
    principal: Principal = Depends(get_principal),
) -> list[MemoryOut]:
    root = _root()
    store = MemoryStore(root)
    if scope:
        assert_scope(principal, scope)
    records = filter_memories(
        store, scope=scope, state=state, mtype=type, include_archived=include_archived
    )
    if not scope:
        records = [r for r in records if r.scope and can_access_scope(principal, r.scope)]
    return [record_to_out(r) for r in records]


@router.get("/memories/{memory_id}", response_model=MemoryOut)
def get_memory(memory_id: str, principal: Principal = Depends(get_principal)) -> MemoryOut:
    store = MemoryStore(_root())
    found = store.find_by_id(memory_id)
    if not found:
        raise HTTPException(status_code=404, detail="Memory not found")
    scope, rec = found
    assert_scope(principal, scope)
    return record_to_out(rec)


@router.post("/memories", response_model=MemoryOut)
def create_memory(body: MemoryCreate, principal: Principal = Depends(get_principal)) -> MemoryOut:
    assert_role(principal, "admin", "operator")
    scope = body.scope or principal.user_scope
    assert_scope(principal, scope)
    root = _root()
    store = MemoryStore(root)
    rec = build_record(
        content=body.content,
        type_=body.type,
        confidence=body.confidence,
        stability=body.stability,
        scope=scope,
    )
    size = store.append(scope, rec)
    append_audit(root, batch_id="api", record_id=rec.id, action="create", scope=scope, size_bytes=size)
    return record_to_out(rec)


@router.patch("/memories/{memory_id}", response_model=MemoryOut)
def patch_memory(
    memory_id: str,
    body: MemoryPatch,
    principal: Principal = Depends(get_principal),
) -> MemoryOut:
    assert_role(principal, "admin", "operator")
    root = _root()
    store = MemoryStore(root)
    found = store.find_by_id(memory_id)
    if not found:
        raise HTTPException(status_code=404, detail="Memory not found")
    scope, rec = found
    assert_scope(principal, scope)
    updated = rec.model_copy(deep=True)
    if body.content is not None:
        updated.content = body.content
    if body.type is not None:
        updated.type = MemoryType(body.type)
    if body.confidence is not None:
        updated.confidence = Confidence(body.confidence)
    if body.stability is not None:
        updated.stability = Stability(body.stability)
    size = store.append(scope, updated)
    append_audit(root, batch_id="api", record_id=updated.id, action="update", scope=scope, size_bytes=size)
    return record_to_out(updated)


@router.post("/memories/{memory_id}/archive", response_model=MemoryOut)
def archive_memory(memory_id: str, principal: Principal = Depends(get_principal)) -> MemoryOut:
    assert_role(principal, "admin", "operator")
    root = _root()
    store = MemoryStore(root)
    found = store.find_by_id(memory_id)
    if not found:
        raise HTTPException(status_code=404, detail="Memory not found")
    scope, rec = found
    assert_scope(principal, scope)
    store.archive(scope, rec)
    append_audit(root, batch_id="api", record_id=rec.id, action="archive", scope=scope, size_bytes=0)
    archived = rec.model_copy(deep=True)
    archived.state = RecordState.ARCHIVED
    return record_to_out(archived)


@router.post("/ingest")
def ingest(body: IngestRequest, principal: Principal = Depends(get_principal)) -> dict:
    assert_role(principal, "admin", "operator")
    root = _root()
    cfg = _config(root)
    if body.sessions is None:
        raise HTTPException(status_code=400, detail="Provide sessions JSON array")

    uid = body.user_id or principal.sub
    sid = body.session_id
    if principal.role != "admin" and uid != principal.sub:
        raise HTTPException(status_code=403, detail="Cannot ingest for another user")

    sessions_data = body.sessions
    if isinstance(sessions_data, dict) and "sessions" in sessions_data:  # type: ignore[operator]
        sessions = [Session.model_validate(s) for s in sessions_data["sessions"]]  # type: ignore[index]
    elif isinstance(sessions_data, list):
        sessions = [Session.model_validate(s) for s in sessions_data]
    else:
        sessions = [Session.model_validate(sessions_data)]

    batch = construct(sessions, config=cfg)
    result = govern(batch, root, user_id=uid, session_id=sid, config=cfg)
    return {
        "approved": len(result.approved),
        "pending": len(result.pending),
        "rejected": len(result.rejected),
        "contradictions": [c.model_dump(mode="json") for c in result.contradictions],
        "batch_id": batch.batch_id,
    }


@router.post("/query")
def query_memories(body: QueryRequest, principal: Principal = Depends(get_principal)) -> dict:
    assert_scope(principal, body.scope)
    root = _root()
    cfg = _config(root)
    result = retrieve(
        root,
        body.task,
        body.scope,
        body.budget,
        config=cfg,
        include_archived=body.include_archived,
    )
    return {
        "prompt_block": result.prompt_block,
        "total_tokens": result.total_tokens,
        "scores": result.scores,
        "selected": [record_to_out(r).model_dump() for r in result.selected],
    }


@router.get("/contradictions")
def contradictions_list(principal: Principal = Depends(get_principal)) -> list[dict]:
    root = _root()
    items = list_contradictions(root, unresolved_only=False)
    out = []
    for item in items:
        scope = item.get("scope")
        if scope and not can_access_scope(principal, scope):
            continue
        out.append(item)
    return out


@router.get("/contradictions/{cid}")
def contradiction_detail(cid: str, principal: Principal = Depends(get_principal)) -> dict:
    root = _root()
    item = get_contradiction(root, cid)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    assert_scope(principal, item["scope"])
    store = MemoryStore(root)
    new_rec = store.find_by_id(item["new_id"])
    old_rec = store.find_by_id(item["existing_id"])
    return {
        "contradiction": item,
        "new": record_to_out(new_rec[1]).model_dump() if new_rec else None,
        "existing": record_to_out(old_rec[1]).model_dump() if old_rec else None,
    }


@router.post("/contradictions/{cid}/resolve")
def contradiction_resolve(
    cid: str,
    body: ResolveRequest,
    principal: Principal = Depends(get_principal),
) -> dict:
    assert_role(principal, "admin", "operator")
    root = _root()
    item = get_contradiction(root, cid)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    assert_scope(principal, item["scope"])
    if body.keep not in {"new", "existing", "both-archive"}:
        raise HTTPException(status_code=400, detail="keep must be new|existing|both-archive")
    result = resolve_contradiction(root, cid, body.keep)
    return result.model_dump(mode="json")


@router.post("/maintain")
def run_maintain(body: MaintainRequest, principal: Principal = Depends(get_principal)) -> dict:
    assert_role(principal, "admin", "operator")
    root = _root()
    cfg = _config(root)
    try:
        result = maintain(root, body.mode, config=cfg)
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return result if isinstance(result, dict) else {"result": result}


@router.get("/me")
def me(principal: Principal = Depends(get_principal)) -> dict:
    return {
        "sub": principal.sub,
        "email": principal.email,
        "org_id": principal.org_id,
        "workspace_id": principal.workspace_id,
        "role": principal.role,
        "user_scope": principal.user_scope,
        "via": principal.via,
    }

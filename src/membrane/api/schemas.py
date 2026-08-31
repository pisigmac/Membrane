"""Request/response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MemoryOut(BaseModel):
    id: str
    type: str
    content: str
    confidence: str
    stability: str
    provenance: str
    state: str
    scope: str | None
    estimated_tokens: int
    created_at: str | None = None
    last_accessed_at: str | None = None
    access_count: int = 0
    contradicted_by: list[str] = Field(default_factory=list)
    embedding: list[float] | None = None


class MemoryCreate(BaseModel):
    content: str
    type: str = "fact"
    confidence: str = "medium"
    stability: str = "stable"
    scope: str | None = None


class MemoryPatch(BaseModel):
    content: str | None = None
    type: str | None = None
    confidence: str | None = None
    stability: str | None = None


class IngestRequest(BaseModel):
    sessions: list[dict[str, Any]] | None = None
    user_id: str | None = None
    session_id: str | None = None


class QueryRequest(BaseModel):
    task: str
    scope: str
    budget: int = 2000
    include_archived: bool = False


class ResolveRequest(BaseModel):
    keep: str  # new|existing|both-archive


class MaintainRequest(BaseModel):
    mode: str  # daily|weekly|monthly


class HealthOut(BaseModel):
    health: dict[str, Any]
    unresolved_contradictions: int
    maintain_loop_running: bool = False

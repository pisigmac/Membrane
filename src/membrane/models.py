"""Pydantic models for Membrane Memory OS."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid4())


class MemoryType(str, Enum):
    FACT = "fact"
    SKILL = "skill"
    PREFERENCE = "preference"
    CONSTRAINT = "constraint"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Stability(str, Enum):
    STABLE = "stable"
    EPHEMERAL = "ephemeral"


class Provenance(str, Enum):
    DIRECT = "direct"
    INFERRED = "inferred"
    BEHAVIORAL = "behavioral"
    CONSOLIDATED = "consolidated"


class RecordState(str, Enum):
    ACTIVE = "active"
    PENDING = "pending"
    ARCHIVED = "archived"
    REJECTED = "rejected"


CONFIDENCE_WEIGHTS: dict[Confidence, float] = {
    Confidence.HIGH: 1.0,
    Confidence.MEDIUM: 0.7,
    Confidence.LOW: 0.4,
}


class Message(BaseModel):
    role: str
    content: str
    tool_name: str | None = None


class Session(BaseModel):
    id: str = Field(default_factory=new_id)
    messages: list[Message] = Field(default_factory=list)
    safety_score: float = 1.0
    adversarial: bool = False
    jailbreak: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryRecord(BaseModel):
    id: str = Field(default_factory=new_id)
    type: MemoryType
    content: str
    confidence: Confidence
    stability: Stability
    source_chunks: list[str] = Field(default_factory=list)
    provenance: Provenance = Provenance.INFERRED
    estimated_tokens: int = 15
    state: RecordState = RecordState.ACTIVE
    scope: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    last_accessed_at: datetime | None = None
    access_count: int = 0
    batch_id: str | None = None
    contradicted_by: list[str] = Field(default_factory=list)
    pending_until: datetime | None = None
    embedding: list[float] | None = None

    def touch(self) -> None:
        self.last_accessed_at = utcnow()
        self.access_count += 1


class ConstructionBatch(BaseModel):
    batch_id: str = Field(default_factory=new_id)
    constructed_at: datetime = Field(default_factory=utcnow)
    records: list[MemoryRecord] = Field(default_factory=list)


class Contradiction(BaseModel):
    id: str = Field(default_factory=new_id)
    new_id: str
    existing_id: str
    type: str
    explanation: str
    similarity: float
    scope: str
    created_at: datetime = Field(default_factory=utcnow)
    resolved: bool = False
    resolution: str | None = None
    resolved_at: datetime | None = None


class HealthReport(BaseModel):
    generated_at: datetime = Field(default_factory=utcnow)
    record_count: int
    archive_count: int
    contradiction_count: int
    pending_count: int
    avg_density: float
    checksum_ok: bool
    alerts: list[str] = Field(default_factory=list)


class GovernanceResult(BaseModel):
    approved: list[MemoryRecord] = Field(default_factory=list)
    pending: list[MemoryRecord] = Field(default_factory=list)
    rejected: list[MemoryRecord] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)


class RetrievalResult(BaseModel):
    prompt_block: str
    selected: list[MemoryRecord] = Field(default_factory=list)
    total_tokens: int = 0
    scores: dict[str, float] = Field(default_factory=dict)

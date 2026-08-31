"""Configuration loading for Membrane Memory OS."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field


class ConstructionConfig(BaseModel):
    batch_size: int = 10
    max_gpu_utilization: float = 0.30
    background_only: bool = True
    max_chunk_tokens: int = 4000
    safety_score_threshold: float = 0.5


class RetrievalConfig(BaseModel):
    context_budget_ratio: float = 0.20
    max_memories_per_query: int = 50
    recency_half_life_days: float = 14.0
    fill_ratio: float = 0.80


class ForgettingConfig(BaseModel):
    low_confidence_ttl_days: int = 7
    medium_confidence_ttl_days: int = 30
    high_confidence_ttl_days: int = 90
    org_constraint_ttl_days: int | None = None
    ephemeral_ttl_days: int = 30
    unresolved_contradiction_days: int = 14


class GovernanceConfig(BaseModel):
    contradiction_grace_period_hours: int = 24
    contradiction_similarity_threshold: float = 0.85
    auto_archive_unresolved_contradictions: bool = False
    pii_scan: Literal["basic", "advanced", "none"] = "basic"
    dedup_similarity_threshold: float = 0.95
    consolidation_similarity_threshold: float = 0.80
    consolidation_min_cluster_size: int = 5


class EmbeddingsConfig(BaseModel):
    provider: Literal["stub", "sentence-transformers"] = "stub"
    model: str = "all-MiniLM-L6-v2"


class LLMConfig(BaseModel):
    provider: Literal["heuristic", "openai_compat"] = "heuristic"
    base_url: str | None = None
    model: str | None = None
    api_key_env: str = "MEMBRANE_LLM_API_KEY"


class MembraneConfig(BaseModel):
    construction: ConstructionConfig = Field(default_factory=ConstructionConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    forgetting: ForgettingConfig = Field(default_factory=ForgettingConfig)
    governance: GovernanceConfig = Field(default_factory=GovernanceConfig)
    embeddings: EmbeddingsConfig = Field(default_factory=EmbeddingsConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)


def default_config_path() -> Path:
    """Locate packaged or repo-root config.yaml."""
    env = os.environ.get("MEMBRANE_CONFIG")
    if env:
        return Path(env)
    cwd = Path.cwd() / "config.yaml"
    if cwd.exists():
        return cwd
    package_root = Path(__file__).resolve().parents[2]
    candidate = package_root / "config.yaml"
    if candidate.exists():
        return candidate
    return cwd


def load_config(path: Path | str | None = None) -> MembraneConfig:
    config_path = Path(path) if path else default_config_path()
    if not config_path.exists():
        return MembraneConfig()
    with config_path.open("r", encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh) or {}
    return MembraneConfig.model_validate(raw)


def membrane_root(explicit: Path | str | None = None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get("MEMBRANE_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    return (Path.cwd() / ".membrane").resolve()

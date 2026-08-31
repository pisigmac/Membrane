"""LLM extractor interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from membrane.config import MembraneConfig
from membrane.models import MemoryRecord


class MemoryExtractor(ABC):
    @abstractmethod
    def extract(self, chunk_id: str, chunk_text: str) -> list[MemoryRecord]:
        """Extract memory candidates from a text chunk."""


def get_extractor(config: MembraneConfig) -> MemoryExtractor:
    if config.llm.provider == "openai_compat":
        from membrane.llm.openai_compat import OpenAICompatExtractor

        return OpenAICompatExtractor(config)
    from membrane.llm.heuristic import HeuristicExtractor

    return HeuristicExtractor()

"""OpenAI-compatible chat extractor."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from membrane.config import MembraneConfig
from membrane.models import (
    Confidence,
    MemoryRecord,
    MemoryType,
    Provenance,
    Stability,
)

SYSTEM_PROMPT = """You extract durable agent memories from conversation chunks.
Return ONLY a JSON array of objects with keys:
type (fact|skill|preference|constraint), content, confidence (high|medium|low),
stability (stable|ephemeral), provenance (direct|inferred|behavioral).
Only include memories that pass specificity, stability, and actionability tests.
If none, return []."""


class OpenAICompatExtractor:
    def __init__(self, config: MembraneConfig) -> None:
        self.config = config
        self.base_url = (config.llm.base_url or os.environ.get("MEMBRANE_LLM_BASE_URL") or "").rstrip(
            "/"
        )
        self.model = config.llm.model or os.environ.get("MEMBRANE_LLM_MODEL") or "gpt-4o-mini"
        self.api_key = os.environ.get(config.llm.api_key_env) or os.environ.get("OPENAI_API_KEY")
        if not self.base_url:
            self.base_url = "https://api.openai.com/v1"
        if not self.api_key:
            raise RuntimeError(
                f"openai_compat extractor requires API key in ${config.llm.api_key_env}"
            )

    def extract(self, chunk_id: str, chunk_text: str) -> list[MemoryRecord]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": chunk_text},
            ],
            "temperature": 0.0,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return self._parse(content, chunk_id)

    def _parse(self, content: str, chunk_id: str) -> list[MemoryRecord]:
        content = content.strip()
        if content.startswith("```"):
            content = content.strip("`")
            if content.startswith("json"):
                content = content[4:].strip()
        try:
            items: list[dict[str, Any]] = json.loads(content)
        except json.JSONDecodeError:
            return []
        if not isinstance(items, list):
            return []
        records: list[MemoryRecord] = []
        for item in items:
            try:
                text = str(item["content"]).strip()
                records.append(
                    MemoryRecord(
                        type=MemoryType(item["type"]),
                        content=text,
                        confidence=Confidence(item.get("confidence", "medium")),
                        stability=Stability(item.get("stability", "stable")),
                        provenance=Provenance(item.get("provenance", "inferred")),
                        source_chunks=[chunk_id],
                        estimated_tokens=max(8, len(text.split())),
                    )
                )
            except (KeyError, ValueError):
                continue
        return records

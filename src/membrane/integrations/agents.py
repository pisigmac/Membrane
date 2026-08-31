"""Agent integration helpers (OpenAI-style messages, Cursor rule snippet)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from membrane.config import MembraneConfig, load_config, membrane_root
from membrane.embeddings.base import EmbeddingProvider, get_embedding_provider
from membrane.phases.retrieval import retrieve


def fetch_memory_block(
    task: str,
    scope: str,
    *,
    root: Path | str | None = None,
    budget: int = 2000,
    config: MembraneConfig | None = None,
    embeddings: EmbeddingProvider | None = None,
    include_archived: bool = False,
) -> str:
    """Return the ``=== AGENT MEMORY ===`` prompt block for a task."""
    r = membrane_root(root)
    cfg = config or load_config(r / "config.yaml" if (r / "config.yaml").exists() else None)
    emb = embeddings or get_embedding_provider(cfg)
    result = retrieve(
        r,
        task,
        scope,
        budget,
        config=cfg,
        embeddings=emb,
        include_archived=include_archived,
    )
    return result.prompt_block


def inject_system_memory(
    messages: list[dict[str, Any]],
    task: str,
    scope: str,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """
    Prepend / merge memory into an OpenAI-style messages list.

    If the first message is role=system, memory is appended to it.
    Otherwise a new system message is inserted at the front.
    """
    block = fetch_memory_block(task, scope, **kwargs)
    out = [dict(m) for m in messages]
    if out and out[0].get("role") == "system":
        out[0]["content"] = f"{out[0].get('content', '').rstrip()}\n\n{block}"
    else:
        out.insert(0, {"role": "system", "content": block})
    return out


def cursor_rule_snippet(scope: str = "user-default", budget: int = 2000) -> str:
    """Example text operators can paste into a Cursor/Claude project rule."""
    return f"""# Membrane memory (manual hook)
Before answering, if shell access is available run:
  ./scripts/query.sh "<user task>" --scope {scope} --budget {budget}
Paste the === AGENT MEMORY === block into your system context and obey Constraints.
"""

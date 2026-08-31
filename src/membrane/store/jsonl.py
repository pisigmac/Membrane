"""Append-only JSONL helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Iterator, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def append_jsonl(path: Path, record: BaseModel | dict) -> int:
    """Append one JSON object as a line. Returns bytes written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(record, BaseModel):
        payload = record.model_dump(mode="json")
    else:
        payload = record
    line = json.dumps(payload, ensure_ascii=False, default=str) + "\n"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)
    return len(line.encode("utf-8"))


def read_jsonl(path: Path) -> Iterator[dict]:
    if not path.exists():
        return
        yield  # pragma: no cover — makes this a generator
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def read_models(path: Path, model: type[T]) -> list[T]:
    return [model.model_validate(row) for row in read_jsonl(path)]


def rewrite_jsonl(path: Path, records: Iterable[BaseModel | dict]) -> None:
    """Atomically rewrite a JSONL file (used for compaction)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for record in records:
            if isinstance(record, BaseModel):
                payload = record.model_dump(mode="json")
            else:
                payload = record
            fh.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    tmp.replace(path)

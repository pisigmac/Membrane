"""Active / pending / archived memory index over JSONL scopes."""

from __future__ import annotations

from pathlib import Path

from membrane.models import MemoryRecord, RecordState, utcnow
from membrane.paths import archive_file, memories_file, scope_path
from membrane.store.jsonl import append_jsonl, read_models, rewrite_jsonl


def _latest_by_id(records: list[MemoryRecord]) -> dict[str, MemoryRecord]:
    """Collapse append-only history to latest version per id (last write wins)."""
    latest: dict[str, MemoryRecord] = {}
    for rec in records:
        latest[rec.id] = rec
    return latest


class MemoryStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def list_scopes(self) -> list[str]:
        memory = self.root / "memory"
        if not memory.exists():
            return []
        scopes: list[str] = []
        for child in memory.iterdir():
            if not child.is_dir():
                continue
            name = child.name
            if name in {"archive", "audit", "embeddings"}:
                continue
            if name.startswith("session-"):
                staging = child / "staging" / "memories.jsonl"
                if staging.exists() or (child / "staging").exists():
                    scopes.append(name)
            elif (child / "memories.jsonl").exists() or child.is_dir():
                scopes.append(name)
        return sorted(scopes)

    def _load_raw(self, scope: str) -> list[MemoryRecord]:
        path = memories_file(self.root, scope)
        return read_models(path, MemoryRecord)

    def load_all(self, scope: str) -> list[MemoryRecord]:
        return list(_latest_by_id(self._load_raw(scope)).values())

    def load_active(self, scope: str, *, include_pending: bool = False) -> list[MemoryRecord]:
        allowed = {RecordState.ACTIVE}
        if include_pending:
            allowed.add(RecordState.PENDING)
        now = utcnow()
        result: list[MemoryRecord] = []
        for rec in self.load_all(scope):
            if rec.state == RecordState.PENDING and rec.pending_until and rec.pending_until <= now:
                # Grace period expired — still pending until operator resolves unless auto
                pass
            if rec.state in allowed:
                result.append(rec)
        return result

    def load_archived(self, scope: str) -> list[MemoryRecord]:
        path = archive_file(self.root, scope)
        return list(_latest_by_id(read_models(path, MemoryRecord)).values())

    def append(self, scope: str, record: MemoryRecord) -> int:
        record.scope = scope
        scope_path(self.root, scope).mkdir(parents=True, exist_ok=True)
        return append_jsonl(memories_file(self.root, scope), record)

    def archive(self, scope: str, record: MemoryRecord) -> int:
        archived = record.model_copy(deep=True)
        archived.state = RecordState.ARCHIVED
        archive_file(self.root, scope).parent.mkdir(parents=True, exist_ok=True)
        size = append_jsonl(archive_file(self.root, scope), archived)
        # Also mark in active file so latest view shows archived
        marker = record.model_copy(deep=True)
        marker.state = RecordState.ARCHIVED
        append_jsonl(memories_file(self.root, scope), marker)
        return size

    def touch(self, scope: str, record: MemoryRecord) -> int:
        updated = record.model_copy(deep=True)
        updated.touch()
        return self.append(scope, updated)

    def compact_scope(self, scope: str) -> int:
        """Rewrite JSONL keeping only latest non-archived records."""
        active = [
            r
            for r in self.load_all(scope)
            if r.state in {RecordState.ACTIVE, RecordState.PENDING}
        ]
        path = memories_file(self.root, scope)
        rewrite_jsonl(path, active)
        return len(active)

    def find_by_id(self, record_id: str) -> tuple[str, MemoryRecord] | None:
        for scope in self.list_scopes():
            for rec in self.load_all(scope):
                if rec.id == record_id:
                    return scope, rec
        return None

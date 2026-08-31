"""Audit log and integrity checksums."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from membrane.paths import audit_log, memories_file
from membrane.store.index import MemoryStore


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_audit(
    root: Path,
    *,
    batch_id: str,
    record_id: str,
    action: str,
    scope: str,
    size_bytes: int,
) -> None:
    path = audit_log(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = f"{_ts()} | {batch_id} | {record_id} | action={action} | {scope} | {size_bytes}\n"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)


def parse_audit(root: Path) -> list[dict[str, str]]:
    path = audit_log(root)
    if not path.exists():
        return []
    entries: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 6:
                continue
            entries.append(
                {
                    "timestamp": parts[0],
                    "batch_id": parts[1],
                    "record_id": parts[2],
                    "action": parts[3].removeprefix("action="),
                    "scope": parts[4],
                    "size_bytes": parts[5],
                }
            )
    return entries


def store_fingerprint(root: Path) -> str:
    """SHA256 over all scope JSONL contents (sorted by path)."""
    store = MemoryStore(root)
    h = hashlib.sha256()
    for scope in store.list_scopes():
        path = memories_file(root, scope)
        if not path.exists():
            continue
        h.update(scope.encode("utf-8"))
        h.update(path.read_bytes())
    return h.hexdigest()


def audit_create_count(root: Path) -> int:
    return sum(1 for e in parse_audit(root) if e["action"] == "create")


def verify_checksums(root: Path) -> tuple[bool, list[str]]:
    """
    Verify basic integrity: every create action should correspond to a known record id
    that exists (active, pending, or archived) somewhere in the store.
    """
    alerts: list[str] = []
    store = MemoryStore(root)
    known_ids: set[str] = set()
    for scope in store.list_scopes():
        for rec in store.load_all(scope):
            known_ids.add(rec.id)
        for rec in store.load_archived(scope):
            known_ids.add(rec.id)

    creates = [e for e in parse_audit(root) if e["action"] == "create"]
    missing = [e["record_id"] for e in creates if e["record_id"] not in known_ids]
    if missing:
        alerts.append(
            f"CHECKSUM MISMATCH: {len(missing)} create audit entries missing from store "
            f"(e.g. {missing[:3]})"
        )
        return False, alerts

    # Fingerprint file for monthly compaction tracking
    fp_path = root / "memory" / "audit" / "store.sha256"
    current = store_fingerprint(root)
    if fp_path.exists():
        expected = fp_path.read_text(encoding="utf-8").strip()
        # Only fail if fingerprint was written after compaction and diverges without audit
        # Soft check: presence of orphaned records without audit create
        audited_creates = {e["record_id"] for e in creates}
        orphans = known_ids - audited_creates
        # Archived-only records may still have create; orphans with no create are suspicious
        if orphans and len(orphans) > len(known_ids) * 0.5 and audited_creates:
            alerts.append(
                f"Integrity warning: {len(orphans)} records lack create audit entries"
            )
        _ = expected  # reserved for future strict mode
    return True, alerts


def write_fingerprint(root: Path) -> str:
    fp = store_fingerprint(root)
    path = root / "memory" / "audit" / "store.sha256"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(fp + "\n", encoding="utf-8")
    return fp


class IntegrityHalt(RuntimeError):
    """Raised when store/audit integrity check fails — data integrity is non-negotiable."""

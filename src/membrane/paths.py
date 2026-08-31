"""MEMBRANE_ROOT-relative path helpers with traversal protection."""

from __future__ import annotations

from pathlib import Path


class PathTraversalError(ValueError):
    """Raised when a path escapes MEMBRANE_ROOT."""


def ensure_under_root(root: Path, candidate: Path) -> Path:
    """Resolve candidate and ensure it stays under root."""
    root_resolved = root.resolve()
    resolved = (root_resolved / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise PathTraversalError(f"Path escapes MEMBRANE_ROOT: {candidate}") from exc
    return resolved


def safe_join(root: Path, *parts: str) -> Path:
    """Join parts under root; reject absolute segments and `..` escapes."""
    for part in parts:
        if part.startswith("/") or part.startswith("\\"):
            raise PathTraversalError(f"Absolute path segment not allowed: {part}")
        if ".." in Path(part).parts:
            raise PathTraversalError(f"Parent traversal not allowed: {part}")
    return ensure_under_root(root, Path(*parts))


def memory_dir(root: Path) -> Path:
    return safe_join(root, "memory")


def scope_path(root: Path, scope: str) -> Path:
    """Return directory for a scope like org, user-4821, session-abc."""
    if ".." in scope or "/" in scope or "\\" in scope:
        raise PathTraversalError(f"Invalid scope name: {scope}")
    if scope.startswith("session-"):
        return safe_join(root, "memory", scope, "staging")
    return safe_join(root, "memory", scope)


def memories_file(root: Path, scope: str) -> Path:
    return scope_path(root, scope) / "memories.jsonl"


def archive_file(root: Path, scope: str) -> Path:
    if ".." in scope or "/" in scope or "\\" in scope:
        raise PathTraversalError(f"Invalid scope name: {scope}")
    return safe_join(root, "memory", "archive", scope) / "memories.jsonl"


def audit_log(root: Path) -> Path:
    return safe_join(root, "memory", "audit", "main.log")


def contradictions_dir(root: Path) -> Path:
    return safe_join(root, "memory", "audit", "contradictions")


def embeddings_dir(root: Path) -> Path:
    return safe_join(root, "memory", "embeddings")


def init_layout(root: Path) -> None:
    """Create the on-disk memory layout."""
    dirs = [
        memory_dir(root) / "org",
        memory_dir(root) / "archive",
        safe_join(root, "memory", "audit"),
        contradictions_dir(root),
        embeddings_dir(root),
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    for f in (memories_file(root, "org"), audit_log(root)):
        f.parent.mkdir(parents=True, exist_ok=True)
        if not f.exists():
            f.touch()

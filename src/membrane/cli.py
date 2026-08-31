"""Membrane CLI."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Optional

import typer

from membrane import __version__
from membrane.config import load_config, membrane_root
from membrane.models import ConstructionBatch, Session
from membrane.paths import contradictions_dir, init_layout
from membrane.phases.construction import construct
from membrane.phases.governance import govern, resolve_contradiction
from membrane.phases.maintenance import health_report, maintain
from membrane.phases.retrieval import retrieve

app = typer.Typer(
    name="membrane",
    help="Membrane Memory OS — construction, governance, retrieval, maintenance.",
    no_args_is_help=True,
)


def _root(root: Optional[Path]) -> Path:
    return membrane_root(root)


def _config_for_root(root: Path, config: Optional[Path]):
    if config:
        return load_config(config)
    candidate = root / "config.yaml"
    if candidate.exists():
        return load_config(candidate)
    return load_config()


@app.command()
def version() -> None:
    """Print version."""
    typer.echo(__version__)


@app.command("init")
def init_cmd(
    root: Optional[Path] = typer.Option(None, "--root", help="MEMBRANE_ROOT path"),
    force: bool = typer.Option(False, "--force", help="Overwrite config if present"),
) -> None:
    """Create on-disk memory layout and seed config.yaml."""
    r = _root(root)
    r.mkdir(parents=True, exist_ok=True)
    init_layout(r)
    dest = r / "config.yaml"
    packaged = Path(__file__).resolve().parents[2] / "config.yaml"
    if not packaged.exists():
        packaged = Path.cwd() / "config.yaml"
    if dest.exists() and not force:
        typer.echo(f"Layout ready at {r} (config exists)")
    elif packaged.exists():
        shutil.copy(packaged, dest)
        typer.echo(f"Initialized Membrane root at {r}")
    else:
        typer.echo(f"Initialized Membrane root at {r} (no config.yaml template found)")


@app.command("construct")
def construct_cmd(
    input_path: Path = typer.Option(..., "--input", "-i", help="Sessions JSON/JSONL"),
    out: Path = typer.Option(..., "--out", "-o", help="Output batch JSON"),
    config: Optional[Path] = typer.Option(None, "--config"),
) -> None:
    """Phase 1: Construct memory batch from sessions."""
    cfg = load_config(config)
    sessions = _load_sessions(input_path)
    batch = construct(sessions, config=cfg)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(batch.model_dump_json(indent=2), encoding="utf-8")
    typer.echo(f"Constructed {len(batch.records)} records → {out}")


@app.command("govern")
def govern_cmd(
    batch_path: Path = typer.Option(..., "--batch", "-b"),
    user_id: Optional[str] = typer.Option(None, "--user-id"),
    session_id: Optional[str] = typer.Option(None, "--session-id"),
    root: Optional[Path] = typer.Option(None, "--root"),
    config: Optional[Path] = typer.Option(None, "--config"),
) -> None:
    """Phase 2: Govern and persist a constructed batch."""
    r = _root(root)
    init_layout(r)
    cfg = _config_for_root(r, config)
    batch = ConstructionBatch.model_validate_json(batch_path.read_text(encoding="utf-8"))
    result = govern(batch, r, user_id=user_id, session_id=session_id, config=cfg)
    typer.echo(
        json.dumps(
            {
                "approved": len(result.approved),
                "pending": len(result.pending),
                "rejected": len(result.rejected),
                "contradictions": [c.model_dump(mode="json") for c in result.contradictions],
            },
            indent=2,
        )
    )


@app.command("retrieve")
def retrieve_cmd(
    task: str = typer.Option(..., "--task", "-t"),
    scope: str = typer.Option(..., "--scope", "-s", help="e.g. user-4821"),
    budget: int = typer.Option(2000, "--budget"),
    root: Optional[Path] = typer.Option(None, "--root"),
    config: Optional[Path] = typer.Option(None, "--config"),
    include_archived: bool = typer.Option(False, "--include-archived"),
) -> None:
    """Phase 3: Retrieve memories for a task within token budget."""
    r = _root(root)
    cfg = _config_for_root(r, config)
    result = retrieve(
        r,
        task,
        scope,
        budget,
        config=cfg,
        include_archived=include_archived,
    )
    typer.echo(result.prompt_block)
    typer.echo(f"\n# selected={len(result.selected)} tokens={result.total_tokens}", err=True)


@app.command("maintain")
def maintain_cmd(
    mode: str = typer.Option(..., "--mode", help="daily|weekly|monthly"),
    root: Optional[Path] = typer.Option(None, "--root"),
    config: Optional[Path] = typer.Option(None, "--config"),
) -> None:
    """Phase 4: Run maintenance job."""
    r = _root(root)
    cfg = _config_for_root(r, config)
    try:
        result = maintain(r, mode, config=cfg)
    except Exception as exc:
        typer.secho(f"HALT: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(json.dumps(result, indent=2, default=str))


@app.command("status")
def status_cmd(
    root: Optional[Path] = typer.Option(None, "--root"),
) -> None:
    """Health summary and pending contradictions."""
    r = _root(root)
    report = health_report(r)
    pending = []
    cdir = contradictions_dir(r)
    if cdir.exists():
        for path in sorted(cdir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            if not data.get("resolved"):
                pending.append(data)
    typer.echo(
        json.dumps(
            {"health": report.model_dump(mode="json"), "unresolved_contradictions": pending},
            indent=2,
            default=str,
        )
    )


@app.command("resolve-contradiction")
def resolve_cmd(
    contradiction_id: str = typer.Option(..., "--id"),
    keep: str = typer.Option(..., "--keep", help="new|existing|both-archive"),
    root: Optional[Path] = typer.Option(None, "--root"),
) -> None:
    """Operator resolution for a held contradiction."""
    r = _root(root)
    result = resolve_contradiction(r, contradiction_id, keep)
    typer.echo(result.model_dump_json(indent=2))


@app.command("serve")
def serve_cmd(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8787, "--port"),
    root: Optional[Path] = typer.Option(None, "--root"),
) -> None:
    """Serve Membrane HTTP API (+ built SPA if web/dist exists)."""
    import os

    import uvicorn

    if root:
        os.environ["MEMBRANE_ROOT"] = str(root)
    from membrane.api.settings import get_api_settings

    get_api_settings.cache_clear()
    typer.echo(f"Membrane API on http://{host}:{port}")
    uvicorn.run("membrane.api.app:app", host=host, port=port, reload=False)


def _load_sessions(path: Path) -> list[Session]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if path.suffix == ".jsonl":
        return [Session.model_validate_json(ln) for ln in text.splitlines() if ln.strip()]
    data = json.loads(text)
    if isinstance(data, list):
        return [Session.model_validate(item) for item in data]
    if isinstance(data, dict) and "sessions" in data:
        return [Session.model_validate(item) for item in data["sessions"]]
    return [Session.model_validate(data)]


if __name__ == "__main__":
    app()

"""Membrane API tests (API key auth + JWT via OpenDesk Auth JWKS)."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient


@pytest.fixture()
def membrane_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = tmp_path / "membrane"
    root.mkdir()
    (root / "auth").mkdir()
    keys = {
        "test-key-admin": {
            "sub": "user-admin",
            "email": "admin@example.com",
            "role": "admin",
        },
        "test-key-op": {
            "sub": "op-1",
            "email": "op@example.com",
            "role": "operator",
        },
    }
    (root / "auth" / "api_keys.json").write_text(json.dumps(keys), encoding="utf-8")
    monkeypatch.setenv("MEMBRANE_ROOT", str(root))
    from membrane.api.settings import get_api_settings

    get_api_settings.cache_clear()
    yield root
    get_api_settings.cache_clear()


@pytest.fixture()
def client(membrane_root: Path):
    from membrane.api.app import create_app
    from membrane.api.deps import reset_jwks_client

    reset_jwks_client()
    app = create_app()
    with TestClient(app) as c:
        yield c
    reset_jwks_client()


def test_rejects_missing_auth(client: TestClient):
    r = client.get("/api/health")
    assert r.status_code == 401


def test_health_and_memory_crud(client: TestClient):
    headers = {"X-API-Key": "test-key-admin"}
    h = client.get("/api/health", headers=headers)
    assert h.status_code == 200, h.text
    body = h.json()
    assert "health" in body

    created = client.post(
        "/api/memories",
        headers=headers,
        json={"content": "Deploy with make release", "type": "skill", "scope": "user-admin"},
    )
    assert created.status_code == 200, created.text
    mid = created.json()["id"]

    listed = client.get("/api/memories?scope=user-admin", headers=headers)
    assert listed.status_code == 200
    assert any(m["id"] == mid for m in listed.json())

    patched = client.patch(
        f"/api/memories/{mid}",
        headers=headers,
        json={"content": "Deploy with make ship"},
    )
    assert patched.status_code == 200
    assert patched.json()["content"] == "Deploy with make ship"

    q = client.post(
        "/api/query",
        headers=headers,
        json={"task": "How do I deploy?", "scope": "user-admin", "budget": 2000},
    )
    assert q.status_code == 200
    assert "prompt_block" in q.json()

    archived = client.post(f"/api/memories/{mid}/archive", headers=headers)
    assert archived.status_code == 200
    assert archived.json()["state"] == "archived"


def test_scope_isolation(client: TestClient):
    admin = {"X-API-Key": "test-key-admin"}
    op = {"X-API-Key": "test-key-op"}
    client.post(
        "/api/memories",
        headers=admin,
        json={"content": "secret admin fact", "scope": "user-admin"},
    )
    denied = client.get("/api/memories?scope=user-admin", headers=op)
    assert denied.status_code == 403


def test_ingest_fixture(client: TestClient):
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "sessions.json"
    if not fixture.exists():
        pytest.skip("no fixtures/sessions.json")
    data = json.loads(fixture.read_text(encoding="utf-8"))
    sessions = data["sessions"] if isinstance(data, dict) else data
    headers = {"X-API-Key": "test-key-admin"}
    r = client.post(
        "/api/ingest",
        headers=headers,
        json={"sessions": sessions, "user_id": "admin", "session_id": "demo"},
    )
    assert r.status_code == 200, r.text
    assert "approved" in r.json()


def test_jwt_via_auth_jwks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Spin OpenDesk Auth on a free port; Membrane validates real JWTs."""
    auth_db = tmp_path / "auth.db"
    monkeypatch.setenv("AUTH_DATABASE_URL", f"sqlite+pysqlite:///{auth_db}")
    monkeypatch.setenv("AUTH_ISSUER", "https://auth.test.local")
    monkeypatch.setenv("AUTH_DEFAULT_AUDIENCES", "membrane")
    monkeypatch.setenv("AUTH_HOST", "127.0.0.1")

    from opendesk_auth.config import get_settings as auth_settings
    from opendesk_auth.crypto import _ensure_keys
    from opendesk_auth.db import init_db, reset_engine
    from opendesk_auth.app import create_app as create_auth_app

    auth_settings.cache_clear()
    _ensure_keys.cache_clear()
    reset_engine()
    init_db()
    auth_app = create_auth_app()

    # Pick a free port
    import socket

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    config = uvicorn.Config(auth_app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(50):
        if server.started:
            break
        time.sleep(0.05)
    assert server.started

    try:
        with TestClient(auth_app) as auth_client:
            tokens = auth_client.post(
                "/v1/auth/register",
                json={"email": "jwt@example.com", "password": "password123"},
            ).json()

        root = tmp_path / "mroot"
        root.mkdir()
        monkeypatch.setenv("MEMBRANE_ROOT", str(root))
        monkeypatch.setenv("MEMBRANE_AUTH_JWKS_URL", f"http://127.0.0.1:{port}/.well-known/jwks.json")
        monkeypatch.setenv("MEMBRANE_AUTH_ISSUER", "https://auth.test.local")
        from membrane.api.settings import get_api_settings
        from membrane.api.deps import reset_jwks_client
        from membrane.api.app import create_app

        get_api_settings.cache_clear()
        reset_jwks_client()
        app = create_app()
        with TestClient(app) as c:
            bad = c.get("/api/health")
            assert bad.status_code == 401
            ok = c.get("/api/health", headers={"Authorization": f"Bearer {tokens['access_token']}"})
            assert ok.status_code == 200, ok.text
            me = c.get("/api/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
            assert me.status_code == 200
            assert me.json()["role"] == "admin"  # first user
    finally:
        server.should_exit = True
        thread.join(timeout=2)
        auth_settings.cache_clear()
        _ensure_keys.cache_clear()
        reset_engine()
        from membrane.api.settings import get_api_settings
        from membrane.api.deps import reset_jwks_client

        get_api_settings.cache_clear()
        reset_jwks_client()

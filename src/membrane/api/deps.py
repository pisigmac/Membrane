"""Auth dependency — verify Bearer JWT via OpenDesk Auth JWKS (or local API keys)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jwt
from fastapi import Header, HTTPException, status
from jwt import PyJWKClient

from membrane.api.settings import APISettings, get_api_settings


@dataclass
class Principal:
    sub: str
    email: str | None
    org_id: str | None
    workspace_id: str | None
    role: str  # admin|operator|viewer
    via: str  # jwt|api_key

    @property
    def user_scope(self) -> str:
        return f"user-{self.sub}"


_jwks_client: PyJWKClient | None = None
_jwks_url_cached: str | None = None


def _get_jwks_client(settings: APISettings) -> PyJWKClient:
    global _jwks_client, _jwks_url_cached
    if _jwks_client is None or _jwks_url_cached != settings.auth_jwks_url:
        _jwks_client = PyJWKClient(settings.auth_jwks_url, cache_keys=True)
        _jwks_url_cached = settings.auth_jwks_url
    return _jwks_client


def reset_jwks_client() -> None:
    global _jwks_client, _jwks_url_cached
    _jwks_client = None
    _jwks_url_cached = None


def verify_jwt(token: str, settings: APISettings | None = None) -> dict[str, Any]:
    settings = settings or get_api_settings()
    try:
        client = _get_jwks_client(settings)
        signing_key = client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=settings.auth_issuer,
            options={"verify_aud": False, "require": ["exp", "sub"]},
        )
        aud = claims.get("aud")
        auds = aud if isinstance(aud, list) else [aud]
        if settings.auth_audience not in auds:
            raise HTTPException(status_code=401, detail="Invalid audience")
        return claims
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc


def load_api_keys(root: Path) -> dict[str, dict[str, Any]]:
    path = root / "auth" / "api_keys.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def get_principal(
    authorization: str | None = Header(default=None),
    x_org_id: str | None = Header(default=None, alias="X-Org-ID"),
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-ID"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> Principal:
    settings = get_api_settings()
    root = settings.root_path()

    if x_api_key:
        keys = load_api_keys(root)
        meta = keys.get(x_api_key)
        if not meta:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return Principal(
            sub=str(meta.get("sub", "api-key")),
            email=meta.get("email"),
            org_id=x_org_id or meta.get("org_id"),
            workspace_id=x_workspace_id or meta.get("workspace_id"),
            role=meta.get("role", "operator"),
            via="api_key",
        )

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    claims = verify_jwt(token, settings)
    roles = claims.get("roles") or {}
    role = roles.get(settings.auth_audience, "viewer")
    return Principal(
        sub=str(claims["sub"]),
        email=claims.get("email"),
        org_id=x_org_id or claims.get("org_id"),
        workspace_id=x_workspace_id or claims.get("workspace_id"),
        role=role,
        via="jwt",
    )


def assert_role(principal: Principal, *allowed: str) -> None:
    if principal.role == "admin":
        return
    if principal.role not in allowed:
        raise HTTPException(status_code=403, detail=f"Requires role: {', '.join(allowed)}")


def can_access_scope(principal: Principal, scope: str) -> bool:
    if principal.role == "admin":
        return True
    if scope == principal.user_scope:
        return True
    if scope.startswith("session-") and principal.role in {"operator", "viewer"}:
        return True
    return False


def assert_scope(principal: Principal, scope: str) -> None:
    if not can_access_scope(principal, scope):
        raise HTTPException(status_code=403, detail=f"No access to scope {scope}")

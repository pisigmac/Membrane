"""API settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class APISettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MEMBRANE_", env_file=".env", extra="ignore")

    root: str = "./.membrane"
    auth_jwks_url: str = "http://127.0.0.1:8090/.well-known/jwks.json"
    auth_issuer: str = "https://auth.pisigma.local"
    auth_audience: str = "membrane"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    host: str = "127.0.0.1"
    port: int = 8787
    # Dev bypass: when set, accept unsigned local tokens for tests only
    allow_dev_auth: bool = False
    web_dist: str = ""

    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def root_path(self) -> Path:
        return Path(self.root).expanduser().resolve()


@lru_cache
def get_api_settings() -> APISettings:
    return APISettings()

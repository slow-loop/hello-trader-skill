from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import yaml

SKILL_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = SKILL_ROOT / "data" / "config" / "agent.yaml"
ACCOUNT_DIR = SKILL_ROOT / "data" / "account"


class ConfigError(RuntimeError):
    pass


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise ConfigError(
            f"Missing config {CONFIG_PATH}. Run `tw init --name <agent-name>` first."
        )
    with CONFIG_PATH.open() as f:
        return yaml.safe_load(f) or {}


def save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)


class Client:
    def __init__(self, base_url: str, token: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token

    @classmethod
    def from_config(cls) -> "Client":
        cfg = load_config()
        token = cfg.get("token") or ""
        if not token:
            raise ConfigError("agent.yaml has no token; re-run `tw init`.")
        return cls(cfg["backend_url"], token)

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def request(
        self, method: str, path: str, *, json: Any = None, params: dict | None = None
    ) -> Any:
        url = f"{self.base_url}{path}"
        r = httpx.request(method, url, json=json, params=params, headers=self._headers(), timeout=30.0)
        if r.status_code >= 400:
            raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text}")
        if r.headers.get("content-type", "").startswith("application/json"):
            return r.json()
        return r.text

    def get(self, url: str, **params: Any) -> Any:
        clean = {k: v for k, v in params.items() if v is not None}
        return self.request("GET", url, params=clean)

    def post(self, path: str, json: Any) -> Any:
        return self.request("POST", path, json=json)

    def put(self, path: str, json: Any) -> Any:
        return self.request("PUT", path, json=json)

    def patch(self, path: str, json: Any) -> Any:
        return self.request("PATCH", path, json=json)

    def delete(self, path: str) -> Any:
        return self.request("DELETE", path)

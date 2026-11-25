from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from secrets import token_urlsafe


def _load_local_env() -> None:
    """读取项目根目录的简单 .env，且不覆盖系统环境变量。"""

    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"").strip("'")
        if key:
            os.environ.setdefault(key, value)


_load_local_env()


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "智能用户反馈分析与工单管理系统")
    app_env: str = os.getenv("APP_ENV", "development")
    api_prefix: str = "/api/v1"
    secret_key: str = os.getenv("SECRET_KEY", "")
    access_token_expire_minutes: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120")
    )
    database_url: str = os.getenv(
        "DATABASE_URL", "sqlite+pysqlite:///./feedback_ticket.db"
    )
    cors_origins_raw: str = os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    )

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins_raw.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    configured_key = os.getenv("SECRET_KEY", "").strip()
    if Settings().app_env != "development" and len(configured_key) < 32:
        raise RuntimeError("非开发环境必须配置至少 32 个字符的 SECRET_KEY")
    return Settings(secret_key=configured_key or token_urlsafe(32))


"""智能分析模块的独立配置。

配置只从环境变量（含项目根目录 .env）读取，不修改 core/config.py，
避免与 1 号维护的公共配置产生冲突。请求到来时才读取，保证 .env 已加载。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

SUPPORTED_PROVIDERS = ("deepseek", "mock", "off")


class AnalysisConfigError(RuntimeError):
    """智能分析配置缺失或不合法。"""


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise AnalysisConfigError(f"{name} 必须是数字，当前值：{raw}") from exc


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise AnalysisConfigError(f"{name} 必须是整数，当前值：{raw}") from exc


@dataclass(frozen=True, slots=True)
class AnalysisSettings:
    provider: str
    api_key: str
    base_url: str
    model: str
    timeout_seconds: float
    max_retries: int
    temperature: float
    max_input_chars: int

    @property
    def enabled(self) -> bool:
        return self.provider != "off"

    @property
    def is_mock(self) -> bool:
        return self.provider == "mock"


@lru_cache
def get_analysis_settings() -> AnalysisSettings:
    provider = (os.getenv("ANALYSIS_PROVIDER", "deepseek") or "deepseek").strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise AnalysisConfigError(
            f"ANALYSIS_PROVIDER 只支持 {', '.join(SUPPORTED_PROVIDERS)}，当前值：{provider}"
        )

    api_key = (
        os.getenv("ANALYSIS_API_KEY", "").strip()
        or os.getenv("DEEPSEEK_API_KEY", "").strip()
    )
    return AnalysisSettings(
        provider=provider,
        api_key=api_key,
        base_url=(os.getenv("ANALYSIS_BASE_URL", "https://api.deepseek.com/v1") or "").strip().rstrip("/"),
        model=(os.getenv("ANALYSIS_MODEL", "deepseek-chat") or "deepseek-chat").strip(),
        timeout_seconds=_env_float("ANALYSIS_TIMEOUT_SECONDS", 30.0),
        max_retries=max(0, min(_env_int("ANALYSIS_MAX_RETRIES", 1), 3)),
        temperature=min(max(_env_float("ANALYSIS_TEMPERATURE", 0.2), 0.0), 1.0),
        max_input_chars=max(500, _env_int("ANALYSIS_MAX_INPUT_CHARS", 4000)),
    )

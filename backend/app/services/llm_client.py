"""模型客户端：统一封装“调用大模型并拿到一段文本”的行为。

设计要点：
- 只依赖 httpx，使用 OpenAI 兼容的 /chat/completions 协议，DeepSeek、通义、Kimi、
  智谱等平台都可以通过改 ANALYSIS_BASE_URL 与 ANALYSIS_MODEL 切换，不必改代码。
- 错误按“可重试/不可重试”分类，超时、429、5xx 才重试，认证错误立即失败。
- 提供 MockChatModel 供无密钥的课堂演示与自动测试使用；其结果会在数据库和接口中
  明确标记为 mock-demo，绝不冒充真实模型输出。
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.services.analysis_config import AnalysisSettings
from app.services.analysis_prompts import CATEGORY_LABELS


class LLMCallError(RuntimeError):
    """模型调用失败的统一异常。kind 用于统计和降级展示。"""

    def __init__(
        self,
        kind: str,
        message: str,
        *,
        retryable: bool = False,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.retryable = retryable
        self.status_code = status_code


class AnalysisNotConfigured(RuntimeError):
    """没有配置模型密钥或显式关闭了智能分析。"""


class ChatModel(Protocol):
    """最小模型接口，便于测试替换为假模型。"""

    name: str
    is_mock: bool

    def complete(self, system_prompt: str, user_prompt: str) -> str: ...


@dataclass(slots=True)
class DeepSeekChatModel:
    """OpenAI 兼容协议的聊天补全客户端。"""

    settings: AnalysisSettings

    @property
    def name(self) -> str:
        return self.settings.model

    @property
    def is_mock(self) -> bool:
        return False

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{self.settings.base_url}/chat/completions"
        payload = {
            "model": self.settings.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.settings.temperature,
            "max_tokens": 800,
            "stream": False,
            # DeepSeek 等平台支持 JSON 模式；若切换到不支持的平台，把该字段删掉即可。
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json",
        }
        timeout = httpx.Timeout(
            self.settings.timeout_seconds, connect=min(5.0, self.settings.timeout_seconds)
        )
        attempts = self.settings.max_retries + 1
        last_error: LLMCallError | None = None

        for attempt in range(attempts):
            try:
                with httpx.Client(timeout=timeout) as client:
                    response = client.post(url, headers=headers, json=payload)
            except httpx.TimeoutException as exc:
                last_error = LLMCallError("TIMEOUT", "模型服务响应超时", retryable=True)
                error: LLMCallError = last_error
            except httpx.HTTPError as exc:
                last_error = LLMCallError("NETWORK", f"模型服务连接失败：{type(exc).__name__}", retryable=True)
                error = last_error
            else:
                if response.status_code in (401, 403):
                    raise LLMCallError(
                        "AUTH",
                        "模型服务认证失败，请检查 ANALYSIS_API_KEY 是否有效",
                        status_code=response.status_code,
                    )
                if response.status_code == 429:
                    error = LLMCallError("RATE_LIMIT", "模型服务限流（HTTP 429）", retryable=True, status_code=429)
                elif response.status_code >= 500:
                    error = LLMCallError(
                        "SERVER",
                        f"模型服务异常（HTTP {response.status_code}）",
                        retryable=True,
                        status_code=response.status_code,
                    )
                elif response.status_code >= 400:
                    raise LLMCallError(
                        "HTTP",
                        f"模型服务拒绝了请求（HTTP {response.status_code}）",
                        status_code=response.status_code,
                    )
                else:
                    return self._extract_content(response)
            last_error = error
            if error.retryable and attempt < attempts - 1:
                time.sleep(0.5 * (2**attempt))
                continue
            raise error

        raise last_error or LLMCallError("UNKNOWN", "模型调用失败")

    @staticmethod
    def _extract_content(response: httpx.Response) -> str:
        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise LLMCallError("BAD_RESPONSE", "模型返回内容不是合法 JSON", retryable=False) from exc
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMCallError("BAD_RESPONSE", "模型返回结构缺少 choices.message.content") from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMCallError("EMPTY", "模型返回内容为空", retryable=False)
        return content


@dataclass(slots=True)
class MockChatModel:
    """离线演示模型：固定关键词规则，输出与真实模型相同的 JSON 结构。

    仅用于没有 API 密钥的课堂演示和自动测试。结果中的 model 名称为 mock-demo，
    接口会返回 status=DEGRADED、needs_manual_review=true，报告与截图必须说明这一点。
    """

    name: str = "mock-demo-v1"
    is_mock: bool = True

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        description = user_prompt.split("用户描述：", 1)[-1].split("（描述是否被截断", 1)[0]
        quick_rules = [
            ("PERFORMANCE", ("慢", "卡", "超时", "很久", "加载不动")),
            ("FEATURE_SUGGESTION", ("希望", "建议", "能不能加", "最好能")),
            ("USAGE_CONSULTATION", ("怎么", "如何", "在哪里", "能不能导", "请问")),
            ("ACCOUNT_LOGIN", ("登录", "密码", "验证码", "注册", "账号")),
        ]
        category = "FUNCTION_ERROR"
        for code, words in quick_rules:
            if any(word in description for word in words):
                category = code
                break
        label = CATEGORY_LABELS[category]
        short = re.split(r"[。，,；;]", description.strip(), maxsplit=1)[0][:14].strip()
        payload = {
            "title": f"{label}：{short}" if short else f"{label}反馈",
            "category": category,
            "summary": description.strip()[:80],
            "keywords": [label, "演示模式"],
            "confidence": 0.4,
            "reason": "离线演示模式的固定关键词规则，未调用真实模型",
        }
        return json.dumps(payload, ensure_ascii=False)


def build_chat_model(settings: AnalysisSettings) -> ChatModel:
    if settings.provider == "mock":
        return MockChatModel()
    if settings.provider == "deepseek":
        if not settings.api_key:
            raise AnalysisNotConfigured(
                "未配置模型密钥：请在项目根目录 .env 中设置 ANALYSIS_API_KEY（或 DEEPSEEK_API_KEY）"
            )
        return DeepSeekChatModel(settings)
    raise AnalysisNotConfigured("智能分析已关闭：ANALYSIS_PROVIDER=off")

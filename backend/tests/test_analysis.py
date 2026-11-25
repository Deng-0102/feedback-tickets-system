"""3 号智能分析模块的自动测试：成功、降级、失败、权限、预览与缓存复用。

全部使用 FakeModel，不消耗真实模型额度，也不依赖网络。
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.api.routes.analysis import get_chat_model
from app.db.session import SessionLocal
from app.main import app
from app.models.analysis import AnalysisResult
from app.models.ticket import TicketRecord
from app.services.analysis_config import get_analysis_settings
from app.services.llm_client import LLMCallError

DESCRIPTION = "修改密码后一直无法登录，重新安装也没有解决，着急使用。"
SUCCESS_PAYLOAD = {
    "title": "修改密码后无法登录",
    "category": "ACCOUNT_LOGIN",
    "summary": "用户修改密码后无法登录，重装后仍未解决，影响正常使用。",
    "keywords": ["密码修改", "无法登录"],
    "confidence": 0.92,
    "reason": "故障发生在修改密码之后，现象为登录失败",
}


class FakeModel:
    name = "fake-model"
    is_mock = False

    def __init__(self, content: str | None = None, error: Exception | None = None) -> None:
        self.content = content
        self.error = error
        self.calls = 0

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.content or ""


def sign_in(client, username: str = "user001") -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login", json={"username": username, "password": "Demo123!"}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def create_ticket(client, headers: dict[str, str], description: str = DESCRIPTION) -> int:
    response = client.post(
        "/api/v1/tickets",
        json={"description": description, "feature_module": "账号中心"},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def analyse(client, model: FakeModel, ticket_id: int, headers: dict[str, str], query: str = "?force=true"):
    app.dependency_overrides[get_chat_model] = lambda: model
    try:
        return client.post(f"/api/v1/tickets/{ticket_id}/analysis{query}", headers=headers)
    finally:
        app.dependency_overrides.pop(get_chat_model, None)


def test_success_updates_ticket_and_writes_record(client):
    headers = sign_in(client)
    ticket_id = create_ticket(client, headers)
    model = FakeModel(json.dumps(SUCCESS_PAYLOAD, ensure_ascii=False))

    response = analyse(client, model, ticket_id, headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "SUCCESS"
    assert data["category"] == "ACCOUNT_LOGIN"
    assert data["category_label"] == "账号登录"
    assert data["needs_manual_review"] is False
    assert data["applied"] is True
    assert data["model_name"] == "fake-model"

    ticket = client.get(f"/api/v1/tickets/{ticket_id}", headers=headers).json()["data"]
    assert ticket["title"] == "修改密码后无法登录"
    assert ticket["category"] == "ACCOUNT_LOGIN"
    assert ticket["summary"] == SUCCESS_PAYLOAD["summary"]

    with SessionLocal() as db:
        results = db.scalars(select(AnalysisResult)).all()
        records = db.scalars(select(TicketRecord).where(TicketRecord.action == "AI_ANALYSIS")).all()
    assert len(results) == 1
    assert results[0].generated_title == "修改密码后无法登录"
    assert results[0].confidence == pytest.approx(0.92)
    assert len(records) == 1


def test_chinese_category_and_missing_confidence_is_degraded(client):
    headers = sign_in(client)
    ticket_id = create_ticket(client, headers)
    payload = dict(SUCCESS_PAYLOAD, category="账号登录", confidence=None)
    model = FakeModel(json.dumps(payload, ensure_ascii=False))

    data = analyse(client, model, ticket_id, headers).json()["data"]

    assert data["status"] == "DEGRADED"
    assert data["category"] == "ACCOUNT_LOGIN"
    assert data["needs_manual_review"] is True


def test_invalid_json_fails_without_touching_ticket(client):
    headers = sign_in(client)
    ticket_id = create_ticket(client, headers)
    model = FakeModel("抱歉，我无法完成这个任务。")

    response = analyse(client, model, ticket_id, headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "FAILED"
    assert data["error"].startswith("BAD_FORMAT")
    assert data["fallback_used"] is True

    ticket = client.get(f"/api/v1/tickets/{ticket_id}", headers=headers).json()["data"]
    assert ticket["title"] == "待智能整理"
    assert ticket["category"] is None

    with SessionLocal() as db:
        assert db.scalars(select(AnalysisResult)).all() == []
        failed = db.scalars(
            select(TicketRecord).where(TicketRecord.action == "AI_ANALYSIS_FAILED")
        ).all()
    assert len(failed) == 1
    assert "BAD_FORMAT" in failed[0].content

    latest = client.get(f"/api/v1/tickets/{ticket_id}/analysis", headers=headers)
    assert latest.status_code == 404


def test_model_timeout_is_reported_as_failure(client):
    headers = sign_in(client)
    ticket_id = create_ticket(client, headers)
    model = FakeModel(error=LLMCallError("TIMEOUT", "模型服务响应超时", retryable=True))

    data = analyse(client, model, ticket_id, headers).json()["data"]

    assert data["status"] == "FAILED"
    assert data["error"] == "TIMEOUT: 模型服务响应超时"
    assert data["title"].startswith("修改密码后")
    assert len(data["title"]) <= 20


def test_unknown_category_is_rejected_for_manual_review(client):
    headers = sign_in(client)
    ticket_id = create_ticket(client, headers)
    payload = dict(SUCCESS_PAYLOAD, category="NETWORK")
    model = FakeModel(json.dumps(payload, ensure_ascii=False))

    data = analyse(client, model, ticket_id, headers).json()["data"]

    assert data["status"] == "FAILED"
    assert data["category"] is None
    assert "分类不合法" in data["error"]


def test_user_cannot_analyse_other_users_ticket(client):
    owner = sign_in(client, "user001")
    other = sign_in(client, "user002")
    ticket_id = create_ticket(client, owner)

    response = analyse(client, FakeModel(json.dumps(SUCCESS_PAYLOAD)), ticket_id, other)

    assert response.status_code == 404
    assert response.json()["code"] == 40400


def test_preview_returns_suggestion_without_creating_ticket(client):
    headers = sign_in(client)
    app.dependency_overrides[get_chat_model] = lambda: FakeModel(
        json.dumps(SUCCESS_PAYLOAD, ensure_ascii=False)
    )
    try:
        response = client.post(
            "/api/v1/analysis/preview",
            json={"description": DESCRIPTION, "feature_module": "账号中心"},
            headers=headers,
        )
    finally:
        app.dependency_overrides.pop(get_chat_model, None)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["title"] == "修改密码后无法登录"
    assert data["ticket_id"] is None
    assert data["result_id"] is None

    with SessionLocal() as db:
        assert db.scalars(select(AnalysisResult)).all() == []


def test_second_request_reuses_cached_result(client):
    headers = sign_in(client)
    ticket_id = create_ticket(client, headers)
    model = FakeModel(json.dumps(SUCCESS_PAYLOAD, ensure_ascii=False))

    analyse(client, model, ticket_id, headers)
    second = analyse(client, model, ticket_id, headers, query="")

    assert second.status_code == 200
    assert second.json()["data"]["cached"] is True
    assert model.calls == 1


def test_analysis_disabled_returns_503(client, monkeypatch):
    headers = sign_in(client)
    ticket_id = create_ticket(client, headers)

    with monkeypatch.context() as patch:
        patch.setenv("ANALYSIS_PROVIDER", "off")
        get_analysis_settings.cache_clear()
        try:
            response = client.post(
                f"/api/v1/tickets/{ticket_id}/analysis", headers=headers
            )
        finally:
            get_analysis_settings.cache_clear()

    assert response.status_code == 503
    assert response.json()["code"] == 50300
    assert "关闭" in response.json()["message"]

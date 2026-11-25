import pytest

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.ticket import TicketRecord


def sign_in(client, username):
    response = client.post(
        "/api/v1/auth/login", json={"username": username, "password": "Demo123!"}
    )
    assert response.status_code == 200
    data = response.json()["data"]
    return {"Authorization": f"Bearer {data['access_token']}"}, data["user"]["id"]


def test_health(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "code": 0,
        "message": "success",
        "data": {"status": "ok"},
    }


@pytest.mark.parametrize(
    ("username", "role"), [("user001", "USER"), ("agent001", "AGENT"), ("admin", "ADMIN")]
)
def test_login_and_current_user(client, username, role):
    headers, user_id = sign_in(client, username)
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["data"]["id"] == user_id
    assert me.json()["data"]["role"] == role


def test_role_guard_blocks_normal_user(client):
    headers, _ = sign_in(client, "user001")
    response = client.get("/api/v1/users", headers=headers)
    assert response.status_code == 403
    assert response.json()["code"] == 40300


def test_invalid_password_is_rejected(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "user001", "password": "Wrong123!"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == 40100


def test_unauthenticated_ticket_list_is_rejected(client):
    response = client.get("/api/v1/tickets")
    assert response.status_code == 401
    assert response.json()["code"] == 40100


def test_login_validation_does_not_echo_password(client):
    response = client.post(
        "/api/v1/auth/login", json={"username": "user001", "password": "short!"}
    )
    assert response.status_code == 422
    assert response.json()["data"]["errors"][0]["loc"] == ["body", "password"]
    assert "short!" not in response.text


def test_ticket_lifecycle_and_visibility(client):
    user, user_id = sign_in(client, "user001")
    other_user, _ = sign_in(client, "user002")
    agent, agent_id = sign_in(client, "agent001")
    other_agent, _ = sign_in(client, "agent002")
    admin, admin_id = sign_in(client, "admin")
    tickets_url = "/api/v1/tickets"

    created = client.post(
        tickets_url,
        headers=user,
        json={"description": "修改密码后一直无法登录，重新安装仍无法解决。", "feature_module": "账号中心"},
    )
    assert created.status_code == 201
    ticket = created.json()["data"]
    assert ticket["status"] == "PENDING_ASSIGNMENT"
    assert ticket["assignee_id"] is None
    ticket_url = f"{tickets_url}/{ticket['id']}"
    assign_url = f"{ticket_url}/assign"
    status_url = f"{ticket_url}/status"

    assert client.get(ticket_url, headers=agent).status_code == 404
    assert client.get(ticket_url, headers=other_user).status_code == 404
    assert client.patch(assign_url, headers=user, json={"assignee_id": agent_id}).status_code == 403
    assert client.patch(assign_url, headers=admin, json={"assignee_id": user_id}).status_code == 400
    assert client.patch(status_url, headers=admin, json={"status": "PENDING"}).status_code == 409

    assigned = client.patch(assign_url, headers=admin, json={"assignee_id": agent_id})
    assert assigned.status_code == 200
    assert assigned.json()["data"]["status"] == "PENDING"
    assert assigned.json()["data"]["assignee_id"] == agent_id
    for headers in (user, agent, admin):
        listing = client.get(tickets_url, headers=headers)
        assert [item["id"] for item in listing.json()["data"]] == [ticket["id"]]
    for headers in (other_user, other_agent):
        assert client.get(tickets_url, headers=headers).json()["data"] == []
        assert client.patch(status_url, headers=headers, json={"status": "IN_PROGRESS"}).status_code == 404
    assert client.patch(status_url, headers=agent, json={"status": "RESOLVED"}).status_code == 409

    for headers, target, content in (
        (agent, "IN_PROGRESS", "检查账号状态"),
        (agent, "RESOLVED", "重置旧的登录会话"),
        (user, "REOPENED", "新设备上仍无法登录"),
        (agent, "IN_PROGRESS", "检查新设备上的报错"),
        (agent, "RESOLVED", "更新登录状态"),
        (user, "CLOSED", "已验证可以登录"),
    ):
        updated = client.patch(status_url, headers=headers, json={"status": target, "content": content})
        assert updated.status_code == 200, updated.text
        data = updated.json()["data"]
        assert data["status"] == target
        if target == "REOPENED":
            assert data["resolved_at"] is None
        elif target == "CLOSED":
            assert data["resolved_at"] and data["closed_at"]
    assert client.patch(status_url, headers=user, json={"status": "REOPENED"}).status_code == 409

    with SessionLocal() as db:
        records = db.scalars(select(TicketRecord).where(TicketRecord.ticket_id == ticket["id"]).order_by(TicketRecord.id)).all()
        assert [record.action for record in records] == ["CREATE", "ASSIGN", *(["STATUS_CHANGE"] * 6)]
        assert [record.operator_id for record in records] == [user_id, admin_id, agent_id, agent_id, user_id, agent_id, agent_id, user_id]
        assert records[4].content == "新设备上仍无法登录"


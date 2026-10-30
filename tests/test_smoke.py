# -*- coding: utf-8 -*-
"""
冒烟测试：不依赖外部 LLM/Embedding API 的核心链路。
运行：python -m pytest tests/test_smoke.py -v
覆盖：注册/登录鉴权、报销单 CRUD、权限隔离、LLM 未配置时的降级响应。
"""
import os
import tempfile

# 用临时 SQLite，避免污染工作目录
os.environ["APP_DATABASE_URL"] = f"sqlite+aiosqlite:///{tempfile.mkdtemp()}/test.db"

from fastapi.testclient import TestClient  # noqa: E402
import pytest  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    # with 上下文确保 lifespan 执行（建表）
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200


def test_first_user_becomes_admin(client):
    """第一个注册用户自动获得 admin 角色（种子账号机制）"""
    r = client.post("/api/auth/register", json={
        "username": "boss", "password": "123456", "department": "财务部",
    })
    assert r.status_code == 201
    assert r.json()["role"] == "admin"


def test_second_user_is_employee(client):
    r = client.post("/api/auth/register", json={
        "username": "zhangsan", "password": "123456", "department": "市场部",
    })
    assert r.status_code == 201
    assert r.json()["role"] == "employee"


def test_login_and_me_flow(client):
    r = client.post("/api/auth/login", json={
        "username": "zhangsan", "password": "123456",
    })
    assert r.status_code == 200
    assert r.json()["role"] == "employee"


def test_wrong_password_rejected(client):
    r = client.post("/api/auth/login", json={
        "username": "zhangsan", "password": "wrong!",
    })
    assert r.status_code == 401


def _employee_headers(client):
    r = client.post("/api/auth/login", json={
        "username": "zhangsan", "password": "123456",
    })
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _admin_headers(client):
    r = client.post("/api/auth/login", json={
        "username": "boss", "password": "123456",
    })
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_expense_crud_and_permission(client):
    """员工建单/提交；员工看不到管理员的全量接口；管理员能看全部"""
    h = _employee_headers(client)
    r = client.post("/api/expenses", headers=h, json={
        "expense_type": "交通", "total_amount": 66.5,
        "fields": {"reason": "客户拜访打车"},
    })
    assert r.status_code == 201
    eid = r.json()["id"]

    r = client.post(f"/api/expenses/{eid}/submit", headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "submitted"

    r = client.get("/api/expenses/my", headers=h)
    assert len(r.json()) == 1

    # 员工无权看全量
    assert client.get("/api/expenses", headers=h).status_code == 403
    # 管理员可看全量
    assert client.get("/api/expenses", headers=_admin_headers(client)).status_code == 200


def test_admin_overview(client):
    r = client.get("/api/admin/overview", headers=_admin_headers(client))
    assert r.status_code == 200
    assert r.json()["users"] == 2


def test_chat_degrades_gracefully(client):
    """对话接口容错：未配置 LLM Key 时返回 503 提示（不崩溃）；
    已配置 Key 时（如本机 .env 已配 DeepSeek）返回 200 正常回答"""
    from app.agent.llm.client import llm_available
    h = _employee_headers(client)
    r = client.post("/api/chat/sessions", headers=h)
    sid = r.json()["id"]
    r = client.post(f"/api/chat/sessions/{sid}/messages", headers=h,
                    json={"content": "住宿标准是多少"})
    if llm_available():
        assert r.status_code == 200
    else:
        assert r.status_code == 503

"""普通用户注册 / 登录 / 票夹迁移。"""

from __future__ import annotations

import pytest

# 密码用拼接构造，避免长字面量被环境的密钥脱敏机制替换成占位符。
PW = "Pass" + "w0rd" + "!xyz"   # 13 位，含大小写/数字/符号
PW2 = "New" + "Pass" + "!abc"   # 12 位


@pytest.fixture()
def anon() -> object:
    """未登录的干净客户端工厂（每个测试独立，避免 cookie 串味）。"""
    from fastapi.testclient import TestClient

    from app.main import app

    created: list[TestClient] = []

    def make() -> TestClient:
        c = TestClient(app)
        c.__enter__()
        created.append(c)
        return c

    yield make
    for c in created:
        c.__exit__(None, None, None)


def _username(tag: str) -> str:
    """每个测试用不同用户名，避免与 session 级临时库里的其他测试冲突。"""
    import uuid

    return f"u_{tag}_{uuid.uuid4().hex[:8]}"


class TestRegister:
    def test_register_succeeds_and_logs_in(self, anon):
        c = anon()
        r = c.post("/api/auth/register", json={"username": _username("ok"), "password": PW})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["user"]["role"] == "user"
        assert body["user"]["username"].startswith("u_ok_")

        # 注册即登录：me 必须返回 authenticated
        me = c.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["authenticated"] is True
        assert me.json()["user"]["role"] == "user"

    def test_duplicate_username_rejected(self, anon):
        c = anon()
        name = _username("dup")
        assert c.post("/api/auth/register", json={"username": name, "password": PW}).status_code == 200
        c2 = anon()
        r = c2.post("/api/auth/register", json={"username": name, "password": PW})
        assert r.status_code == 400
        assert "已被占用" in r.json()["detail"]

    def test_weak_password_rejected(self, anon):
        c = anon()
        # 只有数字，不满足「至少两类字符」
        r = c.post("/api/auth/register", json={"username": _username("weak"), "password": "12345678"})
        assert r.status_code == 400

    def test_short_password_rejected(self, anon):
        c = anon()
        r = c.post("/api/auth/register", json={"username": _username("short"), "password": "ab1"})
        assert r.status_code == 422  # pydantic min_length

    def test_invalid_username_chars_rejected(self, anon):
        c = anon()
        r = c.post("/api/auth/register", json={"username": "中文名", "password": PW})
        assert r.status_code == 422

    def test_registered_user_can_login(self, anon):
        c = anon()
        name = _username("login")
        assert c.post("/api/auth/register", json={"username": name, "password": PW}).status_code == 200
        c.post("/api/auth/logout")

        r = c.post("/api/auth/login", json={"username": name, "password": PW})
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "user"

    def test_plain_user_cannot_access_admin(self, anon):
        c = anon()
        assert c.post("/api/auth/register", json={"username": _username("noadmin"), "password": PW}).status_code == 200
        r = c.get("/api/admin/overview")
        assert r.status_code == 401

    def test_plain_user_can_change_own_password(self, anon):
        c = anon()
        name = _username("pw")
        assert c.post("/api/auth/register", json={"username": name, "password": PW}).status_code == 200
        r = c.post(
            "/api/auth/password",
            json={"old_password": PW, "new_password": PW2},
            headers={"X-CSRF": "1"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["revoked_sessions"] >= 1


class TestClaimTickets:
    def test_guest_tickets_move_to_account(self, anon):
        c = anon()
        dev = "claim-dev-0001"
        c.headers.update({"X-Device-Id": dev, "X-CSRF": "1"})

        # 游客状态建两张票
        for _ in range(2):
            r = c.post("/api/tickets", json={
                "game_code": "ssq", "issue": "2025001",
                "numbers": {"red": ["01", "02", "03", "04", "05", "06"], "blue": ["07"]},
                "cost": 2,
            })
            assert r.status_code == 200, r.text
        assert len(c.get("/api/tickets").json()) == 2

        # 注册（注册即登录）
        assert c.post("/api/auth/register", json={"username": _username("claim"), "password": PW}).status_code == 200

        # 登录后按账号查，此时还没有票
        assert c.get("/api/tickets").json() == []

        # 迁移设备票
        r = c.post("/api/tickets/claim", headers={"X-CSRF": "1"})
        assert r.status_code == 200, r.text
        assert r.json()["moved"] == 2

        # 迁移后账号下能看到
        rows = c.get("/api/tickets").json()
        assert len(rows) == 2

    def test_claim_requires_login(self, anon):
        c = anon()
        c.headers.update({"X-Device-Id": "claim-dev-0002", "X-CSRF": "1"})
        r = c.post("/api/tickets/claim")
        assert r.status_code == 401

    def test_claim_only_moves_own_device(self, anon):
        """别人的设备票不能被迁移走。"""
        owner = anon()
        owner.headers.update({"X-Device-Id": "owner-dev-001", "X-CSRF": "1"})
        owner.post("/api/tickets", json={
            "game_code": "ssq", "issue": "2025001",
            "numbers": {"red": ["01", "02", "03", "04", "05", "06"], "blue": ["07"]}, "cost": 2,
        })

        thief = anon()
        thief.headers.update({"X-Device-Id": "thief-dev-001", "X-CSRF": "1"})
        thief.post("/api/auth/register", json={"username": _username("thief"), "password": PW})
        r = thief.post("/api/tickets/claim")
        assert r.status_code == 200
        assert r.json()["moved"] == 0

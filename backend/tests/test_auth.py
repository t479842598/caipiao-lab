"""账号 / 会话 / 权限边界测试。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import db as db_module
from app.models import AuditLog, User
from app.security import SESSION_COOKIE, hash_password, password_ok, verify_password


def test_password_hash_roundtrip():
    blob = hash_password("Abcdefg123!@#")
    assert blob.startswith("scrypt$")
    assert verify_password("Abcdefg123!@#", blob) is True
    assert verify_password("wrong-password", blob) is False
    assert verify_password("", blob) is False
    assert verify_password("x", "") is False
    assert verify_password("x", "plain-text") is False


def test_password_policy():
    assert password_ok("short1!")[0] is False
    assert password_ok("alllowercaseonly")[0] is False
    assert password_ok("Abcdefgh123")[0] is True


def test_login_sets_cookie_and_returns_csrf(client, admin_creds):
    r = client.post("/api/auth/login", json=admin_creds)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["csrf"] == "1"
    assert body["user"]["username"] == admin_creds["username"]
    assert body["user"]["role"] == "admin"
    assert SESSION_COOKIE in r.cookies


def test_login_rejects_wrong_password(fresh_client, admin_creds):
    payload = dict(admin_creds, password=admin_creds["password"] + "x")
    r = fresh_client.post("/api/auth/login", json=payload)
    assert r.status_code == 401
    assert SESSION_COOKIE not in r.cookies


def test_login_unknown_user(fresh_client):
    r = fresh_client.post("/api/auth/login", json={"username": "ghost", "password": "Nothing12345!"})
    assert r.status_code == 401


def test_login_failure_is_audited(fresh_client, admin_creds, session):
    from sqlalchemy import select

    before = len(session.execute(select(AuditLog)).scalars().all())
    fresh_client.post("/api/auth/login", json=dict(admin_creds, password="bad-pass-12345"))
    after = session.execute(select(AuditLog)).scalars().all()
    assert len(after) > before
    assert any(row.action == "login" and row.status == "fail" for row in after)


def test_me_anonymous(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    body = r.json()
    assert body["authenticated"] is False
    assert body["user"] is None


def test_me_authenticated(admin):
    r = admin.get("/api/auth/me")
    assert r.status_code == 200
    body = r.json()
    assert body["authenticated"] is True
    assert body["user"]["username"] == "admin"


def test_write_requires_login(fresh_client):
    r = fresh_client.post("/api/sync/ssq", json={"mode": "incremental"})
    assert r.status_code == 401
    r2 = fresh_client.patch("/api/providers/c500", json={"enabled": False})
    assert r2.status_code == 401


def test_session_write_needs_csrf_header(client, admin_creds):
    assert client.post("/api/auth/login", json=admin_creds).status_code == 200
    r = client.post("/api/sync/ssq", json={"mode": "incremental"})
    assert r.status_code == 403
    assert "CSRF" in r.json()["detail"]


def test_csrf_header_allows_write(admin):
    r = admin.patch("/api/providers/c500", json={"priority": 5})
    assert r.status_code == 200


def test_logout_invalidates_session(admin):
    assert admin.get("/api/auth/me").json()["authenticated"] is True
    assert admin.post("/api/auth/logout").status_code == 200
    assert admin.get("/api/auth/me").json()["authenticated"] is False


def test_static_token_still_works(fresh_client, session):
    from app.config import settings

    settings.admin_token = "unit-test-static-token"
    try:
        r = fresh_client.patch(
            "/api/providers/c500",
            json={"enabled": True},
            headers={"X-Admin-Token": "unit-test-static-token"},
        )
        assert r.status_code == 200
        bad = fresh_client.patch(
            "/api/providers/c500", json={"enabled": True}, headers={"X-Admin-Token": "nope"}
        )
        assert bad.status_code == 401
    finally:
        settings.admin_token = ""


def test_session_list_and_revoke(admin):
    r = admin.get("/api/auth/sessions")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) >= 1
    sid = rows[0]["id"]
    assert admin.delete(f"/api/auth/sessions/{sid}").status_code == 200
    assert admin.get("/api/auth/me").json()["authenticated"] is False


def test_change_password(client, admin_creds, session):
    assert client.post("/api/auth/login", json=admin_creds).status_code == 200
    client.headers.update({"x-csrf": "1"})
    new_pw = "NewPassw0rd!2026"
    r = client.post(
        "/api/auth/password",
        json={"old_password": admin_creds["password"], "new_password": new_pw},
    )
    assert r.status_code == 200
    # 旧会话已被吊销
    assert client.get("/api/auth/me").json()["authenticated"] is False
    # 新密码可登录
    r2 = client.post("/api/auth/login", json={"username": admin_creds["username"], "password": new_pw})
    assert r2.status_code == 200
    # 复原，避免影响其他测试
    client.headers.update({"x-csrf": "1"})
    assert client.post(
        "/api/auth/password",
        json={"old_password": new_pw, "new_password": admin_creds["password"]},
    ).status_code == 200


def test_change_password_rejects_weak(client, admin_creds):
    assert client.post("/api/auth/login", json=admin_creds).status_code == 200
    client.headers.update({"x-csrf": "1"})
    r = client.post(
        "/api/auth/password",
        json={"old_password": admin_creds["password"], "new_password": "short"},
    )
    # 422 由 pydantic 长度约束拦截，400 由口令策略拦截，两条路径都算拒绝
    assert r.status_code in (400, 422)


def test_disabled_user_cannot_login(fresh_client, admin_creds, session):
    user = session.query(User).filter(User.username == admin_creds["username"]).one()
    user.enabled = False
    session.commit()
    try:
        r = fresh_client.post("/api/auth/login", json=admin_creds)
        assert r.status_code == 401
    finally:
        user.enabled = True
        session.commit()

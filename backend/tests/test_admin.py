"""管理后台接口：审计、账号、概览。"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_overview_requires_admin(fresh_client: TestClient) -> None:
    assert fresh_client.get("/api/admin/overview").status_code == 401


def test_overview_counts(admin: TestClient) -> None:
    r = admin.get("/api/admin/overview")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["draws"] > 0
    assert body["users"] >= 1
    assert body["audit_logs"] >= 1
    assert isinstance(body["read_only"], bool)


def test_audit_list_and_actions(admin: TestClient) -> None:
    admin.post("/api/sync/ssq", params={"mode": "incremental"})
    rows = admin.get("/api/admin/audit", params={"limit": 50})
    assert rows.status_code == 200
    actions = {row["action"] for row in rows.json()}
    assert "login" in actions
    grouped = admin.get("/api/admin/audit/actions")
    assert grouped.status_code == 200
    assert any(item["action"] == "login" for item in grouped.json())


def test_audit_filter(admin: TestClient) -> None:
    r = admin.get("/api/admin/audit", params={"action": "login", "limit": 10})
    assert r.status_code == 200
    assert all(row["action"] == "login" for row in r.json())


def test_user_crud(admin: TestClient) -> None:
    created = admin.post(
        "/api/admin/users",
        json={"username": "ops-viewer", "password": "ViewerPass!2024", "role": "viewer"},
    )
    assert created.status_code == 200, created.text
    uid = created.json()["id"]

    dup = admin.post(
        "/api/admin/users",
        json={"username": "ops-viewer", "password": "ViewerPass!2024"},
    )
    assert dup.status_code == 409

    weak = admin.post("/api/admin/users", json={"username": "weak-one", "password": "12345678"})
    assert weak.status_code == 400

    patched = admin.patch(f"/api/admin/users/{uid}", json={"enabled": False})
    assert patched.status_code == 200
    assert patched.json()["enabled"] is False

    listed = admin.get("/api/admin/users")
    assert any(row["username"] == "ops-viewer" for row in listed.json())


def test_user_patch_guards(admin: TestClient, admin_creds: dict) -> None:
    me = admin.get("/api/auth/me").json()["user"]
    own_disable = admin.patch(f"/api/admin/users/{me['id']}", json={"enabled": False})
    assert own_disable.status_code == 400
    own_role = admin.patch(f"/api/admin/users/{me['id']}", json={"role": "viewer"})
    assert own_role.status_code == 400
    missing = admin.patch("/api/admin/users/99999", json={"enabled": False})
    assert missing.status_code == 404


def test_admin_sessions_and_revoke(admin: TestClient) -> None:
    rows = admin.get("/api/admin/sessions")
    assert rows.status_code == 200
    data = rows.json()
    assert len(data) >= 1
    current = next(row for row in data if row["current"])
    killed = admin.delete(f"/api/admin/sessions/{current['id']}")
    assert killed.status_code == 200
    after = admin.get("/api/auth/me")
    assert after.status_code == 200
    assert after.json()["authenticated"] is False


def test_admin_writes_require_csrf(admin: TestClient) -> None:
    admin.headers.pop("x-csrf", None)
    r = admin.post("/api/admin/users", json={"username": "nocsrf", "password": "NoCsrf!2024a"})
    assert r.status_code == 403
    admin.headers["x-csrf"] = "1"

from __future__ import annotations

import pytest


def test_health(client) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert set(body["draws"]) == {"ssq", "3d", "qlc", "kl8"}


def test_games_list(client) -> None:
    r = client.get("/api/games")
    assert r.status_code == 200
    codes = [g["code"] for g in r.json()]
    assert codes == ["ssq", "3d", "qlc", "kl8"]


def test_game_detail_domain(client) -> None:
    body = client.get("/api/games/ssq").json()
    red = next(b for b in body["balls"] if b["key"] == "red")
    assert red["count"] == 6
    assert red["domain"][0] == 1 and red["domain"][-1] == 33
    assert body["draw_count"] > 0


def test_unknown_game_404(client) -> None:
    assert client.get("/api/games/nope").status_code == 404


def test_draws_pagination(client) -> None:
    body = client.get("/api/draws/ssq", params={"page": 1, "page_size": 10}).json()
    assert body["page_size"] == 10
    assert len(body["items"]) == 10
    assert body["total"] == 120
    body2 = client.get("/api/draws/ssq", params={"page": 12, "page_size": 10}).json()
    assert len(body2["items"]) == 10


def test_draws_asc_order(client) -> None:
    body = client.get("/api/draws/ssq", params={"order": "asc", "page_size": 5}).json()
    issues = [d["issue"] for d in body["items"]]
    assert issues == sorted(issues)


def test_draw_by_issue(client) -> None:
    latest = client.get("/api/draws/ssq/latest/one").json()
    one = client.get(f"/api/draws/ssq/{latest['issue']}")
    assert one.status_code == 200
    assert one.json()["issue"] == latest["issue"]


def test_draw_missing_404(client) -> None:
    assert client.get("/api/draws/ssq/1999999").status_code == 404


def test_analytics_frequency(client) -> None:
    body = client.get("/api/analytics/ssq/frequency", params={"window": 50}).json()
    assert body["window"] == 50
    assert len(body["items"]) == 33


def test_analytics_omission(client) -> None:
    body = client.get("/api/analytics/ssq/omission").json()
    assert len(body["items"]) == 33


def test_analytics_trend(client) -> None:
    body = client.get("/api/analytics/ssq/trend", params={"periods": 20}).json()
    assert len(body["matrix"]) == 20


def test_analytics_distribution(client) -> None:
    body = client.get("/api/analytics/ssq/distribution", params={"window": 40}).json()
    assert body["stats"]["draws"] == 40


def test_analytics_randomness(client) -> None:
    body = client.get("/api/analytics/ssq/randomness").json()
    assert "verdict" in body and body["verdict"]


def test_analytics_bad_ball(client) -> None:
    assert client.get("/api/analytics/ssq/frequency", params={"ball": "green"}).status_code == 400


def test_predict_post(client) -> None:
    r = client.post("/api/predict", json={"game": "ssq", "count": 3, "engine": "frequency", "window": 50, "seed": 1})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["tickets"]) == 3
    assert body["weights"]


def test_predict_count_upper_bound(client) -> None:
    r = client.post("/api/predict", json={"game": "ssq", "count": 101, "engine": "frequency", "window": 50})
    assert r.status_code == 422


def test_predict_bad_engine(client) -> None:
    r = client.post("/api/predict", json={"game": "ssq", "count": 1, "engine": "magic", "window": 50})
    assert r.status_code == 422


def test_predict_history(client) -> None:
    body = client.get("/api/predict/history/ssq", params={"limit": 5}).json()
    assert isinstance(body, list)


def test_backtest_runs(client) -> None:
    r = client.post("/api/backtest", json={"game": "ssq", "periods": 50, "engine": "frequency", "window": 40, "topk": 6})
    assert r.status_code == 200, r.text
    body = r.json()
    # 实际可回测期数受历史长度限制（最后一期没有未来标签），允许略小于请求值
    assert 40 <= body["periods"] <= 50
    assert "verdict" in body
    assert body["model"]["avg_hits"] >= 0


def test_backtest_rejects_short_periods(client) -> None:
    r = client.post("/api/backtest", json={"game": "ssq", "periods": 5, "engine": "frequency"})
    assert r.status_code == 422


def test_providers_list(client) -> None:
    body = client.get("/api/providers").json()
    codes = {p["code"] for p in body}
    assert {"cwl_official", "csv_import"} <= codes


def test_provider_patch_toggles(admin) -> None:
    before = next(p for p in admin.get("/api/providers").json() if p["code"] == "c500")
    r = admin.patch("/api/providers/c500", json={"enabled": not before["enabled"]})
    assert r.status_code == 200
    assert r.json()["enabled"] is (not before["enabled"])
    admin.patch("/api/providers/c500", json={"enabled": before["enabled"]})


def test_provider_patch_requires_admin(fresh_client) -> None:
    assert fresh_client.patch("/api/providers/c500", json={"enabled": False}).status_code == 401


def test_provider_patch_unknown_404(admin) -> None:
    assert admin.patch("/api/providers/none", json={"enabled": False}).status_code == 404


def test_sync_status_shape(client) -> None:
    body = client.get("/api/sync/status").json()
    assert "counts" in body
    assert "next_jobs" in body


def test_sync_missing_issues(client) -> None:
    body = client.get("/api/sync/missing/ssq").json()
    assert body["game"] == "ssq"
    assert isinstance(body["missing"], list)


def test_sync_rejects_bad_mode(admin) -> None:
    r = admin.post("/api/sync/ssq", params={"mode": "turbo"})
    assert r.status_code == 400


def test_sync_requires_admin(fresh_client) -> None:
    assert fresh_client.post("/api/sync/ssq", params={"mode": "incremental"}).status_code == 401


def test_ticket_crud(guest) -> None:
    created = guest.post(
        "/api/tickets",
        json={"game_code": "ssq", "issue": "2026001", "numbers": {"red": ["01", "02", "03", "04", "05", "06"], "blue": ["07"]}, "cost": 2},
    )
    assert created.status_code == 200, created.text
    tid = created.json()["id"]
    stats = guest.get("/api/tickets/stats/summary").json()
    assert stats["total_tickets"] >= 1
    assert guest.delete(f"/api/tickets/{tid}").status_code == 200


def test_ticket_requires_device_id(fresh_client) -> None:
    r = fresh_client.post("/api/tickets", json={"game_code": "ssq", "numbers": {"red": ["01"]}})
    assert r.status_code == 400


def test_ticket_unknown_game_404(guest) -> None:
    r = guest.post("/api/tickets", json={"game_code": "xxx", "numbers": {"red": ["01"]}})
    assert r.status_code == 404


def test_ticket_delete_missing_404(guest) -> None:
    assert guest.delete("/api/tickets/999999").status_code == 404


def test_spa_served(client) -> None:
    """构建产物存在时根路径应返回 index.html。"""
    from pathlib import Path

    from app.config import settings

    index = Path(settings.static_dir) / "index.html"
    r = client.get("/")
    if index.exists():
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
    else:
        assert r.status_code == 200
        assert r.json()["service"] == "caipiao-lab"


def test_spa_unknown_api_returns_json_404(client) -> None:
    """未知 /api 路径必须是 404 JSON，不能被 SPA 兜底成 200 + HTML。"""
    r = client.get("/api/definitely-not-a-route")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json")
    assert r.json()["detail"] == "Not Found"


def test_spa_client_route_still_served(client) -> None:
    """/sync 这类前端路由仍要拿到 index.html（不能误伤 SPA 兜底）。"""
    from pathlib import Path

    from app.config import settings

    index = Path(settings.static_dir) / "index.html"
    r = client.get("/sync")
    assert r.status_code == 200
    if index.exists():
        assert "text/html" in r.headers["content-type"]


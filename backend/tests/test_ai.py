"""AI 供应商自助提交 / 管理员审核 / 分析调用测试（全部离线）。"""

from __future__ import annotations

import pytest

from app.ai import client as ai_client
from app.ai.client import VENDORS, _endpoint, default_base_url, default_model
from app.ai.prompt import build_payload, build_user_message, fallback_answer


@pytest.fixture()
def no_network(monkeypatch):
    """拦截真实出网，返回固定回复。"""

    calls: list[dict] = []

    def fake_chat(*, provider, system, user, timeout=None, max_tokens=None, temperature=None):
        calls.append({"provider": provider.name, "user": user[:80]})
        return ai_client.AiReply(
            ok=True,
            text="离线假回复：模型认为号码分布均匀，仅供研究参考。",
            model=provider.model or "fake-model",
            prompt_tokens=120,
            completion_tokens=60,
            latency_ms=12,
            error="",
            raw={},
        )

    monkeypatch.setattr("app.routers.ai.chat", fake_chat)
    return calls


def test_vendors_list(client):
    r = client.get("/api/ai/vendors")
    assert r.status_code == 200
    rows = r.json()
    codes = {row["code"] for row in rows}
    assert set(VENDORS).issubset(codes)
    assert all("base_url" in row and "model" in row for row in rows)


def test_endpoint_normalisation():
    assert _endpoint("https://api.deepseek.com") == "https://api.deepseek.com/v1/chat/completions"
    assert _endpoint("https://api.deepseek.com/v1") == "https://api.deepseek.com/v1/chat/completions"
    assert _endpoint("https://x/v1/chat/completions") == "https://x/v1/chat/completions"
    assert default_base_url("deepseek").startswith("https://")
    assert default_model("deepseek")


def test_submit_creates_pending(client, session):
    from app.models import AiProvider

    r = client.post(
        "/api/ai/providers/submit",
        json={
            "name": "我的 DeepSeek",
            "vendor": "deepseek",
            "api_key": "sk-test-1234567890abcdef",
            "submitter_name": "访客甲",
            "note": "想试试",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "pending"
    assert body["enabled"] is False
    row = session.get(AiProvider, body["id"])
    assert row is not None
    assert row.api_key_enc and row.api_key_enc != "sk-test-1234567890abcdef"
    assert row.api_key_hint.endswith("cdef")


def test_pending_not_usable_before_approval(client, admin, no_network):
    created = client.post(
        "/api/ai/providers/submit",
        json={"name": "待审", "vendor": "openai", "api_key": "sk-pending-000000"},
    ).json()
    assert client.get("/api/ai/providers").json() == [] or all(
        p["id"] != created["id"] for p in client.get("/api/ai/providers").json()
    )
    r = client.post("/api/ai/analyze", json={"game": "ssq", "count": 2})
    assert r.status_code == 200
    assert r.json()["provider_name"] in ("local", "")


def test_admin_approve_then_analyze(client, admin, no_network):
    created = client.post(
        "/api/ai/providers/submit",
        json={"name": "可用供应商", "vendor": "deepseek", "api_key": "sk-live-abcdef123456"},
    ).json()
    r = admin.patch(f"/api/ai/providers/{created['id']}", json={"status": "approved"})
    assert r.status_code == 200
    assert r.json()["status"] == "approved"
    assert r.json()["enabled"] is True

    listed = client.get("/api/ai/providers").json()
    assert any(p["id"] == created["id"] for p in listed)

    r2 = client.post("/api/ai/analyze", json={"game": "ssq", "count": 3})
    assert r2.status_code == 200
    body = r2.json()
    assert body["provider_name"] == "可用供应商"
    assert "离线假回复" in body["answer"]
    assert body["payload"]["推荐号码"]
    assert no_network


def test_analyze_without_provider_falls_back(client, session):
    from sqlalchemy import delete

    from app.models import AiProvider

    session.execute(delete(AiProvider))
    session.commit()
    r = client.post("/api/ai/analyze", json={"game": "3d", "count": 2})
    assert r.status_code == 200
    body = r.json()
    assert body["provider_name"] == "local"
    assert body["answer"]


def test_reject_hides_provider(client, admin):
    created = client.post(
        "/api/ai/providers/submit",
        json={"name": "被拒", "vendor": "qwen", "api_key": "sk-reject-654321"},
    ).json()
    r = admin.patch(f"/api/ai/providers/{created['id']}", json={"status": "rejected"})
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"
    assert r.json()["enabled"] is False
    assert all(p["id"] != created["id"] for p in client.get("/api/ai/providers").json())


def test_provider_admin_list_requires_admin(fresh_client):
    assert fresh_client.get("/api/ai/providers/all").status_code == 401


def test_provider_patch_requires_admin(fresh_client):
    assert fresh_client.patch("/api/ai/providers/999", json={"status": "approved"}).status_code == 401


def test_submit_rejects_bad_vendor(client):
    r = client.post(
        "/api/ai/providers/submit",
        json={"name": "x", "vendor": "not-a-vendor", "api_key": "sk-123456"},
    )
    assert r.status_code == 400


def test_insight_shape(client):
    r = client.get("/api/ai/insight/ssq")
    assert r.status_code == 200
    body = r.json()
    for key in ("hot", "cold", "omission_top", "structure", "randomness"):
        assert key in body


def test_prompt_payload_has_disclaimer():
    payload = build_payload(
        "ssq",
        {
            "hot": [{"number": "1", "count": 9}],
            "cold": [{"number": "2", "count": 1}],
            "omission_top": [],
            "structure": {},
            "randomness": {},
        },
        {"target_issue": "2026121", "based_on": "2026120", "tickets": [], "engine": "ensemble"},
    )
    text = build_user_message(payload, "帮我看看")
    assert "2026121" in text
    assert "帮我看看" in text
    fallback = fallback_answer(payload)
    assert fallback
    assert "随机" in fallback or "独立" in fallback


def test_analyze_records_audit(client, admin, session, no_network):
    from sqlalchemy import select

    from app.models import AiAnalysis

    created = client.post(
        "/api/ai/providers/submit",
        json={"name": "审计用", "vendor": "deepseek", "api_key": "sk-audit-11223344"},
    ).json()
    admin.patch(f"/api/ai/providers/{created['id']}", json={"status": "approved"})
    client.post("/api/ai/analyze", json={"game": "qlc", "count": 2})
    rows = session.execute(select(AiAnalysis)).scalars().all()
    assert rows
    assert rows[-1].game_code == "qlc"
    assert rows[-1].provider_name == "审计用"

def test_private_endpoint_blocked_by_default(client):
    r = client.post(
        "/api/ai/providers/submit",
        json={"name": "内网试探", "vendor": "custom", "base_url": "http://192.168.1.9:8000/v1", "api_key": "sk-x-12345678"},
    )
    assert r.status_code == 400
    assert "内网" in r.json()["detail"]


def test_ollama_private_endpoint_allowed_by_design(client):
    r = client.post(
        "/api/ai/providers/submit",
        json={"name": "本地 Ollama 默认", "vendor": "ollama", "base_url": "http://127.0.0.1:11434/v1"},
    )
    assert r.status_code == 200


def test_private_endpoint_allowed_when_enabled(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ai_allow_private_endpoint", True)
    r = client.post(
        "/api/ai/providers/submit",
        json={"name": "内网自定义", "vendor": "custom", "base_url": "http://127.0.0.1:8000/v1"},
    )
    assert r.status_code == 200
    assert r.json()["base_url"] == "http://127.0.0.1:8000/v1"


def test_public_endpoint_still_allowed(client):
    r = client.post(
        "/api/ai/providers/submit",
        json={"name": "公网网关", "vendor": "custom", "base_url": "https://gw.example.com/v1", "api_key": "sk-x-12345678"},
    )
    assert r.status_code == 200
"""AI 供应商：用户自助登记 + 管理员审核 + 用预测凭据做 AI 分析。"""

from __future__ import annotations

import time
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session as OrmSession

from ..ai.client import VENDORS, chat, default_base_url, default_model
from ..ai.prompt import SYSTEM, build_payload, build_user_message, fallback_answer
from ..auth_deps import Principal, client_ip, optional_user, require_admin
from ..config import settings
from ..db import get_db
from ..engine.predictor import predict
from ..games import GAMES, get_game
from ..models import AiAnalysis, AiProvider
from ..schemas import (
    AiAnalysisOut,
    AiAnalyzeIn,
    AiProviderAdmin,
    AiProviderOut,
    AiProviderSubmit,
    InsightOut,
)
from ..security import audit, decrypt_secret, encrypt_secret, mask_secret, utcnow

router = APIRouter(prefix="/ai", tags=["ai"])

MAX_PENDING = 200


def _out(row: AiProvider) -> AiProviderOut:
    key = decrypt_secret(row.api_key_enc)
    return AiProviderOut(
        id=row.id,
        name=row.name,
        vendor=row.vendor,
        base_url=row.base_url,
        model=row.model,
        api_key_set=bool(key),
        api_key_hint=row.api_key_hint or (mask_secret(key) if key else ""),
        temperature=row.temperature,
        max_tokens=row.max_tokens,
        enabled=row.enabled,
        status=row.status,
        submitter_name=row.submitter_name,
        submitter_contact=row.submitter_contact,
        note=row.note,
        review_note=row.review_note,
        created_at=row.created_at,
        reviewed_at=row.reviewed_at,
        last_ok_at=row.last_ok_at,
        last_error=row.last_error or "",
        calls=row.calls,
        healthy=not row.last_error,
    )


def _analysis_out(row: AiAnalysis) -> AiAnalysisOut:
    return AiAnalysisOut(
        id=row.id,
        game_code=row.game_code,
        target_issue=row.target_issue,
        provider_name=row.provider_name,
        model=row.model,
        latency_ms=row.latency_ms,
        prompt_tokens=row.prompt_tokens,
        completion_tokens=row.completion_tokens,
        answer=row.answer,
        error=row.error,
        payload=row.payload or {},
        created_at=row.created_at,
    )


_PRIVATE_HOSTS = ("localhost", "127.", "0.0.0.0", "10.", "192.168.", "172.16.", "172.17.",
                  "172.18.", "172.19.", "172.2", "172.30.", "172.31.", "::1", "[::1]", "169.254.")


def _is_private_host(url: str) -> bool:
    host = url.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0].lower()
    return any(host.startswith(p) or host == p.rstrip(".") for p in _PRIVATE_HOSTS)


def _normalize_url(vendor: str, base_url: str) -> str:
    url = (base_url or "").strip()
    if url and not url.startswith(("http://", "https://")):
        raise HTTPException(400, "base_url 必须以 http:// 或 https:// 开头")
    if url and len(url) > 255:
        raise HTTPException(400, "base_url 过长")
    if url and _is_private_host(url) and vendor != "ollama" and not settings.ai_allow_private_endpoint:
        raise HTTPException(400, "不允许把 base_url 指向内网地址；用本地 Ollama 请把 AI_ALLOW_PRIVATE_ENDPOINT 设为 true")
    return url or default_base_url(vendor)


def _pick_provider(db: OrmSession, provider_id: int | None) -> AiProvider:
    if provider_id is not None:
        row = db.get(AiProvider, provider_id)
        if row is None or not row.enabled or row.status != "approved":
            raise HTTPException(404, "该供应商不可用")
        return row
    row = db.execute(
        select(AiProvider)
        .where(AiProvider.enabled.is_(True), AiProvider.status == "approved")
        .order_by(AiProvider.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(503, "还没有审核通过的 AI 供应商，可先在「AI 供应商」页提交")
    return row


# --------------------------------------------------------------------------- #
# 公开：供应商目录 + 用户自助提交
# --------------------------------------------------------------------------- #
@router.get("/vendors")
def vendors() -> list[dict]:
    return [
        {"code": code, "label": meta["label"], "base_url": meta["base_url"], "model": meta["model"]}
        for code, meta in VENDORS.items()
    ]


@router.get("/providers", response_model=list[AiProviderOut])
def public_providers(db: OrmSession = Depends(get_db)) -> list[AiProviderOut]:
    rows = db.execute(
        select(AiProvider)
        .where(AiProvider.status == "approved", AiProvider.enabled.is_(True))
        .order_by(AiProvider.id.desc())
    ).scalars().all()
    return [_out(r) for r in rows]


@router.post("/providers/submit", response_model=AiProviderOut)
def submit_provider(
    payload: AiProviderSubmit,
    request: Request,
    db: OrmSession = Depends(get_db),
    who: Principal = Depends(optional_user),
) -> AiProviderOut:
    if not settings.ai_allow_public_submit and not who.is_admin:
        raise HTTPException(403, "当前不接受自助提交")
    if payload.vendor not in VENDORS:
        raise HTTPException(400, "未知供应商类型")
    pending = db.execute(
        select(func.count(AiProvider.id)).where(AiProvider.status == "pending")
    ).scalar() or 0
    if pending >= MAX_PENDING:
        raise HTTPException(429, "待审核队列已满，请稍后再试")

    key = (payload.api_key or "").strip()
    if key and len(key) > 400:
        raise HTTPException(400, "api_key 过长")
    row = AiProvider(
        name=payload.name.strip()[:64],
        vendor=payload.vendor,
        base_url=_normalize_url(payload.vendor, payload.base_url),
        model=(payload.model or "").strip()[:128] or default_model(payload.vendor),
        api_key_enc=encrypt_secret(key),
        api_key_hint=mask_secret(key),
        status="pending",
        enabled=False,
        submitter_name=payload.submitter_name.strip()[:64],
        submitter_contact=payload.submitter_contact.strip()[:128],
        note=payload.note.strip()[:500],
        owner_id=who.user_id,
    )
    db.add(row)
    db.flush()
    audit(db, actor=who.username, action="ai_submit", target=f"ai:{row.id}",
          detail={"name": row.name, "vendor": row.vendor}, ip=client_ip(request),
          ua=request.headers.get("user-agent", ""))
    db.commit()
    db.refresh(row)
    return _out(row)


# --------------------------------------------------------------------------- #
# 后台：审核 / 维护
# --------------------------------------------------------------------------- #
@router.get("/providers/all", response_model=list[AiProviderOut])
def all_providers(
    db: OrmSession = Depends(get_db),
    _: Principal = Depends(require_admin),
) -> list[AiProviderOut]:
    rows = db.execute(select(AiProvider).order_by(AiProvider.id.desc()).limit(500)).scalars().all()
    return [_out(r) for r in rows]


@router.patch("/providers/{provider_id}", response_model=AiProviderOut)
def patch_provider(
    provider_id: int,
    payload: AiProviderAdmin,
    request: Request,
    db: OrmSession = Depends(get_db),
    who: Principal = Depends(require_admin),
) -> AiProviderOut:
    row = db.get(AiProvider, provider_id)
    if row is None:
        raise HTTPException(404, "供应商不存在")
    data = payload.model_dump(exclude_unset=True)
    if "vendor" in data and data["vendor"] not in VENDORS:
        raise HTTPException(400, "未知供应商类型")
    if "status" in data and data["status"] not in ("pending", "approved", "rejected"):
        raise HTTPException(400, "status 只能是 pending / approved / rejected")
    for field in ("name", "vendor", "model", "review_note", "submitter_name", "submitter_contact", "note"):
        if field in data and data[field] is not None:
            setattr(row, field, str(data[field])[:500])
    if "base_url" in data and data["base_url"] is not None:
        row.base_url = _normalize_url(row.vendor, data["base_url"])
    if "temperature" in data and data["temperature"] is not None:
        row.temperature = max(0.0, min(2.0, float(data["temperature"])))
    if "max_tokens" in data and data["max_tokens"] is not None:
        row.max_tokens = max(64, min(8000, int(data["max_tokens"])))
    if "enabled" in data and data["enabled"] is not None:
        row.enabled = bool(data["enabled"])
    if data.get("api_key"):
        row.api_key_enc = encrypt_secret(str(data["api_key"]).strip())
        row.api_key_hint = mask_secret(str(data["api_key"]).strip())
    if "status" in data and data["status"] != row.status:
        row.status = data["status"]
        row.reviewed_at = utcnow()
        row.enabled = data["status"] == "approved"
    audit(db, actor=who.username, action="ai_patch", target=f"ai:{row.id}",
          detail={k: ("***" if k == "api_key" else v) for k, v in data.items()},
          ip=client_ip(request))
    db.commit()
    db.refresh(row)
    return _out(row)


@router.delete("/providers/{provider_id}")
def delete_provider(
    provider_id: int,
    request: Request,
    db: OrmSession = Depends(get_db),
    who: Principal = Depends(require_admin),
) -> dict:
    row = db.get(AiProvider, provider_id)
    if row is None:
        raise HTTPException(404, "供应商不存在")
    db.delete(row)
    audit(db, actor=who.username, action="ai_delete", target=f"ai:{provider_id}", ip=client_ip(request))
    db.commit()
    return {"ok": True}


@router.post("/providers/{provider_id}/test")
def test_provider(
    provider_id: int,
    db: OrmSession = Depends(get_db),
    _: Principal = Depends(require_admin),
) -> dict:
    row = db.get(AiProvider, provider_id)
    if row is None:
        raise HTTPException(404, "供应商不存在")
    started = time.monotonic()
    reply = chat(provider=row, system="你是连通性测试助手。", user="只回复两个字：可用", timeout=30)
    row.last_ok_at = utcnow() if reply.ok else row.last_ok_at
    row.last_error = "" if reply.ok else reply.error[:2000]
    db.commit()
    return {
        "ok": reply.ok,
        "latency_ms": reply.latency_ms or int((time.monotonic() - started) * 1000),
        "message": reply.text if reply.ok else reply.error,
        "model": reply.model,
    }


# --------------------------------------------------------------------------- #
# 预测凭据（确定性统计，不依赖 AI）
# --------------------------------------------------------------------------- #
def build_insight(db: OrmSession, game: str, window: int = 100) -> dict:
    from ..engine.dataset import load_ball_data
    from ..engine.stats import distribution_stats, frequency_table, omission_table, randomness_report

    spec = get_game(game)
    data = load_ball_data(db, game, "red")
    if data.n == 0:
        raise HTTPException(400, f"{spec.name} 还没有任何开奖数据")
    freq = frequency_table(data, window=window)
    omi = omission_table(data, limit=40)
    dist = distribution_stats(data, window=window)
    rnd = randomness_report(data)
    hot = sorted(freq, key=lambda x: -x["count"])[:10]
    cold = sorted(freq, key=lambda x: x["count"])[:10]
    return {
        "game": game,
        "draws": data.n,
        "based_on": data.issues[-1] if data.issues else "",
        "hot": hot,
        "cold": cold,
        "omission_top": sorted(omi, key=lambda x: -x["current"])[:10],
        "structure": dist,
        "randomness": rnd.get("verdict", ""),
    }


@router.get("/insight/{game}", response_model=InsightOut)
def insight(game: str, window: int = Query(default=100, ge=10, le=2000),
            db: OrmSession = Depends(get_db)) -> InsightOut:
    if game not in GAMES:
        raise HTTPException(404, f"未知彩种 {game}")
    data = build_insight(db, game, window)
    return InsightOut(**data)


# --------------------------------------------------------------------------- #
# AI 分析
# --------------------------------------------------------------------------- #
@router.post("/analyze", response_model=AiAnalysisOut)
def analyze(
    payload: AiAnalyzeIn,
    request: Request,
    db: OrmSession = Depends(get_db),
    who: Principal = Depends(optional_user),
) -> AiAnalysisOut:
    if payload.game not in GAMES:
        raise HTTPException(404, f"未知彩种 {payload.game}")
    if payload.count > settings.predict_max_count:
        raise HTTPException(400, f"最多一次生成 {settings.predict_max_count} 注")

    ip = client_ip(request)
    hour_ago = utcnow() - timedelta(hours=1)
    used = db.execute(
        select(func.count(AiAnalysis.id)).where(AiAnalysis.created_at >= hour_ago, AiAnalysis.actor == (who.username or ip))
    ).scalar() or 0
    if used >= settings.ai_max_calls_per_hour:
        raise HTTPException(429, f"每小时最多 {settings.ai_max_calls_per_hour} 次 AI 分析")

    prediction = predict(db, game=payload.game, count=payload.count, engine=payload.engine,
                         strategy=payload.strategy, window=payload.window)
    ins = build_insight(db, payload.game, payload.window)
    prompt_payload = build_payload(payload.game, ins, prediction)

    try:
        provider = _pick_provider(db, payload.provider_id)
    except HTTPException as exc:
        if exc.status_code != 503:
            raise
        row = AiAnalysis(
            game_code=payload.game,
            target_issue=prediction.get("target_issue", ""),
            provider_name="local",
            model="builtin",
            payload=prompt_payload,
            answer=fallback_answer(prompt_payload),
            actor=who.username or ip,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _analysis_out(row)

    reply = chat(provider=provider, system=SYSTEM, user=build_user_message(prompt_payload, payload.question))
    provider.calls = (provider.calls or 0) + 1
    if reply.ok:
        provider.last_ok_at = utcnow()
        provider.last_error = ""
    else:
        provider.last_error = reply.error[:2000]

    row = AiAnalysis(
        game_code=payload.game,
        target_issue=prediction.get("target_issue", ""),
        provider_id=provider.id,
        provider_name=provider.name,
        model=reply.model or provider.model,
        prompt_tokens=reply.prompt_tokens,
        completion_tokens=reply.completion_tokens,
        latency_ms=reply.latency_ms,
        payload=prompt_payload,
        answer=reply.text if reply.ok else fallback_answer(prompt_payload),
        error="" if reply.ok else reply.error[:2000],
        actor=who.username or ip,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _analysis_out(row)


@router.get("/analyses", response_model=list[AiAnalysisOut])
def analyses(
    game: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    db: OrmSession = Depends(get_db),
) -> list[AiAnalysisOut]:
    stmt = select(AiAnalysis).order_by(AiAnalysis.id.desc()).limit(limit)
    if game:
        stmt = stmt.where(AiAnalysis.game_code == game)
    rows = db.execute(stmt).scalars().all()
    return [_analysis_out(r) for r in rows]

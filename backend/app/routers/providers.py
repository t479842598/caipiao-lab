from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth_deps import Principal, client_ip, require_admin
from ..config import settings
from ..db import get_db, session_scope
from ..models import Provider
from ..providers.registry import registry
from ..schemas import ProviderOut, ProviderPatch
from ..security import audit

router = APIRouter(prefix="/providers", tags=["providers"])


def _ensure_rows() -> None:
    with session_scope() as session:
        for provider in registry.all():
            if session.get(Provider, provider.code) is None:
                session.add(
                    Provider(
                        code=provider.code,
                        name=provider.name,
                        enabled=True,
                        priority=provider.priority,
                        rate_limit=provider.rate_limit,
                        config={"supported_games": sorted(provider.supported_games)},
                    )
                )


@router.get("", response_model=list[ProviderOut])
def list_providers(db: Session = Depends(get_db)) -> list[ProviderOut]:
    _ensure_rows()
    rows = {row.code: row for row in db.execute(select(Provider)).scalars().all()}
    out = []
    for provider in registry.all():
        row = rows.get(provider.code)
        out.append(
            ProviderOut(
                code=provider.code,
                name=provider.name,
                enabled=row.enabled if row else True,
                priority=row.priority if row else provider.priority,
                rate_limit=provider.rate_limit,
                last_ok_at=row.last_ok_at if row else None,
                last_error=(row.last_error if row else "") or "",
                supported_games=sorted(provider.supported_games),
                healthy=not (row.last_error if row else ""),
            )
        )
    return out


@router.patch("/{code}", response_model=ProviderOut)
def patch_provider(
    code: str,
    patch: ProviderPatch,
    request: Request,
    db: Session = Depends(get_db),
    who: Principal = Depends(require_admin),
) -> ProviderOut:
    if settings.read_only:
        raise HTTPException(403, "当前为只读模式")
    _ensure_rows()
    try:
        provider = registry.get(code)
    except KeyError as exc:
        raise HTTPException(404, f"未知供应商 {code}") from exc
    row = db.get(Provider, code)
    assert row is not None
    if patch.enabled is not None:
        row.enabled = patch.enabled
    if patch.priority is not None:
        row.priority = patch.priority
    audit(db, actor=who.username, action="provider_patch", target=code,
          detail={"enabled": row.enabled, "priority": row.priority}, ip=client_ip(request))
    db.commit()
    return ProviderOut(
        code=code, name=provider.name, enabled=row.enabled, priority=row.priority,
        rate_limit=provider.rate_limit, last_ok_at=row.last_ok_at, last_error=row.last_error or "",
        supported_games=sorted(provider.supported_games), healthy=not row.last_error,
    )


@router.post("/{code}/test")
async def test_provider(
    code: str,
    request: Request,
    db: Session = Depends(get_db),
    who: Principal = Depends(require_admin),
) -> dict:
    try:
        provider = registry.get(code)
    except KeyError as exc:
        raise HTTPException(404, f"未知供应商 {code}") from exc
    health = await provider.health()
    audit(db, actor=who.username, action="provider_test", target=code,
          detail={"healthy": health.healthy}, ip=client_ip(request))
    db.commit()
    return {"code": health.code, "healthy": health.healthy, "message": health.message,
            "latency_ms": health.latency_ms}

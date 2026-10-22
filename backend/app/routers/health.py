from __future__ import annotations

from fastapi import APIRouter

from .. import __version__
from ..config import settings
from ..db import session_scope
from ..models import Draw

router = APIRouter(tags=["meta"])


@router.get("/health")
def health() -> dict:
    counts: dict[str, int] = {}
    try:
        from sqlalchemy import func, select

        with session_scope() as session:
            rows = session.execute(select(Draw.game_code, func.count(Draw.id)).group_by(Draw.game_code)).all()
            counts = {code: n for code, n in rows}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "version": __version__, "error": str(exc)}
    return {"ok": True, "version": __version__, "draws": counts, "sync_enabled": settings.sync_enabled}

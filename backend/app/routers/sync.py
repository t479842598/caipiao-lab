from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..auth_deps import Principal, client_ip, require_admin
from ..config import settings
from ..db import get_db, session_scope
from ..engine.settle import settle_pending
from ..games import GAMES, GAME_ORDER
from ..jobs.scheduler import next_jobs
from ..jobs.sync_job import sync_service
from ..schemas import SyncStatusOut
from ..security import audit

router = APIRouter(prefix="/sync", tags=["sync"])

ALLOWED_MODES = ("incremental", "full", "backfill")
BACKFILL_GAMES = ("ssq", "3d", "qlc")


@router.get("/status", response_model=SyncStatusOut)
def status() -> SyncStatusOut:
    payload = sync_service.status()
    payload["next_jobs"] = next_jobs()
    return SyncStatusOut(**payload)


@router.post("/all")
async def trigger_all(
    request: Request,
    mode: str = "incremental",
    db=Depends(get_db),
    who: Principal = Depends(require_admin),
) -> dict:
    if settings.read_only:
        raise HTTPException(403, "当前为只读模式")
    if mode not in ALLOWED_MODES:
        raise HTTPException(400, "mode 只能是 incremental / full / backfill")
    audit(db, actor=who.username, action="sync_trigger", target="all", detail={"mode": mode},
          ip=client_ip(request))
    db.commit()
    _spawn(_run_all(mode))
    return {"accepted": True, "game": "all", "mode": mode}


@router.post("/{game}")
async def trigger(
    game: str,
    request: Request,
    mode: str = "incremental",
    background: BackgroundTasks = None,  # type: ignore[assignment]
    db=Depends(get_db),
    who: Principal = Depends(require_admin),
) -> dict:
    if game != "all" and game not in GAMES:
        raise HTTPException(404, f"未知彩种 {game}")
    if settings.read_only:
        raise HTTPException(403, "当前为只读模式")
    if mode not in ALLOWED_MODES:
        raise HTTPException(400, "mode 只能是 incremental / full / backfill")
    if mode == "backfill" and game not in BACKFILL_GAMES:
        raise HTTPException(400, "深历史补录仅支持 ssq / 3d / qlc")

    audit(db, actor=who.username, action="sync_trigger", target=game, detail={"mode": mode},
          ip=client_ip(request))
    db.commit()
    _spawn(_run_all(mode) if game == "all" else _run_one(game, mode))
    return {"accepted": True, "game": game, "mode": mode}


_bg_tasks: set[asyncio.Task] = set()


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)


async def _run_one(game: str, mode: str) -> dict:
    result = await sync_service.sync_game(game, mode=mode)
    with session_scope() as session:
        settle_pending(session, game)
    return result


async def _run_all(mode: str) -> list[dict]:
    results = []
    for code in GAME_ORDER:
        results.append(await sync_service.sync_game(code, mode=mode))
    with session_scope() as session:
        settle_pending(session)
    return results


@router.post("/settle/all")
def settle_all(
    request: Request,
    db=Depends(get_db),
    who: Principal = Depends(require_admin),
) -> dict:
    audit(db, actor=who.username, action="settle_all", ip=client_ip(request))
    db.commit()
    with session_scope() as session:
        return settle_pending(session)


@router.get("/stream")
async def stream():
    """SSE：同步进度实时推送到前端（只读，公开可订阅）。"""

    async def gen():
        queue = sync_service.subscribe()
        try:
            yield f"data: {json.dumps({'type': 'hello'})}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"data: {json.dumps(event, default=str)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            sync_service.unsubscribe(queue)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.get("/missing/{game}")
def missing(game: str) -> dict:
    if game not in GAMES:
        raise HTTPException(404, f"未知彩种 {game}")
    items = sync_service.missing_issues(game)
    return {"game": game, "missing": items, "count": len(items)}

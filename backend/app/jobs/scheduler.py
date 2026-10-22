"""定时任务：开奖后自动同步 + 自动兑奖。

策略：每个彩种按开奖日 + 开奖时间后 10 分钟触发，另加一个 30 分钟的兜底巡检
（覆盖官方延迟开奖 / 节假日调整）。所有时间按 SYNC_TZ（默认 Asia/Shanghai）。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..config import settings
from ..db import session_scope
from ..engine.settle import settle_pending
from ..games import GAMES, GAME_ORDER
from .sync_job import sync_service

logger = logging.getLogger("caipiao.scheduler")

_scheduler: AsyncIOScheduler | None = None


def _tz() -> ZoneInfo:
    try:
        return ZoneInfo(settings.sync_tz)
    except Exception:  # noqa: BLE001  pragma: no cover
        return ZoneInfo("Asia/Shanghai")


async def _sync_and_settle(game: str) -> None:
    if not settings.sync_enabled:
        return
    try:
        result = await sync_service.sync_game(game, mode="incremental")
        logger.info("auto sync %s -> %s", game, result.get("status"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("auto sync %s failed: %s", game, exc)
        return
    try:
        with session_scope() as session:
            settle_pending(session, game)
    except Exception as exc:  # noqa: BLE001
        logger.warning("settle %s failed: %s", game, exc)


async def patrol() -> None:
    """兜底巡检：所有彩种各跑一次增量。"""
    for game in GAME_ORDER:
        await _sync_and_settle(game)


def start_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    tz = _tz()
    scheduler = AsyncIOScheduler(timezone=tz)

    for code in GAME_ORDER:
        spec = GAMES[code]
        hour, minute = (int(x) for x in spec.draw_time.split(":"))
        run_at = datetime(2000, 1, 1, hour, minute) + timedelta(minutes=12)
        weekdays = ",".join(str(d) for d in spec.draw_weekdays) if spec.draw_weekdays else "*"
        scheduler.add_job(
            _sync_and_settle,
            CronTrigger(day_of_week=weekdays, hour=run_at.hour, minute=run_at.minute, timezone=tz),
            args=[code],
            id=f"sync_{code}",
            replace_existing=True,
            misfire_grace_time=1800,
        )

    scheduler.add_job(
        patrol,
        CronTrigger(minute="*/30", timezone=tz),
        id="patrol",
        replace_existing=True,
        misfire_grace_time=900,
    )
    scheduler.start()
    logger.info("scheduler started tz=%s", settings.sync_tz)
    _scheduler = scheduler
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def next_jobs() -> list[dict]:
    if _scheduler is None:
        return []
    out = []
    for job in _scheduler.get_jobs():
        out.append({"id": job.id, "next_run": str(job.next_run_time) if job.next_run_time else ""})
    return out

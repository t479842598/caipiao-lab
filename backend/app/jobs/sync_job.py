"""同步服务：全量首灌 / 增量补齐 / 幂等 upsert / per-game 串行 / 进度推送。

幂等的关键：draws 上 UNIQUE(game_code, issue)，写入走 upsert；重复跑不会新增行。
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime
from typing import Any, AsyncIterator, Callable

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from ..config import settings
from ..db import session_scope
from ..games import GAMES, GAME_ORDER, get_game
from ..models import Draw, DrawNumber, PrizeGrade, Provider, SyncRun
from ..providers.base import BaseProvider, ProviderError, RawDraw
from ..providers.registry import registry


class SyncService:
    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {code: asyncio.Lock() for code in GAMES}
        self._running: dict[str, bool] = {code: False for code in GAMES}
        self._subscribers: list[asyncio.Queue] = []

    # ---------- 状态 ----------
    def is_running(self, game: str | None = None) -> bool | dict[str, bool]:
        if game:
            return self._running.get(game, False)
        return dict(self._running)

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    def _publish(self, event: dict[str, Any]) -> None:
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    # ---------- 供应商选择 ----------
    def _provider_chain(self, game: str, mode: str = "incremental") -> list[BaseProvider]:
        chain = registry.candidates(game)
        if mode == "backfill":
            # 补录要用有深历史的源，官方源本身只有 2013 起的数据
            chain = [p for p in chain if getattr(p, "backfill_capable", False)]
            if not chain:
                raise ProviderError(f"彩种 {game} 没有可用的深历史源")
        if not chain:
            raise ProviderError(f"没有供应商支持彩种 {game}")
        # 优先 primary 配置
        preferred = settings.provider_primary
        chain.sort(key=lambda p: (0 if p.code == preferred else 1, p.priority))
        return chain

    def _provider_enabled(self, session: Session, code: str) -> bool:
        row = session.get(Provider, code)
        return True if row is None else row.enabled

    def _provider_priority(self, session: Session, code: str, fallback: int) -> int:
        row = session.get(Provider, code)
        return fallback if row is None else row.priority

    def _mark_provider(self, session: Session, code: str, ok: bool, message: str = "") -> None:
        row = session.get(Provider, code)
        if row is None:
            return
        if ok:
            row.last_ok_at = datetime.now()
            row.last_error = ""
        else:
            row.last_error = message[:500]

    # ---------- 写入 ----------
    def _upsert_draw(self, session: Session, raw: RawDraw, source: str, insert_only: bool = False) -> str:
        if insert_only:
            return self._insert_draw(session, raw, source)
        stmt = sqlite_insert(Draw).values(
            game_code=raw.game_code,
            issue=raw.issue,
            draw_date=raw.draw_date,
            week=raw.week,
            numbers=raw.numbers,
            ordered=raw.ordered,
            sales=raw.sales,
            pool_money=raw.pool_money,
            content=raw.content,
            source=source,
            raw=raw.raw,
            fetched_at=datetime.now(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["game_code", "issue"],
            set_={
                "draw_date": stmt.excluded.draw_date,
                "week": stmt.excluded.week,
                "numbers": stmt.excluded.numbers,
                "ordered": stmt.excluded.ordered,
                "sales": stmt.excluded.sales,
                "pool_money": stmt.excluded.pool_money,
                "content": stmt.excluded.content,
                "source": stmt.excluded.source,
                "raw": stmt.excluded.raw,
                "fetched_at": stmt.excluded.fetched_at,
            },
        )
        existing = session.execute(
            select(Draw.id).where(Draw.game_code == raw.game_code, Draw.issue == raw.issue)
        ).scalar_one_or_none()
        session.execute(stmt)
        session.flush()
        draw_id = session.execute(
            select(Draw.id).where(Draw.game_code == raw.game_code, Draw.issue == raw.issue)
        ).scalar_one()

        # 重建展开表与奖级（幂等）
        session.query(DrawNumber).filter(DrawNumber.draw_id == draw_id).delete()
        session.query(PrizeGrade).filter(PrizeGrade.draw_id == draw_id).delete()
        spec = get_game(raw.game_code)
        rows = []
        for idx, value in enumerate(raw.numbers.get("red", [])):
            rows.append(DrawNumber(draw_id=draw_id, game_code=raw.game_code, ball=spec.red.key,
                                   position=idx + 1, value=int(value), is_blue=False))
        for idx, value in enumerate(raw.numbers.get("blue", [])):
            rows.append(DrawNumber(draw_id=draw_id, game_code=raw.game_code, ball="blue",
                                   position=idx + 1, value=int(value), is_blue=True))
        session.add_all(rows)
        for prize in raw.prizes:
            if prize.get("type_num") is None and prize.get("type_money") is None:
                continue
            session.add(
                PrizeGrade(
                    draw_id=draw_id,
                    type=str(prize.get("type") or ""),
                    type_num=prize.get("type_num"),
                    type_money=prize.get("type_money"),
                )
            )
        return "updated" if existing else "inserted"

    def _insert_draw(self, session: Session, raw: RawDraw, source: str) -> str:
        """补录模式：只插入库里没有的期号，绝不覆盖官方已有数据。"""
        existing = session.execute(
            select(Draw.id).where(Draw.game_code == raw.game_code, Draw.issue == raw.issue)
        ).scalar_one_or_none()
        if existing is not None:
            return "skipped_existing"
        draw = Draw(
            game_code=raw.game_code,
            issue=raw.issue,
            draw_date=raw.draw_date,
            week=raw.week,
            numbers=raw.numbers,
            ordered=raw.ordered,
            sales=raw.sales,
            pool_money=raw.pool_money,
            content=raw.content,
            source=source,
            raw=raw.raw,
            fetched_at=datetime.now(),
        )
        session.add(draw)
        session.flush()
        self._rebuild_children(session, draw, raw)
        return "inserted"

    def _rebuild_children(self, session: Session, draw: Draw, raw: RawDraw) -> None:
        spec = get_game(raw.game_code)
        for idx, value in enumerate(raw.numbers.get("red", [])):
            session.add(DrawNumber(draw_id=draw.id, game_code=raw.game_code, ball=spec.red.key,
                                   position=idx + 1, value=int(value), is_blue=False))
        for idx, value in enumerate(raw.numbers.get("blue", [])):
            session.add(DrawNumber(draw_id=draw.id, game_code=raw.game_code, ball="blue",
                                   position=idx + 1, value=int(value), is_blue=True))

    # ---------- 同步主流程 ----------
    async def sync_game(
        self,
        game: str,
        mode: str = "incremental",
        progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        lock = self._locks[game]
        if lock.locked():
            return {"game": game, "status": "skipped", "reason": "已有同步任务在跑"}
        async with lock:
            self._running[game] = True
            started = datetime.now()
            run_id = None
            try:
                with session_scope() as session:
                    run = SyncRun(game_code=game, mode=mode, status="running", started_at=started)
                    session.add(run)
                    session.flush()
                    run_id = run.id

                stats = {"fetched": 0, "inserted": 0, "updated": 0}
                provider_code = ""
                errors: list[str] = []

                if mode == "backfill" and not any(
                    getattr(p, "backfill_capable", False) for p in registry.candidates(game)
                ):
                    # 快乐8 官方源从 2020 年才有，500.com 也没有，补录直接跳过
                    with session_scope() as session:
                        run = session.get(SyncRun, run_id)
                        if run is not None:
                            run.status = "skipped"
                            run.finished_at = datetime.now()
                            run.error = "该彩种无深历史源"
                    self._publish({"type": "sync_done", "game": game, "status": "skipped",
                                   "reason": "该彩种无深历史源"})
                    return {"game": game, "status": "skipped", "reason": "该彩种无深历史源"}
                chain = [p for p in self._provider_chain(game, mode)]
                for provider in chain:
                    with session_scope() as session:
                        if not self._provider_enabled(session, provider.code):
                            continue
                    try:
                        if mode == "full":
                            await self._run_full(game, provider, stats, progress)
                        elif mode == "backfill":
                            await self._run_backfill(game, provider, stats, progress)
                        else:
                            await self._run_incremental(game, provider, stats, progress)
                        provider_code = provider.code
                        with session_scope() as session:
                            self._mark_provider(session, provider.code, True)
                        break
                    except Exception as exc:  # noqa: BLE001
                        errors.append(f"{provider.code}: {exc}")
                        with session_scope() as session:
                            self._mark_provider(session, provider.code, False, str(exc))
                        continue

                status = "success" if provider_code else "failed"
                with session_scope() as session:
                    run = session.get(SyncRun, run_id)
                    assert run is not None
                    run.provider = provider_code
                    run.finished_at = datetime.now()
                    run.fetched = stats["fetched"]
                    run.inserted = stats["inserted"]
                    run.updated = stats["updated"]
                    run.status = status
                    run.error = " | ".join(errors)[:2000]

                result = {"game": game, "status": status, "provider": provider_code, **stats,
                          "errors": errors, "run_id": run_id}
                self._publish({"type": "sync_done", **result})
                return result
            finally:
                self._running[game] = False

    async def _run_full(self, game: str, provider: BaseProvider, stats: dict[str, int],
                        progress: Callable[[dict[str, Any]], None] | None) -> None:
        page = 1
        pages = 1
        while page <= pages:
            rows, pages = await provider.fetch_page(game, page=page, size=settings.page_size)
            if not rows:
                break
            stats["fetched"] += len(rows)
            self._write_batch(rows, provider.code, stats)
            if progress:
                progress({"game": game, "page": page, "pages": pages, **stats})
            self._publish({"type": "sync_progress", "game": game, "page": page, "pages": pages, **stats})
            page += 1

    async def _run_backfill(self, game: str, provider: BaseProvider, stats: dict[str, int],
                            progress: Callable[[dict[str, Any]], None] | None) -> None:
        """深历史补录：从兜底源翻页抓全量，只插入缺失期号，已有数据一字不改。"""
        page = 1
        pages = 1
        while page <= pages:
            rows, pages = await provider.fetch_page(game, page=page, size=settings.page_size)
            if not rows:
                break
            stats["fetched"] += len(rows)
            self._write_batch(rows, provider.code, stats, insert_only=True)
            if progress:
                progress({"game": game, "page": page, "pages": pages, **stats})
            self._publish({"type": "sync_progress", "game": game, "page": page, "pages": pages,
                           "mode": "backfill", **stats})
            page += 1

    async def _run_incremental(self, game: str, provider: BaseProvider, stats: dict[str, int],
                               progress: Callable[[dict[str, Any]], None] | None) -> None:
        with session_scope() as session:
            known = set(
                session.execute(select(Draw.issue).where(Draw.game_code == game)).scalars().all()
            )
        rows = await provider.fetch_latest(game, n=settings.page_size)
        fresh = [r for r in rows if r.issue not in known]
        if not fresh:
            # 没有新数据也算成功，但补一次最新一页的字段刷新
            fresh = rows[:1]
        stats["fetched"] += len(rows)
        self._write_batch(fresh, provider.code, stats)
        if progress:
            progress({"game": game, "page": 1, "pages": 1, **stats})

    def _write_batch(self, rows: list[RawDraw], source: str, stats: dict[str, int],
                     insert_only: bool = False) -> None:
        with session_scope() as session:
            for raw in rows:
                outcome = self._upsert_draw(session, raw, source, insert_only=insert_only)
                stats[outcome] = stats.get(outcome, 0) + 1

    async def sync_all(self, mode: str = "incremental") -> list[dict[str, Any]]:
        results = []
        for game in GAME_ORDER:
            results.append(await self.sync_game(game, mode=mode))
        return results

    # ---------- 查询 ----------
    def status(self) -> dict[str, Any]:
        with session_scope() as session:
            counts = dict(
                session.execute(select(Draw.game_code, func.count(Draw.id)).group_by(Draw.game_code)).all()
            )
            last_runs = (
                session.execute(select(SyncRun).order_by(SyncRun.id.desc()).limit(12)).scalars().all()
            )
            runs = [
                {
                    "id": r.id,
                    "game_code": r.game_code,
                    "provider": r.provider,
                    "mode": r.mode,
                    "status": r.status,
                    "started_at": r.started_at,
                    "finished_at": r.finished_at,
                    "fetched": r.fetched,
                    "inserted": r.inserted,
                    "updated": r.updated,
                    "error": r.error,
                }
                for r in last_runs
            ]
        return {
            "enabled": settings.sync_enabled,
            "running": self.is_running(),
            "counts": {g: counts.get(g, 0) for g in GAME_ORDER},
            "last_runs": runs,
            "next_jobs": [],
        }

    def missing_issues(self, game: str) -> list[str]:
        with session_scope() as session:
            issues = session.execute(
                select(Draw.issue).where(Draw.game_code == game).order_by(Draw.draw_date)
            ).scalars().all()
        if not issues:
            return []
        from ..games import issue_sort_key

        year_seqs: dict[int, set[int]] = defaultdict(set)
        for issue in issues:
            year, seq = issue_sort_key(issue)
            year_seqs[year].add(seq)
        missing: list[str] = []
        for year, seqs in year_seqs.items():
            if not seqs:
                continue
            top = max(seqs)
            for seq in range(1, top + 1):
                if seq not in seqs:
                    missing.append(f"{year}{seq:03d}")
        return missing


sync_service = SyncService()

from __future__ import annotations

import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..games import GAMES
from ..models import Draw
from ..schemas import DrawOut, DrawPage, PrizeOut

router = APIRouter(prefix="/draws", tags=["draws"])


def to_draw_out(draw: Draw) -> DrawOut:
    return DrawOut(
        id=draw.id,
        game_code=draw.game_code,
        issue=draw.issue,
        draw_date=draw.draw_date,
        week=draw.week or "",
        numbers=draw.numbers or {},
        ordered=draw.ordered,
        sales=float(draw.sales) if draw.sales is not None else None,
        pool_money=float(draw.pool_money) if draw.pool_money is not None else None,
        content=draw.content or "",
        source=draw.source or "",
        prizes=[
            PrizeOut(type=str(p.type), type_num=p.type_num,
                     type_money=float(p.type_money) if p.type_money is not None else None)
            for p in sorted(draw.prizes, key=lambda x: str(x.type))
        ],
    )


@router.get("/{game}", response_model=DrawPage)
def list_draws(
    game: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=300),
    start_date: date | None = None,
    end_date: date | None = None,
    issue: str | None = Query(None, max_length=16, description="期号，支持后缀模糊匹配，如 121 可命中 2026121"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
) -> DrawPage:
    if game not in GAMES:
        raise HTTPException(404, f"未知彩种 {game}")
    stmt = select(Draw).where(Draw.game_code == game)
    count_stmt = select(func.count(Draw.id)).where(Draw.game_code == game)
    if start_date:
        stmt = stmt.where(Draw.draw_date >= start_date)
        count_stmt = count_stmt.where(Draw.draw_date >= start_date)
    if end_date:
        stmt = stmt.where(Draw.draw_date <= end_date)
        count_stmt = count_stmt.where(Draw.draw_date <= end_date)
    if issue:
        # 期号是零填充字符串，用后缀匹配能同时命中「121」和「2026121」；
        # 前缀匹配则能命中「2026」查整年。两头都开，交给用户输入决定。
        needle = issue.strip()
        if needle:
            pattern = f"%{needle}%"
            stmt = stmt.where(Draw.issue.like(pattern))
            count_stmt = count_stmt.where(Draw.issue.like(pattern))

    total = db.execute(count_stmt).scalar_one()
    ordering = (Draw.draw_date.desc(), Draw.issue.desc()) if order == "desc" else (Draw.draw_date.asc(), Draw.issue.asc())
    rows = db.execute(stmt.order_by(*ordering).offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return DrawPage(total=total, page=page, page_size=page_size, items=[to_draw_out(d) for d in rows])


@router.get("/{game}/export.csv", include_in_schema=False)
def export_draws(
    game: str,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(20000, ge=1, le=200000),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """导出全量历史为 CSV（UTF-8 BOM，Excel 直接打开不乱码）。"""
    if game not in GAMES:
        raise HTTPException(404, f"未知彩种 {game}")
    stmt = select(Draw).where(Draw.game_code == game)
    if start_date:
        stmt = stmt.where(Draw.draw_date >= start_date)
    if end_date:
        stmt = stmt.where(Draw.draw_date <= end_date)
    rows = db.execute(
        stmt.order_by(Draw.draw_date.asc(), Draw.issue.asc()).limit(limit)
    ).scalars().all()

    def gen():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["game", "issue", "date", "week", "red", "blue", "ordered", "sales", "pool"])
        yield "\ufeff" + buf.getvalue()
        buf.seek(0)
        buf.truncate(0)
        for d in rows:
            numbers = d.numbers or {}
            writer.writerow([
                game,
                d.issue,
                d.draw_date.isoformat() if d.draw_date else "",
                d.week or "",
                " ".join(numbers.get("red", [])),
                " ".join(numbers.get("blue", [])),
                " ".join(d.ordered or []) if d.ordered else "",
                f"{float(d.sales):.2f}" if d.sales is not None else "",
                f"{float(d.pool_money):.2f}" if d.pool_money is not None else "",
            ])
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    return StreamingResponse(
        gen(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{game}-history.csv"'},
    )


@router.get("/{game}/{issue}", response_model=DrawOut)
def get_draw(game: str, issue: str, db: Session = Depends(get_db)) -> DrawOut:
    if game not in GAMES:
        raise HTTPException(404, f"未知彩种 {game}")
    draw = db.execute(select(Draw).where(Draw.game_code == game, Draw.issue == issue)).scalar_one_or_none()
    if draw is None:
        raise HTTPException(404, "期号不存在")
    return to_draw_out(draw)


@router.get("/{game}/latest/one", response_model=DrawOut)
def latest_draw(game: str, db: Session = Depends(get_db)) -> DrawOut:
    if game not in GAMES:
        raise HTTPException(404, f"未知彩种 {game}")
    draw = db.execute(
        select(Draw).where(Draw.game_code == game)
        .order_by(Draw.draw_date.desc(), Draw.issue.desc()).limit(1)
    ).scalar_one_or_none()
    if draw is None:
        raise HTTPException(404, "尚无开奖数据")
    return to_draw_out(draw)

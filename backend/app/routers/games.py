from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from ..db import get_db
from ..games import GAMES, GAME_ORDER, get_game, next_issue_guess
from ..models import Draw
from ..schemas import BallSpecOut, GameOut
from sqlalchemy.orm import Session
from fastapi import Depends
from datetime import datetime

router = APIRouter(prefix="/games", tags=["games"])


def _to_out(spec, latest) -> GameOut:
    return GameOut(
        code=spec.code,
        name=spec.name,
        short=spec.short,
        first_issue=spec.first_issue,
        draw_weekdays=list(spec.draw_weekdays),
        draw_time=spec.draw_time,
        balls=[
            BallSpecOut(
                key=b.key, label=b.label, count=b.count, min=b.minimum, max=b.maximum,
                pad=b.pad, ordered=b.ordered, domain=list(spec.domain("blue" if b.key == "blue" else "red")),
            )
            for b in spec.balls
        ],
        latest_issue=latest[0] if latest else None,
        latest_date=latest[1] if latest else None,
        latest_numbers=latest[2] if latest else None,
        next_issue=next_issue_guess(latest[0], latest[1].year if latest else None, datetime.now().year) if latest else spec.first_issue,
        draw_count=latest[3] if latest else 0,
    )


@router.get("", response_model=list[GameOut])
def list_games(db: Session = Depends(get_db)) -> list[GameOut]:
    out = []
    for code in GAME_ORDER:
        spec = get_game(code)
        total = db.execute(select(func.count(Draw.id)).where(Draw.game_code == code)).scalar_one()
        latest = db.execute(
            select(Draw.issue, Draw.draw_date, Draw.numbers)
            .where(Draw.game_code == code)
            .order_by(Draw.draw_date.desc(), Draw.issue.desc())
            .limit(1)
        ).first()
        out.append(_to_out(spec, (latest[0], latest[1], latest[2], total) if latest else None))
    return out


@router.get("/{code}", response_model=GameOut)
def get_one(code: str, db: Session = Depends(get_db)) -> GameOut:
    if code not in GAMES:
        raise HTTPException(404, f"未知彩种 {code}")
    spec = get_game(code)
    total = db.execute(select(func.count(Draw.id)).where(Draw.game_code == code)).scalar_one()
    latest = db.execute(
        select(Draw.issue, Draw.draw_date, Draw.numbers)
        .where(Draw.game_code == code)
        .order_by(Draw.draw_date.desc(), Draw.issue.desc())
        .limit(1)
    ).first()
    return _to_out(spec, (latest[0], latest[1], latest[2], total) if latest else None)

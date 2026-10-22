"""兑奖：开奖同步后自动核对预测票与票夹，写回命中情况。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..games import get_game
from ..models import Draw, PredictionRun, PredictionTicket, Ticket


def _actual_numbers(draw: Draw) -> set[int]:
    numbers = draw.numbers or {}
    values: set[int] = set()
    for key in ("red", "blue"):
        for v in numbers.get(key) or []:
            try:
                values.add(int(v))
            except (TypeError, ValueError):
                continue
    return values


def _actual_red(draw: Draw) -> list[int]:
    out = []
    for v in (draw.numbers or {}).get("red") or []:
        try:
            out.append(int(v))
        except (TypeError, ValueError):
            continue
    return out


def settle_pending(session: Session, game: str | None = None) -> dict[str, Any]:
    runs_checked = 0
    tickets_checked = 0

    query = select(PredictionRun).where(PredictionRun.checked.is_(False))
    if game:
        query = query.where(PredictionRun.game_code == game)
    for run in session.execute(query).scalars().all():
        draw = session.execute(
            select(Draw).where(Draw.game_code == run.game_code, Draw.issue == run.target_issue)
        ).scalar_one_or_none()
        if draw is None:
            continue
        actual = _actual_numbers(draw)
        actual_red = set(_actual_red(draw))
        spec = get_game(run.game_code)
        hits_per_ticket = []
        for ticket in run.tickets_rel:
            numbers = ticket.numbers or {}
            picked = {int(v) for v in (numbers.get("red") or []) if str(v).isdigit()}
            hit = len(picked & actual_red)
            hit_detail = {
                "hit": hit,
                "total": len(picked),
                "matched": sorted(picked & actual_red),
                "actual": sorted(actual_red),
            }
            if spec.blue is not None:
                blue_pick = {int(v) for v in (numbers.get("blue") or []) if str(v).isdigit()}
                blue_actual = {int(v) for v in (draw.numbers or {}).get("blue") or [] if str(v).isdigit()}
                hit_detail["blue_hit"] = len(blue_pick & blue_actual)
            ticket.hit_detail = hit_detail
            hits_per_ticket.append(hit)
        if hits_per_ticket:
            run.hit_summary = {
                "issue": draw.issue,
                "max_hit": max(hits_per_ticket),
                "avg_hit": round(sum(hits_per_ticket) / len(hits_per_ticket), 3),
                "any_prize": max(hits_per_ticket) >= (6 if run.game_code in ("ssq", "qlc") else 3),
            }
        run.checked = True
        runs_checked += 1

    tquery = select(Ticket).where(Ticket.settled.is_(False))
    if game:
        tquery = tquery.where(Ticket.game_code == game)
    for ticket in session.execute(tquery).scalars().all():
        draw = session.execute(
            select(Draw).where(Draw.game_code == ticket.game_code, Draw.issue == ticket.issue)
        ).scalar_one_or_none()
        if draw is None:
            continue
        actual_red = set(_actual_red(draw))
        numbers = ticket.numbers or {}
        picked = {int(v) for v in (numbers.get("red") or []) if str(v).isdigit()}
        hit = len(picked & actual_red)
        blue_hit = 0
        blue_pick = {int(v) for v in (numbers.get("blue") or []) if str(v).isdigit()}
        blue_actual = {int(v) for v in (draw.numbers or {}).get("blue") or [] if str(v).isdigit()}
        blue_hit = len(blue_pick & blue_actual)
        ticket.hit_detail = {"hit": hit, "blue_hit": blue_hit, "matched": sorted(picked & actual_red)}
        ticket.prize = _prize(ticket.game_code, hit, blue_hit)
        ticket.settled = True
        tickets_checked += 1

    if runs_checked or tickets_checked:
        session.commit()
    return {"runs_checked": runs_checked, "tickets_checked": tickets_checked}


def _prize(game: str, hit: int, blue_hit: int) -> float:
    """按公开奖级规则估算奖金（仅示意，实际以官方为准）。"""
    table = {
        "ssq": {(6, 1): 6_000_000.0, (6, 0): 300_000.0, (5, 1): 3000.0, (5, 0): 200.0,
                (4, 1): 200.0, (4, 0): 10.0, (3, 1): 10.0, (2, 1): 5.0, (1, 1): 5.0, (0, 1): 5.0},
        "qlc": {(7, 1): 2_000_000.0, (7, 0): 100_000.0, (6, 1): 2000.0, (6, 0): 500.0,
                (5, 1): 50.0, (5, 0): 20.0, (4, 1): 10.0, (4, 0): 5.0},
        "3d": {(3, 0): 1040.0},
        "kl8": {},
    }
    return float(table.get(game, {}).get((hit, blue_hit), 0.0))

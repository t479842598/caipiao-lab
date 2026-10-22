"""兑奖：开奖同步后自动核对预测票与票夹，写回命中情况。

奖金口径分两类：
1. **浮动奖**（双色球一/二等奖、七乐彩一/二等奖等）—— 每期金额不同，
   必须从该期官方 `prize_grades` 里取，不能写死。
2. **固定奖**（3D 直选/组三/组六、快乐8 各档）—— 官方规则固定，
   但快乐8 的金额仍以该期 `prize_grades` 为准（官方会调整），查不到才退回内置表。
"""

from __future__ import annotations

from collections import Counter
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


def _actual_blue(draw: Draw) -> set[int]:
    out: set[int] = set()
    for v in (draw.numbers or {}).get("blue") or []:
        try:
            out.add(int(v))
        except (TypeError, ValueError):
            continue
    return out


def _actual_ordered(draw: Draw) -> list[int]:
    """3D 的位序号码：优先 ordered 字段，回退到 numbers.red。"""
    raw = draw.ordered if draw.ordered else (draw.numbers or {}).get("red") or []
    out: list[int] = []
    for v in raw:
        try:
            out.append(int(v))
        except (TypeError, ValueError):
            continue
    return out


def _to_int_list(values: Any) -> list[int]:
    out: list[int] = []
    for v in values or []:
        try:
            out.append(int(v))
        except (TypeError, ValueError):
            continue
    return out


def _grade_money(draw: Draw, grade_type: str) -> float | None:
    """从该期官方奖级里取某档奖金；查不到返回 None（表示应回退内置表）。"""
    for p in draw.prizes:
        if str(p.type) == str(grade_type) and p.type_money is not None:
            money = float(p.type_money)
            if money > 0:
                return money
    return None


# --------------------------------------------------------------------------- #
# 各彩种规则
# --------------------------------------------------------------------------- #
def _ssq_grade(hit_red: int, hit_blue: int) -> str | None:
    """双色球奖级：返回官方 type 字符串（1-6），未中奖返回 None。

    规则（红球中 hit_red 个，蓝球中 hit_blue 个）：
      一等 6+1 / 二等 6+0 / 三等 5+1 / 四等 5+0 或 4+1
      五等 4+0 或 3+1 / 六等 2+1、1+1、0+1
    """
    if hit_red == 6 and hit_blue == 1:
        return "1"
    if hit_red == 6 and hit_blue == 0:
        return "2"
    if hit_red == 5 and hit_blue == 1:
        return "3"
    if hit_red == 5 and hit_blue == 0:
        return "4"
    if hit_red == 4 and hit_blue == 1:
        return "4"
    if hit_red == 4 and hit_blue == 0:
        return "5"
    if hit_red == 3 and hit_blue == 1:
        return "5"
    if hit_blue == 1 and hit_red <= 2:
        return "6"
    return None


# 双色球六等奖固定 5 元，其余档位若官方数据缺失时的兜底（仅示意，实际以官方为准）
_SSQ_FALLBACK = {"1": 5_000_000.0, "2": 150_000.0, "3": 3000.0, "4": 200.0, "5": 10.0, "6": 5.0}


def _qlc_grade(hit_red: int, hit_blue: int) -> str | None:
    """七乐彩奖级：7 个基本号 + 1 个特别号。

    一等 7+0 / 二等 6+1 / 三等 6+0 / 四等 5+1
    五等 5+0 / 六等 4+1 / 七等 4+0
    """
    if hit_red == 7:
        return "1"
    if hit_red == 6 and hit_blue == 1:
        return "2"
    if hit_red == 6:
        return "3"
    if hit_red == 5 and hit_blue == 1:
        return "4"
    if hit_red == 5:
        return "5"
    if hit_red == 4 and hit_blue == 1:
        return "6"
    if hit_red == 4:
        return "7"
    return None


_QLC_FALLBACK = {"1": 2_000_000.0, "2": 30_000.0, "3": 2000.0, "4": 200.0,
                 "5": 50.0, "6": 10.0, "7": 5.0}


# 3D 固定奖金（国家规定，不随期变动）
_SD_DIRECT = 1040.0   # 直选
_SD_GROUP3 = 346.0    # 组三（开奖号有且仅有一对相同）
_SD_GROUP6 = 173.0    # 组六（开奖号三位互不相同）


def _sd_prize(ticket_ordered: list[int], draw_ordered: list[int]) -> tuple[float, str]:
    """3D 兑奖：先判直选（顺序完全一致），再判组选（排序后一致）。

    组选奖金取决于**开奖号码的形态**而非投注方式：
      - 开奖三位互不相同 → 组六 173
      - 开奖有且仅有一对相同 → 组三 346
      - 开奖三位全同（豹子）→ 只有直选能中，组选不设奖
    """
    if len(ticket_ordered) != 3 or len(draw_ordered) != 3:
        return 0.0, "none"
    if ticket_ordered == draw_ordered:
        return _SD_DIRECT, "direct"
    if sorted(ticket_ordered) != sorted(draw_ordered):
        return 0.0, "none"
    counts = Counter(draw_ordered)
    if len(counts) == 3:
        return _SD_GROUP6, "group6"
    if len(counts) == 2:
        return _SD_GROUP3, "group3"
    # 豹子号（如 555）：组选不设奖
    return 0.0, "none"


def _kl8_prize(picked: set[int], draw_red: set[int], draw: Draw) -> tuple[float, str]:
    """快乐8：选 `len(picked)` 个号，命中 `hit` 个，按 `x{pick}z{hit}` 查官方奖级。

    官方 `prize_grades.type` 形如 `x10z10`（选十中十）、`x9z8`（选九中八）。
    """
    pick = len(picked)
    if pick == 0:
        return 0.0, "none"
    hit = len(picked & draw_red)
    code = f"x{pick}z{hit}"
    money = _grade_money(draw, code)
    if money is not None:
        return money, code
    # 官方数据缺失时按公开规则兜底（选十玩法）
    fallback = {10: 5_000_000.0, 9: 250_000.0, 8: 8000.0, 7: 720.0,
                6: 80.0, 5: 5.0, 4: 3.0, 3: 2.0}
    if pick == 10 and hit >= 3:
        return fallback.get(hit, 0.0), code
    return 0.0, code


def settle_ticket(game: str, numbers: dict[str, Any], draw: Draw) -> dict[str, Any]:
    """算一张票的命中与奖金，返回可直接存进 `hit_detail` 的字典。

    不依赖 Ticket 对象，方便单测直接喂 draw + numbers。
    """
    detail: dict[str, Any] = {"game": game, "issue": draw.issue}

    if game == "3d":
        ticket_ordered = _to_int_list(numbers.get("ordered") or numbers.get("red"))
        draw_ordered = _actual_ordered(draw)
        prize, kind = _sd_prize(ticket_ordered, draw_ordered)
        detail.update({
            "hit": sum(1 for a, b in zip(ticket_ordered, draw_ordered) if a == b),
            "total": len(ticket_ordered),
            "kind": kind,
            "actual": draw_ordered,
            "matched": sorted(set(ticket_ordered) & set(draw_ordered)),
            "prize": prize,
        })
        return detail

    if game == "kl8":
        picked = set(_to_int_list(numbers.get("red")))
        draw_red = set(_actual_red(draw))
        prize, code = _kl8_prize(picked, draw_red, draw)
        detail.update({
            "hit": len(picked & draw_red),
            "total": len(picked),
            "kind": code,
            "actual": sorted(draw_red),
            "matched": sorted(picked & draw_red),
            "prize": prize,
        })
        return detail

    # 双色球 / 七乐彩：命中数 → 奖级 → 官方金额
    picked = set(_to_int_list(numbers.get("red")))
    draw_red = set(_actual_red(draw))
    hit_red = len(picked & draw_red)
    blue_pick = set(_to_int_list(numbers.get("blue")))
    blue_actual = _actual_blue(draw)
    hit_blue = len(blue_pick & blue_actual)

    if game == "ssq":
        grade = _ssq_grade(hit_red, hit_blue)
        money = _grade_money(draw, grade) if grade else None
        prize = money if money is not None else _SSQ_FALLBACK.get(grade or "", 0.0)
    elif game == "qlc":
        grade = _qlc_grade(hit_red, hit_blue)
        money = _grade_money(draw, grade) if grade else None
        prize = money if money is not None else _QLC_FALLBACK.get(grade or "", 0.0)
    else:
        grade = None
        prize = 0.0

    detail.update({
        "hit": hit_red,
        "blue_hit": hit_blue,
        "total": len(picked),
        "grade": grade,
        "actual": sorted(draw_red),
        "matched": sorted(picked & draw_red),
        "prize": float(prize or 0.0),
    })
    return detail


# --------------------------------------------------------------------------- #
# 批量兑奖
# --------------------------------------------------------------------------- #
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
        spec = get_game(run.game_code)
        hits_per_ticket = []
        prizes_per_ticket = []
        for ticket in run.tickets_rel:
            result = settle_ticket(run.game_code, ticket.numbers or {}, draw)
            ticket.hit_detail = result
            hits_per_ticket.append(result.get("hit", 0))
            prizes_per_ticket.append(result.get("prize", 0.0))
        if hits_per_ticket:
            run.hit_summary = {
                "issue": draw.issue,
                "max_hit": max(hits_per_ticket),
                "avg_hit": round(sum(hits_per_ticket) / len(hits_per_ticket), 3),
                "any_prize": max(prizes_per_ticket) > 0 if prizes_per_ticket else False,
                "max_prize": max(prizes_per_ticket) if prizes_per_ticket else 0.0,
                "game": spec.code,
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
        result = settle_ticket(ticket.game_code, ticket.numbers or {}, draw)
        ticket.hit_detail = result
        ticket.prize = float(result.get("prize", 0.0) or 0.0)
        ticket.settled = True
        tickets_checked += 1

    if runs_checked or tickets_checked:
        session.commit()
    return {"runs_checked": runs_checked, "tickets_checked": tickets_checked}

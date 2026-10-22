"""票夹：管理员登录后归到账号，游客归到设备号，彼此不可见不可删。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from ..auth_deps import Principal, optional_user
from ..config import settings
from ..db import get_db
from ..games import GAMES
from ..models import Ticket
from ..schemas import TicketCreate, TicketOut, TicketStatsOut

router = APIRouter(prefix="/tickets", tags=["tickets"])


def _owner_key(who: Principal, request: Request, device_id: str | None) -> str:
    if who.user_id is not None:
        return f"u:{who.user_id}"
    did = (device_id or request.headers.get("x-device-id", "") or "").strip()
    if not did or len(did) > 40:
        raise HTTPException(400, "缺少设备标识 X-Device-Id")
    safe = "".join(ch for ch in did if ch.isalnum() or ch in "-_")
    if not safe:
        raise HTTPException(400, "设备标识非法")
    return f"d:{safe}"


def _to_out(t: Ticket) -> TicketOut:
    return TicketOut(
        id=t.id,
        game_code=t.game_code,
        issue=t.issue or "",
        numbers=t.numbers or {},
        cost=float(t.cost or 0),
        note=t.note or "",
        source=t.source or "",
        created_at=t.created_at,
        settled=bool(t.settled),
        prize=float(t.prize or 0),
        hit_detail=t.hit_detail,
    )


@router.get("", response_model=list[TicketOut])
def list_tickets(
    game: str | None = None,
    limit: int = 200,
    request: Request = None,  # type: ignore[assignment]
    db: OrmSession = Depends(get_db),
    who: Principal = Depends(optional_user),
    device_id: str | None = Header(default=None, alias="X-Device-Id"),
) -> list[TicketOut]:
    key = _owner_key(who, request, device_id)
    limit = max(1, min(limit, 500))
    stmt = select(Ticket).where(Ticket.owner_key == key)
    if game:
        if game not in GAMES:
            raise HTTPException(404, f"未知彩种 {game}")
        stmt = stmt.where(Ticket.game_code == game)
    rows = db.execute(stmt.order_by(Ticket.id.desc()).limit(limit)).scalars().all()
    return [_to_out(t) for t in rows]


@router.post("", response_model=TicketOut)
def create_ticket(
    payload: TicketCreate,
    request: Request,
    db: OrmSession = Depends(get_db),
    who: Principal = Depends(optional_user),
    device_id: str | None = Header(default=None, alias="X-Device-Id"),
) -> TicketOut:
    if settings.read_only:
        raise HTTPException(403, "当前为只读模式")
    if payload.game_code not in GAMES:
        raise HTTPException(404, f"未知彩种 {payload.game_code}")
    if payload.cost < 0 or payload.cost > 100000:
        raise HTTPException(400, "金额超出允许范围")
    key = _owner_key(who, request, device_id)
    row = Ticket(
        game_code=payload.game_code,
        issue=(payload.issue or "").strip()[:16],
        numbers=payload.numbers or {},
        cost=payload.cost,
        note=(payload.note or "")[:500],
        source="manual",
        owner_key=key,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.delete("/{ticket_id}")
def delete_ticket(
    ticket_id: int,
    request: Request,
    db: OrmSession = Depends(get_db),
    who: Principal = Depends(optional_user),
    device_id: str | None = Header(default=None, alias="X-Device-Id"),
) -> dict:
    if settings.read_only:
        raise HTTPException(403, "当前为只读模式")
    key = _owner_key(who, request, device_id)
    row = db.get(Ticket, ticket_id)
    if row is None or row.owner_key != key:
        raise HTTPException(404, "票不存在")
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.get("/stats/summary", response_model=TicketStatsOut)
def stats(
    request: Request,
    db: OrmSession = Depends(get_db),
    who: Principal = Depends(optional_user),
    device_id: str | None = Header(default=None, alias="X-Device-Id"),
) -> TicketStatsOut:
    key = _owner_key(who, request, device_id)
    rows = db.execute(select(Ticket).where(Ticket.owner_key == key)).scalars().all()
    total_cost = sum(float(r.cost or 0) for r in rows)
    total_prize = sum(float(r.prize or 0) for r in rows)
    by_game: dict[str, dict] = {}
    for r in rows:
        item = by_game.setdefault(r.game_code, {"game_code": r.game_code, "count": 0, "cost": 0.0, "prize": 0.0})
        item["count"] += 1
        item["cost"] += float(r.cost or 0)
        item["prize"] += float(r.prize or 0)
    return TicketStatsOut(
        total_tickets=len(rows),
        total_cost=round(total_cost, 2),
        total_prize=round(total_prize, 2),
        roi=round(total_prize / total_cost, 4) if total_cost else 0.0,
        settled=sum(1 for r in rows if r.settled),
        pending=sum(1 for r in rows if not r.settled),
        by_game=list(by_game.values()),
    )

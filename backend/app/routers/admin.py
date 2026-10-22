"""管理后台：审计查询、账号维护、系统概览。全部需要管理员身份。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session as OrmSession

from ..auth_deps import Principal, client_ip, require_admin
from ..config import settings
from ..db import get_db
from ..models import AiAnalysis, AiProvider, AuditLog, Draw, PredictionRun, SyncRun, Ticket, User, UserSession
from ..schemas import (
    AdminOverviewOut,
    AuditOut,
    SessionOut,
    UserAdminCreate,
    UserAdminPatch,
    UserOut,
)
from ..security import audit, hash_password, password_ok, utcnow

router = APIRouter(prefix="/admin", tags=["admin"])


def _audit_out(row: AuditLog) -> AuditOut:
    return AuditOut(
        id=row.id,
        at=row.at,
        actor=row.actor,
        action=row.action,
        target=row.target,
        detail=row.detail or {},
        ip=row.ip,
        ua=row.ua,
        status=row.status,
    )


def _user_out(row: User) -> UserOut:
    return UserOut(
        id=row.id,
        username=row.username,
        display_name=row.display_name,
        role=row.role,
        enabled=row.enabled,
        last_login_at=row.last_login_at,
        password_changed_at=row.password_changed_at,
    )


@router.get("/overview", response_model=AdminOverviewOut)
def overview(
    db: OrmSession = Depends(get_db),
    _: Principal = Depends(require_admin),
) -> AdminOverviewOut:
    def count(stmt) -> int:
        return int(db.execute(stmt).scalar() or 0)

    return AdminOverviewOut(
        draws=count(select(func.count(Draw.id))),
        tickets=count(select(func.count(Ticket.id))),
        predictions=count(select(func.count(PredictionRun.id))),
        sync_runs=count(select(func.count(SyncRun.id))),
        ai_providers=count(select(func.count(AiProvider.id))),
        ai_pending=count(
            select(func.count(AiProvider.id)).where(AiProvider.status == "pending")
        ),
        ai_analyses=count(select(func.count(AiAnalysis.id))),
        users=count(select(func.count(User.id))),
        sessions=count(
            select(func.count(UserSession.id)).where(UserSession.revoked.is_(False))
        ),
        audit_logs=count(select(func.count(AuditLog.id))),
        read_only=settings.read_only,
        sync_enabled=settings.sync_enabled,
        ai_enabled=settings.ai_enabled,
        docs_enabled=settings.enable_docs,
        cookie_secure=settings.cookie_secure,
        admin_token_set=bool(settings.admin_token),
    )


@router.get("/audit", response_model=list[AuditOut])
def list_audit(
    action: str = "",
    actor: str = "",
    status: str = "",
    limit: int = Query(default=100, ge=1, le=500),
    db: OrmSession = Depends(get_db),
    _: Principal = Depends(require_admin),
) -> list[AuditOut]:
    stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if actor:
        stmt = stmt.where(AuditLog.actor == actor)
    if status:
        stmt = stmt.where(AuditLog.status == status)
    return [_audit_out(row) for row in db.execute(stmt).scalars().all()]


@router.get("/audit/actions")
def audit_actions(
    db: OrmSession = Depends(get_db),
    _: Principal = Depends(require_admin),
) -> list[dict]:
    rows = db.execute(
        select(AuditLog.action, func.count(AuditLog.id))
        .group_by(AuditLog.action)
        .order_by(func.count(AuditLog.id).desc())
        .limit(50)
    ).all()
    return [{"action": a, "count": int(c)} for a, c in rows]


@router.get("/users", response_model=list[UserOut])
def list_users(
    db: OrmSession = Depends(get_db),
    _: Principal = Depends(require_admin),
) -> list[UserOut]:
    rows = db.execute(select(User).order_by(User.id)).scalars().all()
    return [_user_out(row) for row in rows]


@router.post("/users", response_model=UserOut)
def create_user(
    payload: UserAdminCreate,
    request: Request,
    db: OrmSession = Depends(get_db),
    who: Principal = Depends(require_admin),
) -> UserOut:
    ok, msg = password_ok(payload.password)
    if not ok:
        raise HTTPException(400, msg)
    exists = db.execute(select(User).where(User.username == payload.username)).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(409, "账号已存在")
    row = User(
        username=payload.username.strip(),
        password_hash=hash_password(payload.password),
        display_name=payload.display_name.strip() or payload.username,
        role=payload.role,
        enabled=True,
        created_at=utcnow(),
        password_changed_at=utcnow(),
    )
    db.add(row)
    db.flush()
    audit(db, actor=who.username, action="user_create", target=row.username,
          ip=client_ip(request), ua=request.headers.get("user-agent", ""))
    db.commit()
    db.refresh(row)
    return _user_out(row)


@router.patch("/users/{user_id}", response_model=UserOut)
def patch_user(
    user_id: int,
    payload: UserAdminPatch,
    request: Request,
    db: OrmSession = Depends(get_db),
    who: Principal = Depends(require_admin),
) -> UserOut:
    row = db.get(User, user_id)
    if row is None:
        raise HTTPException(404, "账号不存在")
    changed: dict[str, object] = {}
    if payload.enabled is not None and payload.enabled != row.enabled:
        if row.username == who.username and not payload.enabled:
            raise HTTPException(400, "不能停用当前登录的账号")
        row.enabled = payload.enabled
        changed["enabled"] = payload.enabled
    if payload.role is not None and payload.role != row.role:
        if row.username == who.username:
            raise HTTPException(400, "不能修改自己的角色")
        if payload.role not in ("admin", "viewer"):
            raise HTTPException(400, "角色只能是 admin 或 viewer")
        row.role = payload.role
        changed["role"] = payload.role
    if payload.password:
        ok, msg = password_ok(payload.password)
        if not ok:
            raise HTTPException(400, msg)
        row.password_hash = hash_password(payload.password)
        row.password_changed_at = utcnow()
        changed["password"] = "reset"
    if payload.display_name is not None:
        row.display_name = payload.display_name.strip()[:64]
        changed["display_name"] = row.display_name
    audit(db, actor=who.username, action="user_patch", target=row.username, detail=changed,
          ip=client_ip(request), ua=request.headers.get("user-agent", ""))
    db.commit()
    db.refresh(row)
    return _user_out(row)


@router.delete("/sessions/{session_id}")
def kill_session(
    session_id: int,
    request: Request,
    db: OrmSession = Depends(get_db),
    who: Principal = Depends(require_admin),
) -> dict:
    row = db.get(UserSession, session_id)
    if row is None:
        raise HTTPException(404, "会话不存在")
    row.revoked = True
    audit(db, actor=who.username, action="admin_session_revoke", target=str(session_id),
          ip=client_ip(request))
    db.commit()
    return {"ok": True}


@router.get("/sessions", response_model=list[SessionOut])
def all_sessions(
    limit: int = Query(default=50, ge=1, le=200),
    db: OrmSession = Depends(get_db),
    who: Principal = Depends(require_admin),
) -> list[SessionOut]:
    rows = db.execute(
        select(UserSession).order_by(UserSession.id.desc()).limit(limit)
    ).scalars().all()
    return [
        SessionOut(
            id=row.id,
            created_at=row.created_at,
            expires_at=row.expires_at,
            last_seen_at=row.last_seen_at,
            ip=row.ip,
            user_agent=row.user_agent,
            current=row.id == who.session_id,
        )
        for row in rows
    ]

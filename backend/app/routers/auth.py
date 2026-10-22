"""账号登录 / 登出 / 改密 / 会话管理。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from ..auth_deps import Principal, client_ip, current_user, optional_user, require_admin, require_login
from ..config import settings
from ..db import get_db
from ..models import User, UserSession
from ..schemas import (
    ChangePasswordIn,
    LoginIn,
    LoginOut,
    MeOut,
    RegisterIn,
    SessionOut,
    UserOut,
)
from ..security import (
    CSRF_VALUE,
    SESSION_COOKIE,
    audit,
    clear_failures,
    create_session,
    failure_count,
    hash_password,
    password_ok,
    register_failure,
    revoke_all,
    revoke_session,
    utcnow,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        enabled=user.enabled,
        last_login_at=user.last_login_at,
        password_changed_at=user.password_changed_at,
    )


@router.post("/login", response_model=LoginOut)
def login(payload: LoginIn, request: Request, response: Response, db: OrmSession = Depends(get_db)) -> LoginOut:
    ip = client_ip(request)
    key = f"{payload.username.lower()}|{ip}"
    locked = failure_count(key)
    if locked >= settings.login_max_fails:
        raise HTTPException(429, f"登录失败次数过多，请 {settings.login_lock_minutes} 分钟后再试")

    user = db.execute(select(User).where(User.username == payload.username)).scalar_one_or_none()
    ok = bool(user and user.enabled and verify_password(payload.password, user.password_hash))
    if not ok:
        count = register_failure(key)
        audit(
            db, actor=payload.username[:64], action="login", status="fail",
            detail={"fails": count}, ip=ip, ua=request.headers.get("user-agent", ""),
        )
        db.commit()
        raise HTTPException(401, "账号或密码错误")

    clear_failures(key)
    user.last_login_at = utcnow()
    user.last_login_ip = ip
    token, _row = create_session(db, user, ip=ip, ua=request.headers.get("user-agent", ""))
    audit(db, actor=user.username, action="login", status="ok", ip=ip,
          ua=request.headers.get("user-agent", ""))
    db.commit()

    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )
    return LoginOut(ok=True, user=_user_out(user), csrf=CSRF_VALUE)


@router.post("/register", response_model=LoginOut)
def register(
    payload: RegisterIn,
    request: Request,
    response: Response,
    db: OrmSession = Depends(get_db),
) -> LoginOut:
    """普通用户注册。注册即登录，票夹随账号跨设备同步。

    与管理员账号共用 users 表，靠 role 区分：admin 能进后台，user 只能用前台功能。
    """
    ip = client_ip(request)
    # 复用登录失败计数器做注册限流，防止批量刷号
    key = f"register|{ip}"
    if failure_count(key) >= settings.login_max_fails:
        raise HTTPException(429, f"注册过于频繁，请 {settings.login_lock_minutes} 分钟后再试")

    exists = db.execute(select(User).where(User.username == payload.username)).scalar_one_or_none()
    if exists is not None:
        register_failure(key)
        raise HTTPException(400, "该用户名已被占用")

    ok, msg = password_ok(payload.password)
    if not ok:
        raise HTTPException(400, msg)

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        display_name=(payload.display_name or payload.username)[:64],
        role="user",
        enabled=True,
        password_changed_at=utcnow(),
    )
    db.add(user)
    db.flush()

    user.last_login_at = utcnow()
    user.last_login_ip = ip
    token, _row = create_session(db, user, ip=ip, ua=request.headers.get("user-agent", ""))
    audit(db, actor=user.username, action="register", status="ok", ip=ip,
          ua=request.headers.get("user-agent", ""))
    db.commit()

    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )
    return LoginOut(ok=True, user=_user_out(user), csrf=CSRF_VALUE)


@router.post("/logout")
def logout(request: Request, response: Response, db: OrmSession = Depends(get_db)) -> dict:
    token = request.cookies.get(SESSION_COOKIE, "")
    from ..security import session_from_token

    found = session_from_token(db, token)
    if found:
        row, user = found
        revoke_session(db, row)
        audit(db, actor=user.username, action="logout", ip=client_ip(request))
        db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/me", response_model=MeOut)
def me(who: Principal = Depends(optional_user), db: OrmSession = Depends(get_db)) -> MeOut:
    # 任何已登录身份（管理员或普通用户）都算 authenticated，
    # 后台权限由前端按 role 判断，不能在这里把普通用户当游客。
    if who.kind == "anonymous":
        return MeOut(authenticated=False, ai_enabled=settings.ai_enabled)

    user = db.get(User, who.user_id) if who.user_id else None
    if user is not None:
        return MeOut(
            authenticated=True,
            user=UserOut(
                id=user.id,
                username=user.username,
                display_name=user.display_name or "",
                role=user.role,
                enabled=user.enabled,
                last_login_at=user.last_login_at,
                password_changed_at=user.password_changed_at,
            ),
            csrf=CSRF_VALUE,
            ai_enabled=settings.ai_enabled,
        )
    # 静态令牌模式
    return MeOut(
        authenticated=True,
        user=UserOut(id=0, username=who.username, display_name="静态令牌", role=who.role, enabled=True),
        csrf=CSRF_VALUE,
        ai_enabled=settings.ai_enabled,
    )


@router.post("/password")
def change_password(
    payload: ChangePasswordIn,
    request: Request,
    db: OrmSession = Depends(get_db),
    who: Principal = Depends(require_login),
) -> dict:
    if who.user_id is None:
        raise HTTPException(400, "静态令牌模式不支持改密")
    user = db.get(User, who.user_id)
    if user is None:
        raise HTTPException(404, "账号不存在")
    if not verify_password(payload.old_password, user.password_hash):
        audit(db, actor=user.username, action="password", status="fail", ip=client_ip(request))
        db.commit()
        raise HTTPException(400, "原密码不正确")
    ok, msg = password_ok(payload.new_password)
    if not ok:
        raise HTTPException(400, msg)
    user.password_hash = hash_password(payload.new_password)
    user.password_changed_at = utcnow()
    killed = revoke_all(db, user.id)
    audit(db, actor=user.username, action="password", status="ok",
          detail={"revoked_sessions": killed}, ip=client_ip(request))
    db.commit()
    return {"ok": True, "revoked_sessions": killed, "relogin": True}


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(
    db: OrmSession = Depends(get_db),
    who: Principal = Depends(require_login),
) -> list[SessionOut]:
    if who.user_id is None:
        return []
    rows = db.execute(
        select(UserSession)
        .where(UserSession.user_id == who.user_id, UserSession.revoked.is_(False))
        .order_by(UserSession.id.desc())
        .limit(50)
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


@router.delete("/sessions/{session_id}")
def kill_session(
    session_id: int,
    request: Request,
    db: OrmSession = Depends(get_db),
    who: Principal = Depends(require_login),
) -> dict:
    row = db.get(UserSession, session_id)
    if row is None or (who.user_id is not None and row.user_id != who.user_id):
        raise HTTPException(404, "会话不存在")
    revoke_session(db, row)
    audit(db, actor=who.username, action="session_revoke", target=str(session_id), ip=client_ip(request))
    db.commit()
    return {"ok": True}


@router.post("/bootstrap")
def bootstrap(db: OrmSession = Depends(get_db), who: Principal = Depends(require_admin)) -> dict:
    """确保默认管理员存在（首启自动创建，重复调用幂等）。"""
    from ..bootstrapping import ensure_admin

    created = ensure_admin(db)
    return {"ok": True, "created": created}


@router.get("/whoami", include_in_schema=False)
def whoami(who: Principal = Depends(optional_user)) -> dict:
    return {"kind": who.kind, "username": who.username, "role": who.role}


__all__ = ["router", "current_user"]

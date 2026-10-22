"""鉴权依赖：从 Cookie / 静态令牌解析出管理员身份。"""

from __future__ import annotations

import hmac
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session as OrmSession

from .config import settings
from .db import get_db
from .models import User
from .security import SESSION_COOKIE, session_from_token


@dataclass
class Principal:
    """当前请求的身份。kind = session | token | anonymous。"""

    username: str = "anonymous"
    user_id: int | None = None
    role: str = "guest"
    kind: str = "anonymous"
    session_id: int | None = None

    @property
    def is_admin(self) -> bool:
        return self.role in ("admin", "owner")


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real = request.headers.get("x-real-ip", "")
    if real:
        return real.strip()
    return request.client.host if request.client else ""


def resolve_principal(
    request: Request,
    db: OrmSession,
    admin_token: str | None = None,
) -> Principal:
    # 1) 静态令牌（兼容旧部署 / 脚本调用）
    expected = settings.admin_token
    if expected and admin_token and hmac.compare_digest(admin_token, expected):
        return Principal(username="token", role="admin", kind="token")

    # 2) 会话 Cookie
    token = request.cookies.get(SESSION_COOKIE, "")
    found = session_from_token(db, token)
    if found:
        row, user = found
        return Principal(
            username=user.username,
            user_id=user.id,
            role=user.role,
            kind="session",
            session_id=row.id,
        )
    return Principal()


def require_admin(
    request: Request,
    db: OrmSession = Depends(get_db),
    admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> Principal:
    who = resolve_principal(request, db, admin_token)
    if not who.is_admin:
        raise HTTPException(401, "需要管理员登录")
    if who.kind == "session" and request.method not in ("GET", "HEAD", "OPTIONS"):
        # 会话 Cookie 走 CSRF 双保险：写操作必须带自定义头
        if request.headers.get("x-csrf", "") != "1":
            raise HTTPException(403, "缺少 CSRF 头")
    return who


def optional_user(
    request: Request,
    db: OrmSession = Depends(get_db),
    admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> Principal:
    return resolve_principal(request, db, admin_token)


def current_user(
    who: Principal = Depends(require_admin),
    db: OrmSession = Depends(get_db),
) -> User:
    if who.user_id is None:
        raise HTTPException(401, "静态令牌无法执行该操作，请用管理员账号登录")
    user = db.get(User, who.user_id)
    if user is None:
        raise HTTPException(401, "账号不存在")
    return user

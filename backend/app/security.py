"""安全基础设施：口令哈希、会话令牌、密钥加密、登录限速、审计记录。

只依赖标准库 + cryptography，不引入 passlib/bcrypt/jose。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from .config import settings
from .models import AuditLog, User, UserSession

SESSION_COOKIE = "cp_session"
CSRF_HEADER = "x-csrf"
CSRF_VALUE = "1"
SCRYPT_N = 2 ** 14
SCRYPT_R = 8
SCRYPT_P = 1
SECRET_FILE = "data-secret.key"


# --------------------------------------------------------------------------- #
# 口令
# --------------------------------------------------------------------------- #
def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
    return "scrypt$%d$%d$%d$%s$%s" % (SCRYPT_N, SCRYPT_R, SCRYPT_P, _b64(salt), _b64(dk))


def verify_password(password: str, stored: str) -> bool:
    if not stored or stored.count("$") != 5:
        return False
    try:
        algo, n, r, p, salt_s, hash_s = stored.split("$")
        if algo != "scrypt":
            return False
        dk = hashlib.scrypt(
            password.encode("utf-8"), salt=_unb64(salt_s), n=int(n), r=int(r), p=int(p), dklen=32
        )
        return hmac.compare_digest(dk, _unb64(hash_s))
    except (ValueError, TypeError):
        return False


def password_ok(password: str) -> tuple[bool, str]:
    if len(password) < settings.min_password_length:
        return False, f"密码至少 {settings.min_password_length} 位"
    kinds = sum(
        1
        for probe in (str.islower, str.isupper, str.isdigit, lambda s: not s.isalnum())
        if any(probe(ch) for ch in password)
    )
    if kinds < 2:
        return False, "密码需包含字母、数字、符号中的至少两类"
    return True, ""


# --------------------------------------------------------------------------- #
# 会话令牌
# --------------------------------------------------------------------------- #
def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def utcnow() -> datetime:
    return datetime.utcnow()


def create_session(db: OrmSession, user: User, *, ip: str = "", ua: str = "") -> tuple[str, UserSession]:
    token = new_token()
    row = UserSession(
        user_id=user.id,
        token_hash=token_hash(token),
        created_at=utcnow(),
        expires_at=utcnow() + timedelta(hours=settings.session_ttl_hours),
        last_seen_at=utcnow(),
        ip=ip[:64],
        user_agent=ua[:200],
        revoked=False,
    )
    db.add(row)
    db.flush()
    return token, row


def session_from_token(db: OrmSession, token: str) -> tuple[UserSession, User] | None:
    if not token:
        return None
    row = db.execute(
        select(UserSession).where(UserSession.token_hash == token_hash(token))
    ).scalar_one_or_none()
    if row is None or row.revoked:
        return None
    if row.expires_at and row.expires_at < utcnow():
        return None
    user = db.get(User, row.user_id)
    if user is None or not user.enabled:
        return None
    return row, user


def revoke_session(db: OrmSession, row: UserSession) -> None:
    row.revoked = True


def revoke_all(db: OrmSession, user_id: int) -> int:
    rows = db.execute(
        select(UserSession).where(UserSession.user_id == user_id, UserSession.revoked.is_(False))
    ).scalars().all()
    for row in rows:
        row.revoked = True
    return len(rows)


# --------------------------------------------------------------------------- #
# 密钥（AI 供应商 api_key 等落库加密）
# --------------------------------------------------------------------------- #
def _secret_key() -> str:
    if settings.secret_key:
        return settings.secret_key
    path = Path(settings.db_path).parent / SECRET_FILE
    if path.exists():
        text = path.read_text(encoding="utf-8").strip()
        if text:
            return text
    key = secrets.token_urlsafe(48)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(key, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return key


def _fernet() -> Fernet:
    digest = hashlib.sha256(_secret_key().encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plain: str) -> str:
    if not plain:
        return ""
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_secret(blob: str) -> str:
    if not blob:
        return ""
    try:
        return _fernet().decrypt(blob.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""


def mask_secret(plain: str) -> str:
    if not plain:
        return ""
    if len(plain) <= 8:
        return "*" * len(plain)
    return plain[:4] + "*" * 6 + plain[-4:]


# --------------------------------------------------------------------------- #
# 审计
# --------------------------------------------------------------------------- #
def audit(
    db: OrmSession,
    *,
    actor: str = "anonymous",
    action: str,
    target: str = "",
    detail: dict[str, Any] | None = None,
    ip: str = "",
    ua: str = "",
    status: str = "ok",
) -> AuditLog:
    row = AuditLog(
        at=utcnow(),
        actor=actor[:64],
        action=action[:64],
        target=target[:128],
        detail=detail or {},
        ip=ip[:64],
        ua=ua[:200],
        status=status[:16],
    )
    db.add(row)
    return row


# --------------------------------------------------------------------------- #
# 登录限速（内存 + 库双保险）
# --------------------------------------------------------------------------- #
_fails: dict[str, tuple[int, float]] = {}


def _now() -> float:
    return datetime.utcnow().timestamp()


def register_failure(key: str) -> int:
    count, ts = _fails.get(key, (0, _now()))
    if _now() - ts > settings.login_lock_minutes * 60:
        count = 0
    count += 1
    _fails[key] = (count, _now())
    return count


def failure_count(key: str) -> int:
    count, ts = _fails.get(key, (0, 0.0))
    if _now() - ts > settings.login_lock_minutes * 60:
        return 0
    return count


def clear_failures(key: str) -> None:
    _fails.pop(key, None)

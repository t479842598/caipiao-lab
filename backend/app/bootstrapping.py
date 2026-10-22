"""首启引导：建默认管理员、迁移老库缺列、幂等补数据。"""

from __future__ import annotations

import logging
import secrets

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session as OrmSession

from .config import settings
from .db import get_engine
from .models import User
from .security import hash_password, password_ok, utcnow

logger = logging.getLogger("caipiao.bootstrap")


def ensure_columns() -> list[str]:
    """SQLite 老库补列（create_all 不会给已存在的表加字段）。"""
    engine = get_engine()
    inspector = inspect(engine)
    added: list[str] = []
    wanted: dict[str, list[tuple[str, str]]] = {
        "tickets": [
            ("owner_key", "VARCHAR(48) DEFAULT ''"),
        ],
    }
    with engine.begin() as conn:
        for table, cols in wanted.items():
            if not inspector.has_table(table):
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in cols:
                if name in existing:
                    continue
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
                added.append(f"{table}.{name}")
    if added:
        logger.info("schema patched: %s", ", ".join(added))
    return added


def ensure_admin(db: OrmSession) -> bool:
    """默认管理员不存在则创建。返回是否新建。

    `ADMIN_PASSWORD` 留空时自动生成 20 位随机密码并打印到日志——
    代码里不存任何可用默认口令，避免公开仓库泄露后台入口。
    生成后请立刻登录后台改密（或记进密码管理器）。
    """
    username = settings.admin_username.strip()
    if not username:
        return False
    exists = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if exists is not None:
        return False

    password = settings.admin_password
    generated = False
    if not password:
        # 排除易混淆字符（0/O、1/l/I），方便手抄
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%"
        password = "".join(secrets.choice(alphabet) for _ in range(20))
        generated = True

    ok, msg = password_ok(password)
    if not ok:
        logger.warning("默认管理员密码不合规（%s），已跳过创建，请手工建号", msg)
        return False

    db.add(
        User(
            username=username,
            password_hash=hash_password(password),
            display_name="管理员",
            role="admin",
            enabled=True,
            created_at=utcnow(),
            password_changed_at=utcnow(),
        )
    )
    db.flush()
    if generated:
        # 只在创建时打印一次，不落库、不打进后续日志
        logger.warning(
            "\n"
            "============================================================\n"
            "  已创建管理员账号（随机密码，仅显示这一次）\n"
            "  用户名: %s\n"
            "  密　码: %s\n"
            "  请立即登录 /login 修改密码\n"
            "============================================================",
            username,
            password,
        )
    else:
        logger.info("默认管理员 %s 已创建（密码取自 ADMIN_PASSWORD）", username)
    return True


def bootstrap_all(db: OrmSession) -> dict:
    return {"columns": ensure_columns(), "admin_created": ensure_admin(db)}

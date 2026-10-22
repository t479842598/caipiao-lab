"""首启引导：建默认管理员、迁移老库缺列、幂等补数据。"""

from __future__ import annotations

import logging

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
    """默认管理员不存在则创建。返回是否新建。"""
    username = settings.admin_username.strip()
    if not username:
        return False
    exists = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if exists is not None:
        return False
    ok, msg = password_ok(settings.admin_password)
    if not ok:
        logger.warning("默认管理员密码不合规（%s），已跳过创建，请手工建号", msg)
        return False
    db.add(
        User(
            username=username,
            password_hash=hash_password(settings.admin_password),
            display_name="管理员",
            role="admin",
            enabled=True,
            created_at=utcnow(),
            password_changed_at=utcnow(),
        )
    )
    db.flush()
    logger.info("默认管理员 %s 已创建", username)
    return True


def bootstrap_all(db: OrmSession) -> dict:
    return {"columns": ensure_columns(), "admin_created": ensure_admin(db)}

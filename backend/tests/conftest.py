"""pytest 公共夹具：临时 SQLite + 合成开奖数据 + TestClient。

不触碰真实 data/lottery.db，也不联网、不启调度器。
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from app import db as db_module
from app.config import settings
from app.games import GAMES
from app.models import Draw, DrawNumber, PrizeGrade


@pytest.fixture(scope="session")
def tmp_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("cpdb") / "test.db"


@pytest.fixture(scope="session", autouse=True)
def _configure(tmp_db: Path) -> Iterator[None]:
    """把全局配置指向临时库，并关掉调度器与鉴权。"""
    settings.db_path = str(tmp_db)
    settings.sync_enabled = False
    settings.read_only = False
    settings.admin_token = ""
    settings.admin_username = "admin"
    settings.admin_password = "TestAdmin!2345"
    settings.inbound_rate_per_min = 1_000_000
    settings.heavy_rate_per_min = 1_000_000
    settings.ai_max_calls_per_hour = 1_000
    settings.enable_docs = True
    db_module._engine = None
    db_module.SessionLocal = None
    db_module.init_db()
    seed_all()
    from app.bootstrapping import bootstrap_all

    with db_module.session_scope() as session:
        bootstrap_all(session)
    yield
    if db_module._engine is not None:
        db_module._engine.dispose()
    db_module._engine = None
    db_module.SessionLocal = None


def _make_draw(game: str, issue: str, day: date, rng: random.Random) -> Draw:
    spec = GAMES[game]
    if spec.code == "3d":
        digits = [str(rng.randint(0, 9)) for _ in range(3)]
        numbers = {"red": digits, "blue": []}
        ordered = digits
    else:
        red = [str(v) for v in sorted(rng.sample(range(spec.red.minimum, spec.red.maximum + 1), spec.red.count))]
        blue = []
        if spec.blue is not None:
            blue = [str(rng.randint(spec.blue.minimum, spec.blue.maximum))]
        numbers = {"red": red, "blue": blue}
        ordered = None
    return Draw(
        game_code=game,
        issue=issue,
        draw_date=day,
        week="",
        numbers=numbers,
        ordered=ordered,
        sales=1_000_000.0,
        pool_money=5_000_000.0,
        content="",
        source="test",
        raw={},
    )


def seed_all() -> None:
    """灌入 120 期合成数据（每彩种），期号形如 YYYY001..（跨年）。"""
    rng = random.Random(20261021)
    with db_module.session_scope() as session:
        for game in GAMES:
            day = date(2025, 9, 1)
            for i in range(1, 121):
                year = 2025 + (1 if i > 100 else 0)
                seq = i if i <= 100 else i - 100
                issue = f"{year}{seq:03d}"
                draw = _make_draw(game, issue, day, rng)
                session.add(draw)
                session.flush()
                for pos, value in enumerate((draw.numbers or {}).get("red") or []):
                    session.add(
                        DrawNumber(
                            draw_id=draw.id,
                            game_code=game,
                            ball="red",
                            position=pos,
                            value=int(value),
                            is_blue=False,
                        )
                    )
                for value in (draw.numbers or {}).get("blue") or []:
                    session.add(
                        DrawNumber(
                            draw_id=draw.id, game_code=game, ball="blue",
                            position=0, value=int(value), is_blue=True,
                        )
                    )
                session.add(
                    PrizeGrade(
                        draw_id=draw.id, type="一等奖", type_num=1, type_money=5_000_000.0
                    )
                )
                day += timedelta(days=2)


@pytest.fixture()
def session() -> Iterator:
    with db_module.session_scope() as s:
        yield s


@pytest.fixture()
def client() -> Iterator[TestClient]:
    from app.main import app

    with TestClient(app) as c:
        yield c
@pytest.fixture(scope="session")
def admin_creds() -> dict:
    return {"username": "admin", "password": "TestAdmin!2345"}


@pytest.fixture()
def admin(client, admin_creds) -> TestClient:
    """已登录的管理员客户端（带 CSRF 头）。"""
    r = client.post("/api/auth/login", json=admin_creds)
    assert r.status_code == 200, r.text
    client.headers.update({"x-csrf": "1"})
    return client


@pytest.fixture()
def guest(client) -> TestClient:
    """带设备号的游客客户端（票夹隔离所需）。"""
    client.headers.update({"X-Device-Id": "pytest-device-0001"})
    return client


@pytest.fixture()
def fresh_client() -> Iterator[TestClient]:
    """不带任何登录态 / 设备号的干净客户端。"""
    from app.main import app

    with TestClient(app) as c:
        yield c

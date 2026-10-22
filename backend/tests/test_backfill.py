"""深历史补录（backfill）离线测试：不联网，用假供应商验证插入语义。"""

from __future__ import annotations

import asyncio
from datetime import date

import pytest
from sqlalchemy import select

from app import db as db_module
from app.jobs.sync_job import sync_service
from app.models import Draw, DrawNumber
from app.providers.base import BaseProvider, RawDraw
from app.providers.c500 import C500Provider
from app.providers.registry import registry


class FakeBackfill(BaseProvider):
    code = "c500"
    name = "fake c500"
    supported_games = {"ssq", "3d", "qlc"}
    priority = 50
    backfill_capable = True
    rate_limit = 100.0

    def __init__(self, rows: list[RawDraw]) -> None:
        self.rows = rows
        self.calls = 0

    async def fetch_page(self, game: str, page: int = 1, size: int = 300):
        self.calls += 1
        start = (page - 1) * size
        pages = max(1, (len(self.rows) + size - 1) // size)
        return self.rows[start : start + size], pages


def _raw(issue: str, day: date, red: list[str], blue: list[str]) -> RawDraw:
    return RawDraw(
        game_code="ssq",
        issue=issue,
        draw_date=day,
        numbers={"red": red, "blue": blue},
        sales=1.0,
        pool_money=2.0,
        raw={"src": "fake"},
    )


def test_backfill_only_fills_missing(monkeypatch) -> None:
    with db_module.session_scope() as session:
        existing = session.execute(
            select(Draw).where(Draw.game_code == "ssq").order_by(Draw.issue)
        ).scalars().first()
    assert existing is not None
    keep_issue = existing.issue
    keep_date = existing.draw_date
    assert existing.source == "test"

    fake = FakeBackfill(
        [
            _raw("2003001", date(2003, 2, 23), ["10", "11", "12", "13", "26", "28"], ["11"]),
            _raw(keep_issue, date(1999, 1, 1), ["01", "02", "03", "04", "05", "06"], ["07"]),
        ]
    )
    monkeypatch.setitem(registry._providers, "c500", fake)

    result = asyncio.run(sync_service.sync_game("ssq", mode="backfill"))
    assert result["status"] == "success"
    assert result.get("inserted", 0) >= 1

    with db_module.session_scope() as session:
        early = session.execute(
            select(Draw).where(Draw.game_code == "ssq", Draw.issue == "2003001")
        ).scalar_one_or_none()
        assert early is not None
        assert early.source == "c500"
        nums = session.execute(
            select(DrawNumber).where(DrawNumber.draw_id == early.id)
        ).scalars().all()
        assert len(nums) == 7

        kept = session.execute(
            select(Draw).where(Draw.game_code == "ssq", Draw.issue == keep_issue)
        ).scalar_one()
        assert kept.source == "test"
        assert kept.draw_date == keep_date


def test_backfill_skips_games_without_deep_source(monkeypatch) -> None:
    monkeypatch.setitem(registry._providers, "c500", FakeBackfill([]))
    result = asyncio.run(sync_service.sync_game("kl8", mode="backfill"))
    assert result["status"] == "skipped"


def test_backfill_chain_excludes_official(monkeypatch) -> None:
    chain = sync_service._provider_chain("ssq", mode="backfill")
    assert chain and all(p.backfill_capable for p in chain)
    assert all(p.code != "cwl_official" for p in chain)


def test_c500_parse_row_columns() -> None:
    provider = C500Provider()
    row = "".join(
        [
            "<td>1</td><td>03001</td>",
            "<td>10</td><td>11</td><td>12</td><td>13</td><td>26</td><td>28</td><td>11</td>",
            "<td>0</td><td>5000000</td><td>3</td><td>2097070</td><td>12</td><td>100000</td>",
            "<td>10307806</td><td>2003-02-23</td>",
        ]
    )
    parsed = provider._parse_row("ssq", row)
    assert parsed is not None
    assert parsed.issue == "2003001"
    assert parsed.draw_date == date(2003, 2, 23)
    assert parsed.numbers["red"] == ["10", "11", "12", "13", "26", "28"]
    assert parsed.numbers["blue"] == ["11"]
    assert parsed.sales == 10307806.0
    assert parsed.pool_money == 5000000.0


@pytest.mark.parametrize(
    "game,row,expected_issue",
    [
        ("3d", "<td>1</td><td>2026279</td><td>7 9 1</td><td>18</td><td>96142502</td><td>2026-10-20</td>", "2026279"),
        ("qlc", "<td>1</td><td>26120</td><td>01 05 07 14 18 20 21 12</td><td>86</td><td>5835960</td><td>0</td><td>2026-10-19</td>", "2026120"),
    ],
)
def test_c500_parse_row_variants(game: str, row: str, expected_issue: str) -> None:
    provider = C500Provider()
    parsed = provider._parse_row(game, row)
    assert parsed is not None
    assert parsed.issue == expected_issue
    if game == "3d":
        assert parsed.ordered == ["7", "9", "1"]
        assert parsed.numbers["blue"] == []
    else:
        assert len(parsed.numbers["red"]) == 7
        assert parsed.numbers["blue"] == ["12"]

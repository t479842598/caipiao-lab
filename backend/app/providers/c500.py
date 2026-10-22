"""500.com 历史数据源（降级 / 交叉校验 / 深历史补录）。

实测（2026-10）端点与结构：
- ssq: https://datachart.500.com/ssq/history/newinc/history.php?start=03001&end=99999
        → 200, GB18030, 3517 行, 回溯到 2003-02-23
        cells: 序号 / 期号 / 6红 / 蓝 / 快乐星期天 / 一等奖注数 / 一等奖金额 / 二等奖注数 /
               二等奖金额 / 奖池 / 销售额 / 日期
- qlc: https://datachart.500.com/qlc/history/newinc/history.php?start=07001&end=99999
        → 200, 3000 行, 回溯到 2007-01-03；号码在同一格 "01 05 07 14 18 20 21 12"
- 3d:  https://datachart.500.com/sd/history/inc/history.php?limit=10000
        → 200, 7786 行, 回溯到 2004-10-18；cells[2] 形如 "2 0 3"（有序三位）
- kl8 在该站 404，不提供。

该源一次性返回全量历史，page 语义为本地切片，便于复用 start/full 同步流程。
"""

from __future__ import annotations

import asyncio
import re
import time
from datetime import date
from typing import Any

import httpx

from ..config import settings
from ..games import get_game
from .base import BaseProvider, ProviderError, ProviderHealth, RawDraw

SSQ_QLC_URL = "https://datachart.500.com/{path}/history/newinc/history.php?start={start}&end={end}"
SD_URL = "https://datachart.500.com/sd/history/inc/history.php?limit={limit}"
PATH_MAP = {"ssq": "ssq", "qlc": "qlc"}
START = {"ssq": "03001", "qlc": "07001"}
ROW_RE = re.compile(r'<tr[^>]*class="t_tr1"[^>]*>(.*?)</tr>', re.S)
ROW_RE_LOOSE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
TD_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
TAG_RE = re.compile(r"<[^>]+>")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
NUM_RE = re.compile(r"[^0-9.]")


def _money(cell: str) -> float | None:
    text = NUM_RE.sub("", cell.replace(",", ""))
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


class C500Provider(BaseProvider):
    code = "c500"
    name = "500.com 历史库"
    supported_games = {"ssq", "3d", "qlc"}
    priority = 50
    backfill_capable = True
    history_depth = "双色球 2003-02 起 / 七乐彩 2007-01 起 / 福彩3D 2004-10 起"
    rate_limit = 0.5

    def __init__(self) -> None:
        self._last_request = 0.0
        self._lock = asyncio.Lock()
        self._cache: dict[str, list[RawDraw]] = {}

    async def _throttle(self) -> None:
        async with self._lock:
            elapsed = time.monotonic() - self._last_request
            wait = (1.0 / max(self.rate_limit, 0.1)) - elapsed
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()

    async def fetch_page(self, game: str, page: int = 1, size: int = 300) -> tuple[list[RawDraw], int]:
        if not self.supports(game):
            raise ProviderError(f"{self.code} 不支持彩种 {game}")
        rows = await self._fetch_all(game)
        start = (page - 1) * size
        pages = max(1, (len(rows) + size - 1) // size)
        return rows[start : start + size], pages

    async def _fetch_all(self, game: str) -> list[RawDraw]:
        cached = self._cache.get(game)
        if cached is not None:
            return cached
        await self._throttle()
        if game in PATH_MAP:
            url = SSQ_QLC_URL.format(path=PATH_MAP[game], start=START[game], end="99999")
        elif game == "3d":
            url = SD_URL.format(limit=12000)
        else:
            raise ProviderError(f"{self.code} 不支持彩种 {game}")

        kwargs: dict[str, Any] = {
            "timeout": settings.request_timeout,
            "headers": {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                "Referer": "https://datachart.500.com/" + (PATH_MAP.get(game) or "sd") + "/history/",
            },
        }
        if settings.http_proxy:
            kwargs["proxy"] = settings.http_proxy
        async with httpx.AsyncClient(**kwargs) as client:
            resp = await client.get(url)
        if resp.status_code != 200:
            raise ProviderError(f"HTTP {resp.status_code}")
        html = resp.content.decode("gb18030", errors="ignore")
        rows = ROW_RE.findall(html) or [r for r in ROW_RE_LOOSE.findall(html) if DATE_RE.search(TAG_RE.sub("", r))]
        if not rows:
            raise ProviderError("页面结构变化，未匹配到数据行")
        out: list[RawDraw] = []
        for row in rows:
            parsed = self._parse_row(game, row)
            if parsed:
                out.append(parsed)
        if not out:
            raise ProviderError("数据行解析失败")
        self._cache[game] = out
        return out

    def _parse_row(self, game: str, row: str) -> RawDraw | None:
        cells = [TAG_RE.sub("", c).replace("&nbsp;", " ").strip() for c in TD_RE.findall(row)]
        if len(cells) < 4:
            return None
        spec = get_game(game)
        issue = cells[1].strip()
        if not issue.isdigit():
            return None

        draw_date: date | None = None
        for cell in reversed(cells):
            if DATE_RE.match(cell):
                draw_date = date.fromisoformat(cell)
                break
        if draw_date is None:
            return None

        if len(issue) == 5 and game != "3d":
            issue = "20" + issue  # 500.com 用 YYNNN 简写，官方口径是 20YYNNN

        numbers: dict[str, list[str]] = {"red": [], "blue": []}
        ordered: list[str] | None = None
        sales: float | None = None
        pool: float | None = None

        if game == "ssq":
            # 列序：序号/期号/6红/蓝/快乐星期天/奖池/一等奖注数/一等奖金额/
            #       二等奖注数/二等奖金额/总投注额/开奖日期
            if len(cells) < 9:
                return None
            numbers = {"red": [c.zfill(2) for c in cells[2:8]], "blue": [cells[8].zfill(2)]}
            if len(cells) >= 16:
                pool = _money(cells[10])
                sales = _money(cells[15])
        elif game == "qlc":
            # 列序：序号/期号/开奖号码/和值/销量/奖池/开奖日期
            tokens = cells[2].split()
            if len(tokens) < 8:
                return None
            numbers = {"red": [t.zfill(2) for t in tokens[:7]], "blue": [tokens[7].zfill(2)]}
            if len(cells) >= 6:
                sales = _money(cells[4])
                pool = _money(cells[5])
        elif game == "3d":
            digits = [t for t in cells[2].replace(",", " ").split() if t.isdigit()]
            if len(digits) != 3:
                joined = re.sub(r"[^0-9]", "", cells[2])
                if len(joined) != 3:
                    return None
                digits = list(joined)
            ordered = digits
            numbers = {"red": digits, "blue": []}
            if len(cells) >= 5:
                sales = _money(cells[4])
        else:
            return None

        if not spec.blue:
            numbers["blue"] = []

        return RawDraw(
            game_code=game,
            issue=issue,
            draw_date=draw_date,
            numbers=numbers,
            ordered=ordered,
            sales=sales,
            pool_money=pool,
            raw={"cells": cells},
        )

    async def health(self) -> ProviderHealth:
        started = time.monotonic()
        try:
            items, _ = await self.fetch_page("ssq", 1, 5)
            return ProviderHealth(self.code, bool(items), "ok" if items else "empty",
                                  int((time.monotonic() - started) * 1000))
        except Exception as exc:  # noqa: BLE001
            return ProviderHealth(self.code, False, str(exc), int((time.monotonic() - started) * 1000))

"""中国福利彩票官网数据源（主源，覆盖全部彩种与完整历史）。

实测要点（2026-10 验证）：
- endpoint: /cwl_admin/front/cwlkj/search/kjxx/findDrawNotice
- 必须携带 Referer: https://www.cwl.gov.cn/ ，否则 302 跳到 /404.html
- name 参数：ssq / 3d / qlc / kl8（注意 3D 是 "3d"，不是 fc3d）
- pageSize 上限 300，超过会被截断
- 3D 的 red 是 "7,9,1" 三位有序数字，必须字符串保留（否则 "0" 会丢）
"""

from __future__ import annotations

import asyncio
import re
import time
from datetime import date, datetime
from typing import Any

import httpx

from ..config import settings
from ..games import get_game
from .base import BaseProvider, ProviderError, ProviderHealth, RawDraw

BASE_URL = "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice"
DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


class CwlOfficialProvider(BaseProvider):
    code = "cwl_official"
    name = "福彩官方接口"
    supported_games = {"ssq", "3d", "qlc", "kl8"}
    priority = 10
    rate_limit = 1.0

    def __init__(self) -> None:
        self._last_request = 0.0
        self._lock = asyncio.Lock()

    def _client(self) -> httpx.AsyncClient:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Referer": "https://www.cwl.gov.cn/",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
        }
        kwargs: dict[str, Any] = {
            "timeout": settings.request_timeout,
            "headers": headers,
            "follow_redirects": False,
        }
        if settings.http_proxy:
            kwargs["proxy"] = settings.http_proxy
        return httpx.AsyncClient(**kwargs)

    async def _throttle(self) -> None:
        async with self._lock:
            elapsed = time.monotonic() - self._last_request
            wait = (1.0 / max(self.rate_limit, 0.1)) - elapsed
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()

    async def _request(self, params: dict[str, Any]) -> dict[str, Any]:
        await self._throttle()
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                async with self._client() as client:
                    resp = await client.get(BASE_URL, params=params)
                if resp.status_code != 200:
                    raise ProviderError(f"HTTP {resp.status_code}")
                text = resp.text.strip()
                if not text.startswith("{"):
                    raise ProviderError("响应不是 JSON（可能被重定向到错误页）")
                payload = resp.json()
                if payload.get("state") != 0:
                    raise ProviderError(f"接口返回 state={payload.get('state')} msg={payload.get('message')}")
                return payload
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                if attempt < 2:
                    await asyncio.sleep(1.0 * (3**attempt))
        raise ProviderError(f"cwl_official 请求失败: {last_err}")

    async def fetch_page(self, game: str, page: int = 1, size: int = 300) -> tuple[list[RawDraw], int]:
        if not self.supports(game):
            raise ProviderError(f"{self.code} 不支持彩种 {game}")
        size = min(size, 300)
        payload = await self._request(
            {"name": game, "pageNo": page, "pageSize": size, "systemType": "PC"}
        )
        rows = payload.get("result") or []
        total = payload.get("total")
        pages = payload.get("pageNum") or 1
        if total is None:  # issueCount 模式不返回 total，用返回条数推算
            pages = 1 if len(rows) < size else page + 1
        return [self._normalize(game, row) for row in rows], int(pages)

    async def fetch_all(self, game: str, size: int = 300) -> list[RawDraw]:
        first, pages = await self.fetch_page(game, 1, size)
        out = list(first)
        page = 1
        while page < pages:
            page += 1
            rows, _ = await self.fetch_page(game, page, size)
            if not rows:
                break
            out.extend(rows)
        return out

    def _normalize(self, game: str, row: dict[str, Any]) -> RawDraw:
        spec = get_game(game)
        issue = str(row.get("code") or "").strip()
        raw_date = str(row.get("date") or "")
        match = DATE_RE.match(raw_date)
        if not match:
            raise ProviderError(f"无法解析开奖日期: {raw_date!r}")
        draw_date = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))

        red_raw = [p.strip() for p in str(row.get("red") or "").split(",") if p.strip()]
        blue_raw = [p.strip() for p in str(row.get("blue") or "").split(",") if p.strip()]

        numbers: dict[str, list[str]] = {}
        ordered: list[str] | None = None
        if spec.code == "3d":
            # 有序三位，保留原始文本（含可能的 "0"）
            ordered = [p.zfill(1) for p in red_raw][:3]
            numbers = {"red": ordered, "blue": []}
        else:
            numbers = {"red": [p.zfill(spec.red.pad) for p in red_raw], "blue": [p.zfill(spec.blue.pad) for p in blue_raw] if spec.blue else []}

        prizes: list[dict[str, Any]] = []
        for grade in row.get("prizegrades") or []:
            num = grade.get("typenum")
            money = grade.get("typemoney")
            prizes.append(
                {
                    "type": str(grade.get("type") or ""),
                    "type_num": _to_int(num),
                    "type_money": _to_float(money),
                }
            )

        return RawDraw(
            game_code=spec.code,
            issue=issue,
            draw_date=draw_date,
            numbers=numbers,
            ordered=ordered,
            week=str(row.get("week") or ""),
            sales=_to_float(row.get("sales")),
            pool_money=_to_float(row.get("poolmoney")),
            content=str(row.get("content") or ""),
            prizes=prizes,
            raw=row,
        )

    async def health(self) -> ProviderHealth:
        started = time.monotonic()
        try:
            await self.fetch_page("ssq", 1, 1)
            return ProviderHealth(self.code, True, "ok", int((time.monotonic() - started) * 1000))
        except Exception as exc:  # noqa: BLE001
            return ProviderHealth(self.code, False, str(exc), int((time.monotonic() - started) * 1000))


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _to_int(value: Any) -> int | None:
    parsed = _to_float(value)
    return int(parsed) if parsed is not None else None

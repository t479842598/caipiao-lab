"""数据源抽象层。所有供应商输出统一的 RawDraw，归一化在各自实现里完成。"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import date
from typing import Any


class ProviderError(RuntimeError):
    """供应商不可用/响应异常。"""


@dataclass
class RawDraw:
    game_code: str
    issue: str
    draw_date: date
    numbers: dict[str, list[str]]  # {"red": [...], "blue": [...]}
    ordered: list[str] | None = None
    week: str = ""
    sales: float | None = None
    pool_money: float | None = None
    content: str = ""
    prizes: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderHealth:
    code: str
    healthy: bool
    message: str = ""
    latency_ms: int = 0


class BaseProvider(abc.ABC):
    code: str = "base"
    name: str = "Base"
    supported_games: set[str] = set()
    priority: int = 50
    rate_limit: float = 1.0  # 每秒请求数
    backfill_capable: bool = False  # 能否提供官方源之外的深历史
    history_depth: str = ""  # 人类可读的历史起点描述

    @abc.abstractmethod
    async def fetch_page(self, game: str, page: int = 1, size: int = 300) -> tuple[list[RawDraw], int]:
        """返回 (本页数据, 总页数)。"""

    async def fetch_latest(self, game: str, n: int = 30) -> list[RawDraw]:
        items, _ = await self.fetch_page(game, page=1, size=max(n, 1))
        return items[:n]

    async def health(self) -> ProviderHealth:  # pragma: no cover - 需要网络
        return ProviderHealth(code=self.code, healthy=True)

    def supports(self, game: str) -> bool:
        return game in self.supported_games

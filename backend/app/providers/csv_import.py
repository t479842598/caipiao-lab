"""CSV 离线导入源（断网/官方改版时的兜底）。

CSV 列：game,issue,date,red,blue[,ordered]
- red / blue 用空格或逗号分隔
- date 格式 YYYY-MM-DD
"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime

from ..games import get_game
from .base import BaseProvider, ProviderError, ProviderHealth, RawDraw


class CsvImportProvider(BaseProvider):
    code = "csv_import"
    name = "CSV 离线导入"
    supported_games = {"ssq", "3d", "qlc", "kl8"}
    priority = 90
    rate_limit = 0.0

    def __init__(self) -> None:
        self._buffer: list[RawDraw] = []

    def load_text(self, text: str) -> int:
        reader = csv.DictReader(io.StringIO(text))
        rows: list[RawDraw] = []
        for line, row in enumerate(reader, start=2):
            try:
                game = (row.get("game") or "").strip() or "ssq"
                spec = get_game(game)
                issue = str(row.get("issue") or "").strip()
                raw_date = str(row.get("date") or "").strip()
                draw_date = datetime.strptime(raw_date, "%Y-%m-%d").date() if raw_date else None
                if not issue or draw_date is None:
                    continue
                red = [t for t in (row.get("red") or "").replace(",", " ").split() if t]
                blue = [t for t in (row.get("blue") or "").replace(",", " ").split() if t]
                numbers = {"red": [t.zfill(spec.red.pad) for t in red],
                           "blue": [t.zfill(spec.blue.pad) for t in blue] if spec.blue else []}
                rows.append(RawDraw(game_code=game, issue=issue, draw_date=draw_date, numbers=numbers,
                                    raw={"line": line}))
            except (KeyError, ValueError):
                continue
        self._buffer = rows
        return len(rows)

    async def fetch_page(self, game: str, page: int = 1, size: int = 300) -> tuple[list[RawDraw], int]:
        items = [r for r in self._buffer if r.game_code == game]
        if not items:
            raise ProviderError("CSV 缓冲区为空，请先调用 load_text 导入")
        start = (page - 1) * size
        return items[start : start + size], max(1, (len(items) + size - 1) // size)

    async def health(self) -> ProviderHealth:
        return ProviderHealth(self.code, bool(self._buffer), f"{len(self._buffer)} 条已载入")

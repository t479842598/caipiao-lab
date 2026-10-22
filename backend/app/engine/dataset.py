"""把开奖记录加载成 numpy 矩阵，所有模型共用同一份数据视图。

关键约束（防未来函数）：任何预测/回测都通过 cut_issue 截断，只允许看到目标期之前的数据。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..games import GameSpec, get_game, issue_sort_key
from ..models import Draw


@dataclass
class BallData:
    game: str
    ball: str
    label: str
    domain: list[int]           # 号码全集
    issues: list[str]           # 按期升序
    dates: list[date]
    matrix: np.ndarray          # (n, D) int8，出现次数（无序彩种为 0/1）
    positions: int = 0          # >0 表示有序彩种（3D），matrix_pos 有意义
    matrix_pos: np.ndarray | None = None  # (n, positions, D) int8

    @property
    def n(self) -> int:
        return len(self.issues)

    @property
    def size(self) -> int:
        return len(self.domain)

    def slice_tail(self, window: int) -> "BallData":
        if window <= 0 or window >= self.n:
            return self
        return BallData(
            game=self.game,
            ball=self.ball,
            label=self.label,
            domain=self.domain,
            issues=self.issues[-window:],
            dates=self.dates[-window:],
            matrix=self.matrix[-window:],
            positions=self.positions,
            matrix_pos=None if self.matrix_pos is None else self.matrix_pos[-window:],
        )

    def cut_before(self, issue: str) -> "BallData":
        """返回只包含 issue 之前记录的子集。"""
        key = issue_sort_key(issue)
        idx = 0
        for i, it in enumerate(self.issues):
            if issue_sort_key(it) >= key:
                break
            idx = i + 1
        return BallData(
            game=self.game,
            ball=self.ball,
            label=self.label,
            domain=self.domain,
            issues=self.issues[:idx],
            dates=self.dates[:idx],
            matrix=self.matrix[:idx],
            positions=self.positions,
            matrix_pos=None if self.matrix_pos is None else self.matrix_pos[:idx],
        )

    def slice_tail_range(self, start: int, end: int) -> "BallData":
        """取 [start, end) 区间，用于训练时构造"截至某期"的历史视图。"""
        start = max(0, start)
        end = min(self.n, end)
        return BallData(
            game=self.game,
            ball=self.ball,
            label=self.label,
            domain=self.domain,
            issues=self.issues[start:end],
            dates=self.dates[start:end],
            matrix=self.matrix[start:end],
            positions=self.positions,
            matrix_pos=None if self.matrix_pos is None else self.matrix_pos[start:end],
        )

    def last_issue(self) -> str | None:
        return self.issues[-1] if self.issues else None


def load_ball_data(session: Session, game: str, ball: str) -> BallData:
    spec = get_game(game)
    spec_ball = spec.red if ball in ("red", "ordered") else spec.blue
    if spec_ball is None:
        raise KeyError(f"{game} 没有 {ball} 球")
    domain = list(range(spec_ball.minimum, spec_ball.maximum + 1))
    # 3D 用 'ordered' 语义，但对外统一叫 red
    db_ball = spec_ball.key
    rows = session.execute(
        select(Draw.issue, Draw.draw_date, Draw.numbers, Draw.ordered)
        .where(Draw.game_code == game)
        .order_by(Draw.draw_date, Draw.issue)
    ).all()

    issues: list[str] = []
    dates: list[date] = []
    records: list[list[int]] = []
    pos_records: list[list[list[int]]] = []

    for issue, draw_date, numbers, ordered in rows:
        raw = numbers or {}
        values: list[str]
        if spec_ball.ordered:
            values = list(ordered or raw.get(db_ball) or [])
        else:
            values = list(raw.get("blue") if ball == "blue" else raw.get("red") or [])
        try:
            nums = [int(v) for v in values]
        except (TypeError, ValueError):
            continue
        if ball in ("red", "ordered") and spec_ball.count and len(nums) < spec_ball.count:
            continue
        issues.append(issue)
        dates.append(draw_date)
        records.append(nums)
        if spec_ball.ordered:
            pos_records.append([[v] for v in nums])

    index = {v: i for i, v in enumerate(domain)}
    n = len(issues)
    matrix = np.zeros((n, len(domain)), dtype=np.int8)
    matrix_pos = None
    if spec_ball.ordered:
        positions = spec_ball.count
        matrix_pos = np.zeros((n, positions, len(domain)), dtype=np.int8)
        for row, nums in enumerate(records):
            for pos, value in enumerate(nums[:positions]):
                if value in index:
                    matrix_pos[row, pos, index[value]] = 1
            for value in nums[:positions]:
                if value in index:
                    matrix[row, index[value]] = 1
    else:
        for row, nums in enumerate(records):
            for value in nums:
                if value in index:
                    matrix[row, index[value]] = 1

    return BallData(
        game=game,
        ball=ball,
        label=spec_ball.label,
        domain=domain,
        issues=issues,
        dates=dates,
        matrix=matrix,
        positions=spec_ball.count if spec_ball.ordered else 0,
        matrix_pos=matrix_pos,
    )


def load_all(session: Session, game: str) -> dict[str, BallData]:
    spec: GameSpec = get_game(game)
    out: dict[str, BallData] = {}
    for ball_spec in spec.balls:
        key = "red" if ball_spec.key == "ordered" else ball_spec.key
        out[key] = load_ball_data(session, game, key)
    return out


def load_issue_index(session: Session, game: str) -> list[tuple[str, date]]:
    rows = session.execute(
        select(Draw.issue, Draw.draw_date).where(Draw.game_code == game).order_by(Draw.draw_date, Draw.issue)
    ).all()
    return [(r[0], r[1]) for r in rows]

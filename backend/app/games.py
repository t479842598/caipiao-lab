"""彩种规格 —— 全站唯一真相源。

号码一律以字符串保存：3D 的 "0" 若被转成 int 会丢失前导零语义。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BallSpec:
    key: str  # red / blue / ordered
    label: str
    count: int
    minimum: int
    maximum: int
    pad: int  # 展示补零宽度
    ordered: bool = False


@dataclass(frozen=True)
class GameSpec:
    code: str  # 官方接口 name 参数
    name: str
    short: str
    first_issue: str
    red: BallSpec
    blue: BallSpec | None = None
    draw_weekdays: tuple[int, ...] = ()  # 0=周一
    draw_time: str = "21:15"
    issue_per_year: bool = True
    extra: dict = field(default_factory=dict)

    @property
    def balls(self) -> list[BallSpec]:
        out = [self.red]
        if self.blue:
            out.append(self.blue)
        return out

    def domain(self, ball: str) -> range:
        spec = self.red if ball in ("red", "ordered") else self.blue
        if spec is None:
            return range(0)
        return range(spec.minimum, spec.maximum + 1)


SSQ = GameSpec(
    code="ssq",
    name="双色球",
    short="SSQ",
    first_issue="2003001",
    red=BallSpec("red", "红球", 6, 1, 33, 2),
    blue=BallSpec("blue", "蓝球", 1, 1, 16, 2),
    draw_weekdays=(1, 3, 6),  # 二 / 四 / 日
    draw_time="21:15",
)

SD = GameSpec(
    code="3d",
    name="福彩3D",
    short="3D",
    first_issue="2003001",
    red=BallSpec("ordered", "开奖号", 3, 0, 9, 0, ordered=True),
    draw_weekdays=(0, 1, 2, 3, 4, 5, 6),
    draw_time="21:15",
)

QLC = GameSpec(
    code="qlc",
    name="七乐彩",
    short="QLC",
    first_issue="2007001",
    red=BallSpec("red", "基本号", 7, 1, 30, 2),
    blue=BallSpec("blue", "特别号", 1, 1, 30, 2),
    draw_weekdays=(0, 2, 4),  # 一 / 三 / 五
    draw_time="21:15",
)

KL8 = GameSpec(
    code="kl8",
    name="快乐8",
    short="KL8",
    first_issue="2020001",
    red=BallSpec("red", "开奖号", 20, 1, 80, 2),
    draw_weekdays=(0, 1, 2, 3, 4, 5, 6),
    draw_time="21:30",
)

GAMES: dict[str, GameSpec] = {g.code: g for g in (SSQ, SD, QLC, KL8)}

# 展示顺序
GAME_ORDER = ("ssq", "3d", "qlc", "kl8")

WEEKDAY_CN = ("一", "二", "三", "四", "五", "六", "日")


def get_game(code: str) -> GameSpec:
    if code not in GAMES:
        raise KeyError(code)
    return GAMES[code]


def issue_sort_key(issue: str) -> tuple[int, int]:
    """期号排序键：先年份后序号，避免跨年后纯字符串比较出错。"""
    text = str(issue)
    if len(text) >= 7:
        return int(text[:-3]), int(text[-3:])
    return 0, int(text)


def next_issue_guess(last_issue: str | None, last_date_year: int | None, today_year: int) -> str:
    """推算下期期号（官方未开奖前用于展示）。"""
    if not last_issue:
        return "待定"
    year, seq = issue_sort_key(last_issue)
    if last_date_year and today_year > last_date_year:
        return f"{today_year}001"
    return f"{year}{seq + 1:03d}"


def format_number(value: int | str, spec: BallSpec) -> str:
    if spec.ordered:
        return str(value)
    return str(int(value)).zfill(spec.pad)

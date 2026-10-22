"""兑奖规则测试：4 彩种全档位覆盖。

历史背景：这里长期零测试，导致快乐8 奖金恒为 0、3D 组选恒为 0 两个 bug 潜伏。
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.engine.settle import settle_ticket


def make_draw(game: str, red: list[str], blue: list[str] | None = None,
              ordered: list[str] | None = None, prizes: list[tuple[str, float]] | None = None):
    """构造一个只带兑奖所需字段的轻量 draw（不落库）。"""
    return SimpleNamespace(
        game_code=game,
        issue="2026121",
        draw_date=date(2026, 10, 20),
        numbers={"red": red, "blue": blue or []},
        ordered=ordered,
        prizes=[SimpleNamespace(type=t, type_money=m) for t, m in (prizes or [])],
    )


# --------------------------------------------------------------------------- #
# 双色球
# --------------------------------------------------------------------------- #
class TestSSQ:
    def test_first_prize_uses_official_money(self):
        draw = make_draw("ssq", ["01", "02", "03", "04", "05", "06"], ["07"],
                         prizes=[("1", 7_232_345.0)])
        r = settle_ticket("ssq", {"red": ["01", "02", "03", "04", "05", "06"], "blue": ["07"]}, draw)
        assert r["hit"] == 6
        assert r["blue_hit"] == 1
        assert r["grade"] == "1"
        assert r["prize"] == 7_232_345.0

    def test_second_prize_six_red_no_blue(self):
        draw = make_draw("ssq", ["01", "02", "03", "04", "05", "06"], ["07"],
                         prizes=[("2", 344_025.0)])
        r = settle_ticket("ssq", {"red": ["01", "02", "03", "04", "05", "06"], "blue": ["08"]}, draw)
        assert r["grade"] == "2"
        assert r["prize"] == 344_025.0

    def test_third_prize_five_plus_blue(self):
        draw = make_draw("ssq", ["01", "02", "03", "04", "05", "06"], ["07"],
                         prizes=[("3", 3000.0)])
        r = settle_ticket("ssq", {"red": ["01", "02", "03", "04", "05", "33"], "blue": ["07"]}, draw)
        assert r["grade"] == "3"
        assert r["prize"] == 3000.0

    def test_fourth_prize_five_red_or_four_plus_blue(self):
        draw = make_draw("ssq", ["01", "02", "03", "04", "05", "06"], ["07"],
                         prizes=[("4", 200.0)])
        r1 = settle_ticket("ssq", {"red": ["01", "02", "03", "04", "05", "33"], "blue": ["08"]}, draw)
        assert r1["grade"] == "4"
        assert r1["prize"] == 200.0
        r2 = settle_ticket("ssq", {"red": ["01", "02", "03", "04", "33", "32"], "blue": ["07"]}, draw)
        assert r2["grade"] == "4"
        assert r2["prize"] == 200.0

    def test_fifth_prize(self):
        draw = make_draw("ssq", ["01", "02", "03", "04", "05", "06"], ["07"],
                         prizes=[("5", 10.0)])
        r = settle_ticket("ssq", {"red": ["01", "02", "03", "04", "33", "32"], "blue": ["08"]}, draw)
        assert r["grade"] == "5"
        assert r["prize"] == 10.0

    def test_sixth_prize_blue_only(self):
        draw = make_draw("ssq", ["01", "02", "03", "04", "05", "06"], ["07"],
                         prizes=[("6", 5.0)])
        r = settle_ticket("ssq", {"red": ["11", "12", "13", "14", "15", "16"], "blue": ["07"]}, draw)
        assert r["grade"] == "6"
        assert r["prize"] == 5.0

    def test_no_prize(self):
        draw = make_draw("ssq", ["01", "02", "03", "04", "05", "06"], ["07"],
                         prizes=[("1", 5_000_000.0)])
        r = settle_ticket("ssq", {"red": ["11", "12", "13", "14", "15", "16"], "blue": ["08"]}, draw)
        assert r["grade"] is None
        assert r["prize"] == 0.0

    def test_falls_back_when_official_data_missing(self):
        """官方奖级缺失时用内置兜底，不能算成 0。"""
        draw = make_draw("ssq", ["01", "02", "03", "04", "05", "06"], ["07"])
        r = settle_ticket("ssq", {"red": ["11", "12", "13", "14", "15", "16"], "blue": ["07"]}, draw)
        assert r["grade"] == "6"
        assert r["prize"] == 5.0  # 六等奖固定 5 元


# --------------------------------------------------------------------------- #
# 七乐彩
# --------------------------------------------------------------------------- #
class TestQLC:
    def test_first_prize_seven_basic(self):
        draw = make_draw("qlc", ["01", "02", "03", "04", "05", "06", "07"], ["08"],
                         prizes=[("1", 4_177_273.0)])
        r = settle_ticket("qlc", {"red": ["01", "02", "03", "04", "05", "06", "07"], "blue": []}, draw)
        assert r["grade"] == "1"
        assert r["prize"] == 4_177_273.0

    def test_second_prize_six_plus_special(self):
        draw = make_draw("qlc", ["01", "02", "03", "04", "05", "06", "07"], ["08"],
                         prizes=[("2", 52_516.0)])
        r = settle_ticket("qlc", {"red": ["01", "02", "03", "04", "05", "06", "30"], "blue": ["08"]}, draw)
        assert r["grade"] == "2"
        assert r["prize"] == 52_516.0

    def test_seventh_prize_four_basic(self):
        draw = make_draw("qlc", ["01", "02", "03", "04", "05", "06", "07"], ["08"],
                         prizes=[("7", 5.0)])
        r = settle_ticket("qlc", {"red": ["01", "02", "03", "04", "28", "29", "30"], "blue": []}, draw)
        assert r["grade"] == "7"
        assert r["prize"] == 5.0


# --------------------------------------------------------------------------- #
# 3D —— 三种玩法
# --------------------------------------------------------------------------- #
class TestSD:
    def test_direct_hit_1040(self):
        draw = make_draw("3d", ["7", "9", "1"], ordered=["7", "9", "1"])
        r = settle_ticket("3d", {"red": ["7", "9", "1"], "ordered": ["7", "9", "1"]}, draw)
        assert r["kind"] == "direct"
        assert r["prize"] == 1040.0

    def test_group6_when_three_distinct(self):
        """开奖 7-9-1 三位互不相同，买 1-7-9 是组六。"""
        draw = make_draw("3d", ["7", "9", "1"], ordered=["7", "9", "1"])
        r = settle_ticket("3d", {"red": ["1", "7", "9"], "ordered": ["1", "7", "9"]}, draw)
        assert r["kind"] == "group6"
        assert r["prize"] == 173.0

    def test_group3_when_one_pair(self):
        """开奖 5-5-8 有且仅有一对相同，买 5-8-5 是组三。"""
        draw = make_draw("3d", ["5", "5", "8"], ordered=["5", "5", "8"])
        r = settle_ticket("3d", {"red": ["5", "8", "5"], "ordered": ["5", "8", "5"]}, draw)
        assert r["kind"] == "group3"
        assert r["prize"] == 346.0

    def test_triple_leopard_group_not_prized(self):
        """豹子号 555：只有直选能中，组选不设奖。"""
        draw = make_draw("3d", ["5", "5", "5"], ordered=["5", "5", "5"])
        r = settle_ticket("3d", {"red": ["5", "5", "5"], "ordered": ["5", "5", "5"]}, draw)
        assert r["kind"] == "direct"
        assert r["prize"] == 1040.0

    def test_miss_returns_zero(self):
        draw = make_draw("3d", ["7", "9", "1"], ordered=["7", "9", "1"])
        r = settle_ticket("3d", {"red": ["1", "2", "3"], "ordered": ["1", "2", "3"]}, draw)
        assert r["kind"] == "none"
        assert r["prize"] == 0.0

    def test_falls_back_to_numbers_red_when_no_ordered(self):
        """老数据可能只有 numbers.red，没有 ordered 字段。"""
        draw = make_draw("3d", ["7", "9", "1"], ordered=None)
        r = settle_ticket("3d", {"red": ["7", "9", "1"]}, draw)
        assert r["kind"] == "direct"
        assert r["prize"] == 1040.0


# --------------------------------------------------------------------------- #
# 快乐8 —— 从官方奖级反查
# --------------------------------------------------------------------------- #
class TestKL8:
    def test_pick10_hit10_uses_official_5m(self):
        draw = make_draw("kl8", [str(i).zfill(2) for i in range(1, 21)],
                         prizes=[("x10z10", 5_000_000.0)])
        picked = [str(i).zfill(2) for i in range(1, 11)]
        r = settle_ticket("kl8", {"red": picked}, draw)
        assert r["hit"] == 10
        assert r["kind"] == "x10z10"
        assert r["prize"] == 5_000_000.0

    def test_pick10_hit6_uses_official_5yuan(self):
        draw = make_draw("kl8", [str(i).zfill(2) for i in range(1, 21)],
                         prizes=[("x10z6", 5.0)])
        picked = [str(i).zfill(2) for i in range(1, 7)] + ["71", "72", "73", "74"]
        r = settle_ticket("kl8", {"red": picked}, draw)
        assert r["hit"] == 6
        assert r["kind"] == "x10z6"
        assert r["prize"] == 5.0

    def test_pick9_uses_x9z_prefix(self):
        draw = make_draw("kl8", [str(i).zfill(2) for i in range(1, 21)],
                         prizes=[("x9z9", 250_000.0)])
        picked = [str(i).zfill(2) for i in range(1, 10)]
        r = settle_ticket("kl8", {"red": picked}, draw)
        assert r["hit"] == 9
        assert r["kind"] == "x9z9"
        assert r["prize"] == 250_000.0

    def test_miss_returns_zero(self):
        draw = make_draw("kl8", [str(i).zfill(2) for i in range(1, 21)],
                         prizes=[("x10z10", 5_000_000.0)])
        picked = [str(i).zfill(2) for i in range(71, 81)]
        r = settle_ticket("kl8", {"red": picked}, draw)
        assert r["hit"] == 0
        assert r["prize"] == 0.0

    def test_fallback_when_no_official_data(self):
        """官方奖级缺失时，选十玩法按内置表兜底。"""
        draw = make_draw("kl8", [str(i).zfill(2) for i in range(1, 21)])
        picked = [str(i).zfill(2) for i in range(1, 11)]
        r = settle_ticket("kl8", {"red": picked}, draw)
        assert r["prize"] == 5_000_000.0


# --------------------------------------------------------------------------- #
# 边界
# --------------------------------------------------------------------------- #
def test_unknown_game_returns_zero():
    draw = make_draw("unknown", ["01"], prizes=[])
    r = settle_ticket("unknown", {"red": ["01"]}, draw)
    assert r["prize"] == 0.0


def test_empty_numbers_does_not_crash():
    draw = make_draw("ssq", ["01", "02", "03", "04", "05", "06"], ["07"])
    r = settle_ticket("ssq", {}, draw)
    assert r["hit"] == 0
    assert r["prize"] == 0.0

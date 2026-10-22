from __future__ import annotations

import pytest

from app.games import GAMES, GAME_ORDER, format_number, get_game, issue_sort_key, next_issue_guess


def test_four_games_registered() -> None:
    assert GAME_ORDER == ("ssq", "3d", "qlc", "kl8")
    assert set(GAMES) == {"ssq", "3d", "qlc", "kl8"}


def test_ssq_domain() -> None:
    spec = get_game("ssq")
    assert spec.red.count == 6
    assert list(spec.domain("red")) == list(range(1, 34))
    assert list(spec.domain("blue")) == list(range(1, 17))


def test_3d_is_ordered_and_keeps_zero() -> None:
    spec = get_game("3d")
    assert spec.red.ordered is True
    assert spec.red.pad == 0
    assert format_number(0, spec.red) == "0"
    assert format_number(7, spec.red) == "7"


def test_kl8_domain() -> None:
    assert list(get_game("kl8").domain("red")) == list(range(1, 81))


def test_unknown_game_raises() -> None:
    with pytest.raises(KeyError):
        get_game("fc3d")


@pytest.mark.parametrize(
    "a,b",
    [("2026120", "2026121"), ("2025999", "2026001"), ("2026110", "2026120")],
)
def test_issue_sort_key_ordering(a: str, b: str) -> None:
    assert issue_sort_key(a) < issue_sort_key(b)


def test_next_issue_guess_same_year() -> None:
    assert next_issue_guess("2026119", 2026, 2026) == "2026120"


def test_next_issue_guess_rolls_year() -> None:
    assert next_issue_guess("2025155", 2025, 2026) == "2026001"

from __future__ import annotations

import pytest

from app.engine.dataset import load_ball_data
from app.engine.generator import build_tickets, describe_structure
from app.engine.models import compute_marginals
from app.games import get_game


def test_ssq_ticket_shape(session) -> None:
    data = load_ball_data(session, "ssq", "red")
    probs, _ = compute_marginals(data, engine="frequency", window=50)
    spec = get_game("ssq")
    tickets = build_tickets(data, probs, spec, count=5, seed=42)
    assert len(tickets) == 5
    for t in tickets:
        red = t["numbers"]["red"]
        assert len(red) == 6
        assert len(set(red)) == 6
        assert all(1 <= int(v) <= 33 for v in red)
        assert red == sorted(red)
        assert len(t["numbers"]["blue"]) == 1


def test_tickets_are_deduplicated(session) -> None:
    data = load_ball_data(session, "ssq", "red")
    probs, _ = compute_marginals(data, engine="uniform")
    tickets = build_tickets(data, probs, get_game("ssq"), count=8, seed=7)
    keys = {tuple(t["numbers"]["red"]) for t in tickets}
    assert len(keys) == len(tickets)


def test_same_seed_same_tickets(session) -> None:
    data = load_ball_data(session, "ssq", "red")
    probs, _ = compute_marginals(data, engine="frequency", window=50)
    a = build_tickets(data, probs, get_game("ssq"), count=3, seed=123)
    b = build_tickets(data, probs, get_game("ssq"), count=3, seed=123)
    assert [t["numbers"] for t in a] == [t["numbers"] for t in b]


def test_3d_tickets_are_three_digits(session) -> None:
    data = load_ball_data(session, "3d", "red")
    probs, _ = compute_marginals(data, engine="frequency", window=50)
    tickets = build_tickets(data, probs, get_game("3d"), count=4, seed=9)
    assert len(tickets) == 4
    for t in tickets:
        ordered = t["numbers"]["ordered"]
        assert len(ordered) == 3
        assert all(v.isdigit() for v in ordered)


def test_kl8_pick_overrides_size(session) -> None:
    data = load_ball_data(session, "kl8", "red")
    probs, _ = compute_marginals(data, engine="frequency", window=50)
    tickets = build_tickets(data, probs, get_game("kl8"), count=2, seed=3, pick=7)
    for t in tickets:
        assert len(t["numbers"]["red"]) == 7


@pytest.mark.parametrize("strategy", ["balanced", "hot", "cold", "mixed", "random"])
def test_all_strategies_produce_valid_output(session, strategy: str) -> None:
    data = load_ball_data(session, "ssq", "red")
    probs, _ = compute_marginals(data, engine="frequency", window=50)
    tickets = build_tickets(data, probs, get_game("ssq"), count=2, seed=5, strategy=strategy)
    assert len(tickets) == 2
    assert all(len(t["numbers"]["red"]) == 6 for t in tickets)


def test_describe_structure_fields() -> None:
    out = describe_structure([1, 2, 3, 10, 20, 33], get_game("ssq"))
    assert out["sum"] == 69
    assert out["span"] == 32
    assert ":" in out["odd_even"]
    assert out["consecutive"] >= 2

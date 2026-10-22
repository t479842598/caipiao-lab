from __future__ import annotations

import numpy as np

from app.engine.dataset import load_ball_data
from app.engine.stats import (
    distribution_stats,
    frequency_table,
    omission_table,
    randomness_report,
    trend_matrix,
)


def test_frequency_table_sums_to_draws_times_k(session) -> None:
    data = load_ball_data(session, "ssq", "red")
    items = frequency_table(data, window=100)
    assert len(items) == 33
    assert sum(i["count"] for i in items) == min(data.n, 100) * 6


def test_frequency_expected_matches_window(session) -> None:
    data = load_ball_data(session, "ssq", "red")
    items = frequency_table(data, window=100)
    assert all(abs(i["expected"] - 100 * 6 / 33) < 0.01 for i in items)


def test_omission_current_bounds(session) -> None:
    data = load_ball_data(session, "ssq", "red")
    items = omission_table(data)
    assert len(items) == 33
    assert all(i["current"] >= 0 and i["max"] >= i["current"] for i in items)


def test_omission_limit_sorted_desc(session) -> None:
    data = load_ball_data(session, "ssq", "red")
    items = omission_table(data, limit=5)
    assert len(items) == 5
    cur = [i["current"] for i in items]
    assert cur == sorted(cur, reverse=True)


def test_trend_matrix_shape(session) -> None:
    data = load_ball_data(session, "ssq", "red")
    out = trend_matrix(data, periods=30)
    assert len(out["matrix"]) == 30
    assert len(out["matrix"][0]) == 33
    assert len(out["issues"]) == 30


def test_distribution_stats(session) -> None:
    data = load_ball_data(session, "ssq", "red")
    out = distribution_stats(data, window=50)
    assert out["window"] == 50
    assert out["stats"]["draws"] == 50
    assert out["sum_hist"]
    assert out["stats"]["sum"]["min"] <= out["stats"]["sum"]["mean"] <= out["stats"]["sum"]["max"]


def test_randomness_report_fields(session) -> None:
    data = load_ball_data(session, "ssq", "red")
    out = randomness_report(data)
    assert 0.0 <= out["chi_square"]["p_value"] <= 1.0
    assert out["chi_square"]["dof"] == 32
    assert isinstance(out["verdict"], str) and out["verdict"]


def test_3d_data_preserves_positions(session) -> None:
    data = load_ball_data(session, "3d", "red")
    assert data.positions == 3
    assert data.matrix_pos is not None
    assert data.matrix_pos.shape[1] == 3
    # 三位都是 0-9
    assert data.size == 10


def test_dataset_cut_before_excludes_target(session) -> None:
    data = load_ball_data(session, "ssq", "red")
    target = data.issues[-1]
    cut = data.cut_before(target)
    assert target not in cut.issues
    assert cut.n == data.n - 1


def test_matrix_rows_are_binary(session) -> None:
    data = load_ball_data(session, "kl8", "red")
    assert set(np.unique(data.matrix).tolist()) <= {0, 1}
    assert data.matrix.sum(axis=1).max() <= 20

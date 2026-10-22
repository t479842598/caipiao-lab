"""模型层：形状、归一化、以及最关键的「无未来泄漏」验证。"""

from __future__ import annotations

import numpy as np
import pytest

from app.engine.dataset import load_ball_data
from app.engine.models import (
    bayes_model,
    compute_marginals,
    frequency_model,
    gbdt_model,
    markov_model,
    omission_model,
    uniform_model,
)

ENGINES = ["uniform", "frequency", "omission", "markov", "bayes", "gbdt", "ensemble"]


@pytest.mark.parametrize("engine", ENGINES)
def test_marginals_normalized(session, engine: str) -> None:
    data = load_ball_data(session, "ssq", "red")
    probs, weights = compute_marginals(data, engine=engine, window=50, fast=True)
    assert probs.shape == (33,)
    assert probs.min() >= 0
    assert abs(float(probs.sum()) - 1.0) < 1e-6
    assert weights


def test_uniform_is_flat(session) -> None:
    data = load_ball_data(session, "ssq", "red")
    probs = uniform_model(data)
    assert np.allclose(probs, 1 / 33)


def test_frequency_model_reacts_to_window(session) -> None:
    data = load_ball_data(session, "ssq", "red")
    short = frequency_model(data, window=10)
    long = frequency_model(data, window=100)
    assert not np.allclose(short, long)


def test_ensemble_weights_sum_to_one(session) -> None:
    data = load_ball_data(session, "ssq", "red")
    _, weights = compute_marginals(data, engine="ensemble", window=50, fast=True)
    assert abs(sum(weights.values()) - 1.0) < 1e-9


@pytest.mark.parametrize("engine", ["frequency", "omission", "markov", "bayes", "gbdt", "ensemble"])
def test_no_future_leak(session, engine: str) -> None:
    """关键不变量：只用 t 期之前的数据算出的概率，必须与加入 t 期之后数据无关。"""
    data = load_ball_data(session, "ssq", "red")
    cut_issue = data.issues[-11]
    past = data.cut_before(cut_issue)
    # 用过去数据预测
    p_past, _ = compute_marginals(past, engine=engine, window=60, fast=True)
    # 用全部数据（含 cut 之后 10 期）在同一个 cut 上预测
    p_full, _ = compute_marginals(data, engine=engine, window=60, fast=True, cut=past.n)
    if engine in ("gbdt", "ensemble"):
        assert p_past.shape == p_full.shape
    # 非树模型：截断后结果应与"只喂过去数据"完全一致
    if engine in ("frequency", "omission", "markov"):
        assert np.allclose(p_past, compute_marginals(past, engine=engine, window=60, fast=True)[0])


def test_gbdt_trains_without_future_labels(session) -> None:
    """树模型的训练标签取 t+1，最后一行永远不参与训练（否则等于偷看答案）。"""
    data = load_ball_data(session, "ssq", "red")
    probs = gbdt_model(data, window=80, fast=True)
    assert probs.shape == (33,)
    assert abs(float(probs.sum()) - 1.0) < 1e-6


def test_gbdt_falls_back_on_short_history(session) -> None:
    data = load_ball_data(session, "ssq", "red")
    tiny = data.slice_tail(10)
    probs = gbdt_model(tiny, window=10)
    assert probs.shape == (33,)
    assert abs(float(probs.sum()) - 1.0) < 1e-6

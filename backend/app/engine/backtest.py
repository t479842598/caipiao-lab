"""回测：滚动预测未来期，模型 vs 均匀基线，用严苛指标判定"到底有没有用"。

指标：
- avg_hits   ：平均命中号码数（top-K 集合对开奖集合的重合数）
- hit@topk   ：命中率@topK
- log_loss   ：边际概率对实际开奖的交叉熵（越低越好）
- brier      ：Brier 分数
口径：每期只用该期之前的数据训练，绝不看未来。
"""

from __future__ import annotations

from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from ..games import get_game
from .dataset import BallData, load_ball_data
from .models import compute_marginals


def _ticket_hits(probs: np.ndarray, actual: np.ndarray, k: int, rng: np.random.Generator) -> float:
    top = np.argsort(-probs)[:k]
    hit = float(actual[top].sum())
    return hit


def _sample_ticket_hits(probs: np.ndarray, actual: np.ndarray, k: int, rng: np.random.Generator) -> float:
    """按概率实际抽一注，看命中几个——更贴近真实购彩。"""
    p = np.clip(probs, 1e-12, None)
    p = p / p.sum()
    picks = rng.choice(len(p), size=min(k, len(p)), replace=False, p=p)
    return float(actual[picks].sum())


def _scores(probs: np.ndarray, actual: np.ndarray) -> tuple[float, float]:
    p = np.clip(probs, 1e-9, 1.0)
    p = p / p.sum()
    log_loss = float(-np.mean(actual * np.log(p) + (1 - actual) * np.log(1 - p)))
    brier = float(np.mean((p - actual) ** 2))
    return log_loss, brier


TREE_ENGINES = {"gbdt", "ensemble"}


def run_backtest(
    session: Session,
    game: str,
    periods: int = 200,
    engine: str = "ensemble",
    window: int = 100,
    topk: int = 6,
    stride: int = 5,
) -> dict[str, Any]:
    spec = get_game(game)
    data = load_ball_data(session, game, "red")
    if data.n < 40:
        raise ValueError(f"{spec.name} 数据不足（{data.n} 期），至少需要 40 期")

    k = topk if game != "kl8" else min(topk, 20)
    n = data.n
    start = max(30, n - periods)
    rng = np.random.default_rng(20240501)

    model_hits: list[float] = []
    base_hits: list[float] = []
    model_ticket: list[float] = []
    base_ticket: list[float] = []
    model_ll: list[float] = []
    base_ll: list[float] = []
    model_br: list[float] = []
    base_br: list[float] = []
    per_issue: list[dict[str, Any]] = []

    cached: np.ndarray | None = None
    step = max(1, stride) if engine in TREE_ENGINES else 1
    for idx, t in enumerate(range(start, n - 1)):
        train = data.slice_tail_range(0, t + 1)
        actual = (data.matrix[t + 1] > 0).astype(np.float64)
        if actual.sum() == 0:
            continue
        # 树模型训练贵，按 stride 重训；缓存的模型只见过 t 之前的数据，无未来泄漏
        if step > 1 and cached is not None and idx % step != 0:
            probs = cached
        else:
            try:
                probs, _ = compute_marginals(train, engine=engine, window=window, fast=True)
            except Exception:  # noqa: BLE001
                probs = np.full(data.size, 1.0 / data.size)
            cached = probs
        base = np.full(data.size, actual.sum() / data.size)

        mh = _ticket_hits(probs, actual, k, rng)
        bh = _ticket_hits(base, actual, k, rng)
        model_hits.append(mh)
        base_hits.append(bh)
        model_ticket.append(_sample_ticket_hits(probs, actual, k, rng))
        base_ticket.append(_sample_ticket_hits(base, actual, k, rng))
        mll, mbr = _scores(probs, actual)
        bll, bbr = _scores(base, actual)
        model_ll.append(mll)
        base_ll.append(bll)
        model_br.append(mbr)
        base_br.append(bbr)
        per_issue.append(
            {
                "issue": data.issues[t + 1],
                "model_hits": int(mh),
                "baseline_hits": int(bh),
                "k": k,
                "actual": [int(v) for v in actual.nonzero()[0]][:30],
            }
        )

    if not model_hits:
        raise ValueError("回测区间内没有可评估的期次")

    avg_model = float(np.mean(model_hits))
    avg_base = float(np.mean(base_hits))
    lift_hits = avg_model / avg_base if avg_base else 1.0
    ll_model = float(np.mean(model_ll))
    ll_base = float(np.mean(base_ll))
    lift_ll = ll_base / ll_model if ll_model else 1.0

    histogram: dict[str, int] = {}
    for h in model_hits:
        key = str(int(h))
        histogram[key] = histogram.get(key, 0) + 1

    verdict = _verdict(lift_hits, lift_ll, len(model_hits))

    return {
        "game": game,
        "engine": engine,
        "periods": len(model_hits),
        "window": window,
        "topk": k,
        "stride": step,
        "model": {
            "label": "模型",
            "avg_hits": round(avg_model, 4),
            "hit_rate_at_topk": round(avg_model / k, 4),
            "log_loss": round(ll_model, 6),
            "brier": round(float(np.mean(model_br)), 6),
            "avg_ticket_hits": round(float(np.mean(model_ticket)), 4),
        },
        "baseline": {
            "label": "均匀基线",
            "avg_hits": round(avg_base, 4),
            "hit_rate_at_topk": round(avg_base / k, 4),
            "log_loss": round(ll_base, 6),
            "brier": round(float(np.mean(base_br)), 6),
            "avg_ticket_hits": round(float(np.mean(base_ticket)), 4),
        },
        "lift_avg_hits": round(lift_hits, 4),
        "lift_log_loss": round(lift_ll, 4),
        "verdict": verdict,
        "hit_histogram": histogram,
        "per_issue": per_issue[-60:],
    }


def _verdict(lift_hits: float, lift_ll: float, periods: int) -> str:
    if lift_hits > 1.03 and lift_ll > 1.01:
        return f"模型在 {periods} 期回测中优于基线（命中 {lift_hits:.2f}×，似然 {lift_ll:.2f}×），但优势幅度仍可能来自随机波动。"
    if lift_hits < 0.97 and lift_ll < 0.99:
        return f"模型弱于均匀基线（命中 {lift_hits:.2f}×），说明当前特征没有可利用信息，建议只用基线做号码生成。"
    return f"模型与均匀基线基本等价（命中 {lift_hits:.2f}×）——这符合彩票独立同分布的预期，预测不能提高中奖率。"

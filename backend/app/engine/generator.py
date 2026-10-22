"""号码生成器：把边际概率变成 N 注可用号码。

要点：
- 同一批次内去重（同号码组合不重复出票）
- 按 strategy 调整抽样权重（热号/冷号/均衡/混合/随机）
- 3D 是有序彩种，按位置概率独立抽样
- 每注附带结构描述与依据，前端可直接展示
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ..games import GameSpec, get_game, format_number
from .dataset import BallData


def _zones(numbers: list[int], spec: GameSpec) -> str:
    low, high = spec.red.minimum, spec.red.maximum
    span = (high - low + 1) / 3
    buckets = [0, 0, 0]
    for value in numbers:
        idx = min(2, int((value - low) / span))
        buckets[idx] += 1
    return f"{buckets[0]}-{buckets[1]}-{buckets[2]}"


def describe_structure(numbers: list[int], spec: GameSpec) -> dict[str, Any]:
    if not numbers:
        return {"odd_even": "", "big_small": "", "sum": 0, "span": 0, "zones": "", "consecutive": 0}
    ordered = sorted(numbers)
    mid = (spec.red.minimum + spec.red.maximum) / 2
    odd = sum(1 for v in ordered if v % 2 == 1)
    big = sum(1 for v in ordered if v > mid)
    consecutive = sum(1 for a, b in zip(ordered, ordered[1:]) if b - a == 1)
    return {
        "odd_even": f"{odd}:{len(ordered) - odd}",
        "big_small": f"{big}:{len(ordered) - big}",
        "sum": int(sum(ordered)),
        "span": int(ordered[-1] - ordered[0]),
        "zones": _zones(ordered, spec),
        "consecutive": consecutive,
    }


def _reshape(probs: np.ndarray, strategy: str, rng: np.random.Generator) -> np.ndarray:
    p = probs.astype(np.float64).copy()
    if strategy == "hot":
        p = p ** 1.8
    elif strategy == "cold":
        order = np.argsort(np.argsort(p))
        p = (len(p) - order).astype(np.float64) ** 1.6
    elif strategy == "mixed":
        order = np.argsort(np.argsort(-p))
        p = p * (0.4 + 0.6 * ((order % 2).astype(np.float64)))
    elif strategy == "random":
        p = np.ones_like(p)
    elif strategy == "balanced":
        p = p ** 1.15
    p = np.clip(p, 1e-9, None)
    # 轻微噪声，避免 count>1 时全部出同注
    p = p * (0.85 + 0.3 * rng.random(len(p)))
    return p / p.sum()


def _draw_disjoint(probs: np.ndarray, k: int, rng: np.random.Generator) -> list[int]:
    """不放回加权抽样 k 个下标。"""
    idxs = rng.choice(len(probs), size=min(k, len(probs)), replace=False, p=probs)
    return sorted(int(i) for i in idxs)


def build_tickets(
    data: BallData,
    probs: np.ndarray,
    spec: GameSpec,
    count: int = 5,
    strategy: str = "balanced",
    seed: int = 0,
    pick: int | None = None,
) -> list[dict[str, Any]]:
    rng = np.random.default_rng(seed)
    tickets: list[dict[str, Any]] = []
    seen: set[tuple] = set()

    if spec.red.ordered:
        # 3D：三位独立按位置概率抽样（位置概率退化为整体边际的扰动）
        base = _reshape(probs, strategy, rng)
        attempts = 0
        while len(tickets) < count and attempts < count * 40:
            attempts += 1
            digits = []
            for pos in range(spec.red.count):
                local = base * (0.9 + 0.2 * rng.random(len(base)))
                local = local / local.sum()
                digits.append(int(rng.choice(spec.red.maximum + 1, p=local)))
            key = tuple(digits)
            if key in seen:
                continue
            seen.add(key)
            values = [str(d) for d in digits]
            tickets.append(
                {
                    "index": len(tickets) + 1,
                    "numbers": {"red": values, "blue": [], "ordered": values},
                    "score": float(np.prod([base[d] for d in digits])),
                    "structure": describe_structure(digits, spec),
                    "rationale": {"type": "ordered", "digits": values},
                }
            )
        return tickets

    k = spec.red.count
    if spec.code == "kl8":
        k = pick or 10
    base_red = _reshape(probs, strategy, rng)
    attempts = 0
    while len(tickets) < count and attempts < count * 60:
        attempts += 1
        cand = base_red * (0.9 + 0.2 * rng.random(len(base_red)))
        cand = cand / cand.sum()
        picked_idx = _draw_disjoint(cand, k, rng)
        red_numbers = [data.domain[i] for i in picked_idx]
        key = tuple(red_numbers)
        if key in seen:
            continue
        seen.add(key)
        score = float(np.mean([probs[i] for i in picked_idx]))
        blue_numbers: list[str] = []
        if spec.blue is not None:
            blue_numbers = [format_number(int(rng.integers(spec.blue.minimum, spec.blue.maximum + 1)), spec.blue)]
        tickets.append(
            {
                "index": len(tickets) + 1,
                "numbers": {
                    "red": [format_number(v, spec.red) for v in red_numbers],
                    "blue": blue_numbers,
                    "ordered": None,
                },
                "score": round(score, 6),
                "structure": describe_structure(red_numbers, spec),
                "rationale": {
                    "sum_prob_rank": "top" if score > float(np.mean(probs)) * 1.3 else "avg",
                    "picked_prob": [round(float(probs[i]), 5) for i in picked_idx],
                },
            }
        )
    return tickets

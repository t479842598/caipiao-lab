"""统计工具箱：频次 / 遗漏 / 走势 / 结构分布 / 随机性检验。"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

import numpy as np

from .dataset import BallData

try:  # scipy 不是硬依赖
    from scipy import stats as _sp

    _HAS_SCIPY = True
except Exception:  # noqa: BLE001  pragma: no cover
    _HAS_SCIPY = False


def _chi2_pvalue(chi2: float, dof: int) -> float:
    if dof <= 0:
        return 1.0
    if _HAS_SCIPY:
        return float(1.0 - _sp.chi2.cdf(chi2, dof))
    # Wilson–Hilferty 近似
    z = ((chi2 / dof) ** (1 / 3) - (1 - 2 / (9 * dof))) / math.sqrt(2 / (9 * dof))
    return float(0.5 * math.erfc(z / math.sqrt(2)))


def frequency_table(data: BallData, window: int = 100) -> list[dict[str, Any]]:
    sub = data.slice_tail(window) if window else data
    n = sub.n
    counts = sub.matrix.sum(axis=0).astype(int) if n else np.zeros(sub.size, dtype=int)
    expected_count = sub.matrix.shape[0] * (sub.matrix.sum() / max(sub.matrix.size, 1))
    items = []
    for i, number in enumerate(sub.domain):
        count = int(counts[i])
        rate = count / n if n else 0.0
        expected = float(expected_count)
        items.append(
            {
                "n": number,
                "count": count,
                "rate": round(rate, 5),
                "expected": round(expected, 3),
                "deviation": round(count - expected, 3),
                "recent": sub.matrix[-10:, i].astype(int).tolist() if n else [],
            }
        )
    return items


def omission_table(data: BallData, limit: int | None = None) -> list[dict[str, Any]]:
    n = data.n
    size = data.size
    if n == 0:
        return [{"n": v, "current": 0, "max": 0, "avg": 0.0, "last_issue": None} for v in data.domain]
    current = np.zeros(size, dtype=int)
    max_gap = np.zeros(size, dtype=int)
    total_gap = np.zeros(size, dtype=int)
    gap_count = np.zeros(size, dtype=int)
    pending = np.zeros(size, dtype=int)
    for row in range(n):
        hit = data.matrix[row] > 0
        gap_count[hit] += 1
        total_gap[hit] += pending[hit]
        pending[hit] = 0
        pending[~hit] += 1
        max_gap = np.maximum(max_gap, pending)
    current = pending
    last_seen: dict[int, str] = {}
    for i, number in enumerate(data.domain):
        column = data.matrix[:, i]
        idxs = np.nonzero(column)[0]
        if idxs.size:
            last_seen[number] = data.issues[int(idxs[-1])]
    items = []
    for i, number in enumerate(data.domain):
        gc = int(gap_count[i])
        items.append(
            {
                "n": number,
                "current": int(current[i]),
                "max": int(max_gap[i]),
                "avg": round(float(total_gap[i]) / gc, 2) if gc else 0.0,
                "last_issue": last_seen.get(number),
            }
        )
    if limit:
        items.sort(key=lambda x: x["current"], reverse=True)
        return items[:limit]
    return items


def trend_matrix(data: BallData, periods: int = 30) -> dict[str, Any]:
    sub = data.slice_tail(periods)
    matrix = sub.matrix.tolist()
    # 逐期遗漏值
    omission: list[list[int]] = []
    pending = [0] * sub.size
    for row in range(sub.n):
        for i in range(sub.size):
            if sub.matrix[row, i] > 0:
                pending[i] = 0
            else:
                pending[i] += 1
        omission.append(list(pending))
    return {
        "game": data.game,
        "ball": data.ball,
        "issues": sub.issues,
        "domain": sub.domain,
        "matrix": matrix,
        "omission": omission,
    }


def _values(mask_row: np.ndarray, domain: list[int], k: int) -> list[int]:
    picked = [domain[i] for i in np.nonzero(mask_row)[0]]
    picked.sort()
    return picked[:k] if k else picked


def distribution_stats(data: BallData, window: int = 100) -> dict[str, Any]:
    sub = data.slice_tail(window) if window else data
    k = data.positions if data.positions else 0
    if k == 0:
        # 无序彩种：按每期开出的号码数推导
        sample_row = sub.matrix[0] if sub.n else None
        k = int(sample_row.sum()) if sample_row is not None else 0
    sums, spans, odd_cnt, big_cnt, consecutive, zones = [], [], [], [], [], []
    low = data.domain[0]
    high = data.domain[-1]
    mid = (low + high) / 2
    span_total = max(high - low, 1)
    for row in range(sub.n):
        picked = _values(sub.matrix[row], sub.domain, k)
        if not picked:
            continue
        sums.append(sum(picked))
        spans.append(max(picked) - min(picked))
        odd_cnt.append(sum(1 for v in picked if v % 2 == 1))
        big_cnt.append(sum(1 for v in picked if v > mid))
        consecutive.append(sum(1 for a, b in zip(picked, picked[1:]) if b - a == 1))
        bucket = [0, 0, 0]
        for v in picked:
            idx = min(2, int((v - low) / (span_total + 1) * 3))
            bucket[idx] += 1
        zones.append(bucket)

    def hist(values: list[int], bins: int = 14) -> list[dict[str, Any]]:
        if not values:
            return []
        counter = Counter(values)
        keys = sorted(counter)
        if len(keys) > bins:
            step = (keys[-1] - keys[0]) / bins or 1
            bucketed: Counter = Counter()
            for key, count in counter.items():
                bucketed[int((key - keys[0]) / step)] += count
            return [{"bin": f"{int(keys[0] + b * step)}-{int(keys[0] + (b + 1) * step)}", "count": c}
                    for b, c in sorted(bucketed.items())]
        return [{"bin": str(key), "count": counter[key]} for key in keys]

    def describe(values: list[int]) -> dict[str, Any]:
        if not values:
            return {}
        arr = np.array(values, dtype=float)
        return {
            "mean": round(float(arr.mean()), 2),
            "std": round(float(arr.std(ddof=1)) if arr.size > 1 else 0.0, 2),
            "min": int(arr.min()),
            "max": int(arr.max()),
            "median": float(np.median(arr)),
        }

    return {
        "game": data.game,
        "window": window,
        "sum_hist": hist(sums, 18),
        "span_hist": hist(spans, 14),
        "odd_even_hist": [{"bin": f"{i}奇{k - i}偶", "count": c} for i, c in sorted(Counter(odd_cnt).items())],
        "big_small_hist": [{"bin": f"{i}大{k - i}小", "count": c} for i, c in sorted(Counter(big_cnt).items())],
        "zone_hist": [{"bin": f"{a}-{b}-{c}", "count": cnt} for (a, b, c), cnt in
                      sorted(Counter(tuple(z) for z in zones).items(), key=lambda x: -x[1])[:12]],
        "consecutive_hist": [{"bin": str(i), "count": c} for i, c in sorted(Counter(consecutive).items())],
        "stats": {
            "draws": sub.n,
            "sum": describe(sums),
            "span": describe(spans),
            "odd": describe(odd_cnt),
            "big": describe(big_cnt),
        },
    }


def randomness_report(data: BallData) -> dict[str, Any]:
    """卡方 + 游程 + 自相关：用来诚实地回答"能不能预测"。"""
    n = data.n
    size = data.size
    if n < 30:
        return {"game": data.game, "draws": n, "chi_square": {}, "runs_test": {},
                "autocorrelation": [], "verdict": "样本不足，无法检验"}

    observed = data.matrix.sum(axis=0).astype(float)
    expected_count = observed.sum() / size
    chi2 = float(((observed - expected_count) ** 2 / expected_count).sum())
    dof = size - 1
    p = _chi2_pvalue(chi2, dof)

    # 游程检验（按期总和序列的升降）
    per_draw = data.matrix.sum(axis=1).astype(float)
    diffs = np.diff(per_draw)
    signs = diffs[diffs != 0]
    runs = 1 + int(np.sum(signs[1:] != signs[:-1])) if signs.size else 0
    n1 = int(np.sum(signs > 0))
    n2 = int(np.sum(signs < 0))
    if n1 > 0 or n2 > 0:
        mean_runs = 2 * n1 * n2 / (n1 + n2) + 1
        var_runs = (2 * n1 * n2 * (2 * n1 * n2 - n1 - n2)) / (((n1 + n2) ** 2) * (n1 + n2 - 1))
        z_runs = (runs - mean_runs) / math.sqrt(var_runs) if var_runs > 0 else 0.0
    else:
        z_runs = 0.0

    autocorr = []
    for lag in range(1, 7):
        if n - lag < 10:
            break
        a = per_draw[:-lag]
        b = per_draw[lag:]
        if a.std() == 0 or b.std() == 0:
            corr = 0.0
        else:
            corr = float(np.corrcoef(a, b)[0, 1])
        autocorr.append({"lag": lag, "corr": round(corr, 4)})

    biased = p < 0.01
    verdict_parts = []
    verdict_parts.append(f"卡方 p={p:.4f}，" + ("各号频率显著不均" if biased else "各号频率未见显著偏差"))
    verdict_parts.append(f"游程 z={z_runs:.2f}，" + ("序列存在趋势" if abs(z_runs) > 2.58 else "序列无显著趋势"))
    verdict_parts.append("滞后自相关均在噪声范围内" if all(abs(a["corr"]) < 0.1 for a in autocorr) else "存在弱自相关")

    return {
        "game": data.game,
        "draws": n,
        "chi_square": {"statistic": round(chi2, 3), "dof": dof, "p_value": round(p, 6),
                       "uniform_expected": round(expected_count, 2)},
        "runs_test": {"runs": runs, "z": round(z_runs, 4),
                      "p_value": round(float(2 * (1 - 0.5 * math.erfc(abs(z_runs) / math.sqrt(2)))), 6)},
        "autocorrelation": autocorr,
        "verdict": "；".join(verdict_parts),
    }

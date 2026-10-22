"""概率模型层：每个模型输出同一形状的边际概率向量 p(number)。

统一契约 —— 输入 BallData（已按截止期截断）、输出 np.ndarray(float64) 长度 = 号码全集。
这样后端可以任意叠加、加权、回测，而生成器 / 组合器只认概率。
"""

from __future__ import annotations

from typing import Callable

import numpy as np

from .dataset import BallData

ENGINE_LABELS = {
    "uniform": "均匀基线（纯随机）",
    "frequency": "频率热号",
    "omission": "遗漏回补",
    "markov": "马尔可夫转移",
    "bayes": "贝叶斯平滑",
    "gbdt": "梯度提升树",
    "ensemble": "多模型集成",
}


def _normalize(p: np.ndarray, prior: np.ndarray | None = None, strength: float = 1e-6) -> np.ndarray:
    p = np.asarray(p, dtype=np.float64)
    p = np.where(np.isfinite(p), p, 0.0)
    p = np.clip(p, 0.0, None)
    if p.sum() <= 0:
        p = np.ones_like(p) if prior is None else prior.copy()
    p = p + strength
    return p / p.sum()


def uniform_model(data: BallData) -> np.ndarray:
    return np.full(data.size, 1.0 / data.size)


def frequency_model(data: BallData, window: int = 100, decay: float = 0.985) -> np.ndarray:
    """指数衰减加权频率：越近的期数权重越高。"""
    sub = data.slice_tail(window) if window else data
    if sub.n == 0:
        return uniform_model(data)
    weights = decay ** np.arange(sub.n - 1, -1, -1, dtype=np.float64)
    counts = weights @ sub.matrix.astype(np.float64)
    return _normalize(counts)


def omission_model(data: BallData, window: int = 200) -> np.ndarray:
    """遗漏回补：当前遗漏 / 历史平均遗漏 越大，回补压力越大。"""
    sub = data.slice_tail(window) if window else data
    if sub.n == 0:
        return uniform_model(data)
    pending = np.zeros(sub.size, dtype=np.float64)
    total_gap = np.zeros(sub.size, dtype=np.float64)
    gap_count = np.zeros(sub.size, dtype=np.float64)
    for row in range(sub.n):
        hit = sub.matrix[row] > 0
        gap_count[hit] += 1
        total_gap[hit] += pending[hit]
        pending[hit] = 0
        pending[~hit] += 1
    avg_gap = np.where(gap_count > 0, total_gap / np.maximum(gap_count, 1), sub.n / 2)
    avg_gap = np.maximum(avg_gap, 1.0)
    pressure = pending / avg_gap
    score = 1.0 + np.clip(pressure, 0, 5)
    return _normalize(score)


def markov_model(data: BallData, window: int = 300) -> np.ndarray:
    """一阶马尔可夫：用"上一期开出号码"作为状态，估计各号在下期出现的条件频率。"""
    sub = data.slice_tail(window) if window else data
    if sub.n < 3:
        return uniform_model(data)
    last = sub.matrix[-1] > 0
    if not last.any():
        return uniform_model(data)
    hits = sub.matrix[1:]
    prev = sub.matrix[:-1] > 0
    # 只看历史中"上期包含当前期号码集合中任一"的样本
    overlap = (prev & last).sum(axis=1)
    mask = overlap > 0
    if mask.sum() < 5:
        return frequency_model(data, window)
    conditional = hits[mask].sum(axis=0).astype(np.float64)
    conditional += 0.5  # 平滑
    return _normalize(conditional)


def bayes_model(data: BallData, window: int = 200, alpha: float = 20.0) -> np.ndarray:
    """Beta-Binomial 后验均值：把长期均匀先验与近期观测做收缩。"""
    sub = data.slice_tail(window) if window else data
    if sub.n == 0:
        return uniform_model(data)
    draws = sub.n
    k = float(sub.matrix.sum()) / draws if draws else 1.0
    prior_p = min(max(k / sub.size, 1e-6), 0.9)
    counts = sub.matrix.sum(axis=0).astype(np.float64)
    posterior = (counts + alpha * prior_p) / (draws + alpha)
    return _normalize(posterior)


def _feature_matrix(matrix: np.ndarray) -> np.ndarray:
    """对每一期 t 生成 (D, F) 特征：只用 t 及以前的数据，天然无未来泄漏。

    特征：近 10 期频率 / 近 50 期频率 / 全期频率 / 当前遗漏 / 冷热位次 / 期序进度。
    """
    n, size = matrix.shape
    m = matrix.astype(np.float64)
    cum = np.cumsum(m, axis=0)  # cum[t] = 到 t 为止的累计

    out = np.zeros((n, size, 6), dtype=np.float64)
    pending = np.zeros(size, dtype=np.float64)
    short_win = np.zeros((n, size), dtype=np.float64)
    mid_win = np.zeros((n, size), dtype=np.float64)
    for t in range(n):
        pending = np.where(matrix[t] > 0, 0.0, pending + 1.0)
        lo10 = max(0, t - 9)
        lo50 = max(0, t - 49)
        short_win[t] = m[lo10 : t + 1].mean(axis=0)
        mid_win[t] = m[lo50 : t + 1].mean(axis=0)
        upto = t + 1
        long = cum[t] / upto
        rank = np.argsort(np.argsort(-long)).astype(np.float64) / max(size - 1, 1)
        out[t, :, 0] = short_win[t]
        out[t, :, 1] = mid_win[t]
        out[t, :, 2] = long
        out[t, :, 3] = pending / 50.0
        out[t, :, 4] = rank
        out[t, :, 5] = upto / max(n, 1)
    return out


def gbdt_model(data: BallData, window: int = 400, cut: int | None = None, fast: bool = False) -> np.ndarray:
    """用 LightGBM 学"下期是否开出"，特征只用当期及以前，标签取自下一期。

    LightGBM 缺失时退化为逻辑回归，再缺失退化为频率模型——保证永远有输出。
    """
    if fast:
        window = min(window, 180)
    sub = data.slice_tail(window) if window else data
    if sub.n < 30:
        return frequency_model(data, window=window)
    limit = sub.n if cut is None else max(30, min(cut, sub.n))
    feats = _feature_matrix(sub.matrix[:limit])
    # 训练样本：t=9..limit-2，标签 y = matrix[t+1]
    rows = []
    labels = []
    for t in range(9, limit - 1):
        rows.append(feats[t])
        labels.append((sub.matrix[t + 1] > 0).astype(np.float64))
    if not rows:
        return frequency_model(data, window=window)
    X = np.vstack(rows)
    y = np.concatenate(labels)
    X_last = feats[limit - 1]
    return _fit_and_predict(X, y, X_last, sub.size, fast=fast)


_GBDT_BACKEND: str | None = None


def gbdt_backend() -> str:
    """探测可用的提升树后端：lightgbm → sklearn HistGBDT → 逻辑回归。

    LightGBM 在 macOS 上需要 libomp，服务器未必装；HistGradientBoosting 是
    sklearn 内置的同类实现，无额外系统依赖，所以默认走它。
    """
    global _GBDT_BACKEND
    if _GBDT_BACKEND:
        return _GBDT_BACKEND
    try:
        import lightgbm  # type: ignore  # noqa: F401

        _GBDT_BACKEND = "lightgbm"
        return _GBDT_BACKEND
    except Exception:  # noqa: BLE001
        pass
    try:
        from sklearn.ensemble import HistGradientBoostingClassifier  # noqa: F401

        _GBDT_BACKEND = "sklearn_hgb"
        return _GBDT_BACKEND
    except Exception:  # noqa: BLE001
        pass
    _GBDT_BACKEND = "logistic"
    return _GBDT_BACKEND


def _fit_and_predict(
    X: np.ndarray, y: np.ndarray, X_last: np.ndarray, size: int, fast: bool = False
) -> np.ndarray:
    if len(np.unique(y)) < 2:
        return np.full(size, 1.0 / size)
    backend = gbdt_backend()
    if backend == "lightgbm":
        try:
            import lightgbm as lgb  # type: ignore

            model = lgb.LGBMClassifier(
                n_estimators=120,
                learning_rate=0.06,
                num_leaves=15,
                min_child_samples=20,
                subsample=0.9,
                colsample_bytree=0.9,
                verbose=-1,
            )
            model.fit(X, y)
            return _normalize(model.predict_proba(X_last)[:, 1])
        except Exception:  # noqa: BLE001
            pass
    if backend in ("lightgbm", "sklearn_hgb"):
        try:
            from sklearn.ensemble import HistGradientBoostingClassifier

            model = HistGradientBoostingClassifier(
                max_iter=25 if fast else 120, learning_rate=0.08 if fast else 0.06,
                max_leaf_nodes=15,
                min_samples_leaf=20, l2_regularization=1.0, random_state=42,
            )
            model.fit(X, y)
            return _normalize(model.predict_proba(X_last)[:, 1])
        except Exception:  # noqa: BLE001
            pass
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler

        scaler = StandardScaler().fit(X)
        model = LogisticRegression(max_iter=400)
        model.fit(scaler.transform(X), y)
        return _normalize(model.predict_proba(scaler.transform(X_last))[:, 1])
    except Exception:  # noqa: BLE001
        return np.full(size, 1.0 / size)


def uniform_model_stub(size: int) -> np.ndarray:
    return np.full(size, 1.0 / size)


ENGINES: dict[str, Callable[[BallData], np.ndarray]] = {
    "uniform": uniform_model,
    "frequency": frequency_model,
    "omission": omission_model,
    "markov": markov_model,
    "bayes": bayes_model,
}


def compute_marginals(
    data: BallData,
    engine: str = "ensemble",
    window: int = 100,
    cut: int | None = None,
    fast: bool = False,
) -> tuple[np.ndarray, dict[str, float]]:
    """返回 (边际概率, 各子模型权重)。fast=True 用于回测的滚动计算。"""
    if engine == "common":
        engine = "ensemble"
    if engine == "gbdt":
        return gbdt_model(data, window=max(window, 200), cut=cut, fast=fast), {"gbdt": 1.0}
    if engine in ENGINES:
        if engine == "frequency":
            return ENGINES[engine](data, window=window), {engine: 1.0}
        return ENGINES[engine](data), {engine: 1.0}
    # ensemble
    parts = {
        "frequency": frequency_model(data, window=window),
        "omission": omission_model(data, window=max(window, 100)),
        "markov": markov_model(data, window=max(window, 200)),
        "bayes": bayes_model(data, window=max(window, 150)),
    }
    gbdt_p = gbdt_model(data, window=max(window, 250), cut=cut, fast=fast)
    parts["gbdt"] = gbdt_p
    weights = {"frequency": 0.30, "omission": 0.15, "markov": 0.15, "bayes": 0.15, "gbdt": 0.25}
    stacked = np.zeros(data.size, dtype=np.float64)
    for name, prob in parts.items():
        stacked += weights[name] * prob
    return _normalize(stacked), weights

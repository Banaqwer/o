"""Fit the entry-score weights on development data only.

An L2-regularised logistic regression of the reversion label on the six
score components the engine already computes. The regularisation strength
is chosen by cross-validation grouped by session so that events from one
session never sit on both sides of a fold. The fitted coefficients replace
the hand-set ``s_*`` weights and ``bias`` in :class:`ReversalConfig`; the
entry threshold stays a rolling quantile, so only the ranking matters.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd

from ..config import ReversalConfig

FEATURES: Tuple[str, ...] = ("c_confluence", "c_overshoot", "c_divergence", "c_climax", "c_regime", "c_ladder")
_CONFIG_NAMES = {"c_confluence": "s_confluence", "c_overshoot": "s_overshoot", "c_divergence": "s_divergence", "c_climax": "s_climax", "c_regime": "s_regime", "c_ladder": "s_ladder"}


@dataclass(frozen=True)
class FitResult:
    weights: Dict[str, float]
    bias: float
    lam: float
    cv_logloss: Dict[float, float]
    n: int
    base_rate: float

    def to_config(self, base: ReversalConfig) -> ReversalConfig:
        kw = {_CONFIG_NAMES[f]: float(w) for f, w in self.weights.items()}
        return replace(base, bias=float(self.bias), **kw)


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


def ridge_logistic(X: np.ndarray, y: np.ndarray, lam: float, iters: int = 100, tol: float = 1e-8) -> Tuple[np.ndarray, float]:
    """Newton-Raphson for L2-penalised logistic regression (intercept unpenalised)."""

    n, p = X.shape
    Xb = np.hstack([X, np.ones((n, 1))])
    w = np.zeros(p + 1)
    pen = np.full(p + 1, lam)
    pen[-1] = 0.0
    for _ in range(iters):
        mu = _sigmoid(Xb @ w)
        g = Xb.T @ (mu - y) + pen * w
        s = mu * (1 - mu)
        H = (Xb * s[:, None]).T @ Xb + np.diag(pen)
        step = np.linalg.solve(H, g)
        w -= step
        if np.max(np.abs(step)) < tol:
            break
    return w[:-1], float(w[-1])


def logloss(X: np.ndarray, y: np.ndarray, w: np.ndarray, b: float) -> float:
    p = np.clip(_sigmoid(X @ w + b), 1e-9, 1 - 1e-9)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def fit_weights(
    events: pd.DataFrame,
    labels: pd.Series,
    lam_grid: Sequence[float] = (0.3, 1.0, 3.0, 10.0, 30.0, 100.0),
    folds: int = 5,
    seed: int = 5,
    features: Sequence[str] = FEATURES,
) -> FitResult:
    mask = labels.notna()
    X = events.loc[mask, list(features)].to_numpy(dtype=float)
    y = labels[mask].to_numpy(dtype=float)
    groups = events.loc[mask, "session_date"].astype(str).to_numpy()
    n = len(y)
    if n < 50:
        raise ValueError("too few labelled events to fit")
    # standardise features on the fit set; weights are mapped back to raw scale
    mu, sd = X.mean(axis=0), X.std(axis=0)
    sd[sd == 0] = 1.0
    Xs = (X - mu) / sd

    rng = np.random.default_rng(seed)
    uniq = np.array(sorted(set(groups)))
    rng.shuffle(uniq)
    fold_of = {g: i % folds for i, g in enumerate(uniq)}
    f = np.array([fold_of[g] for g in groups])

    cv: Dict[float, float] = {}
    for lam in lam_grid:
        losses: List[float] = []
        for k in range(folds):
            tr, te = f != k, f == k
            if te.sum() == 0 or tr.sum() == 0:
                continue
            w, b = ridge_logistic(Xs[tr], y[tr], lam)
            losses.append(logloss(Xs[te], y[te], w, b))
        cv[lam] = float(np.mean(losses))
    best = min(cv, key=cv.get)
    w_s, b_s = ridge_logistic(Xs, y, best)
    w_raw = w_s / sd
    b_raw = b_s - float(np.sum(w_s * mu / sd))
    return FitResult({feat: float(v) for feat, v in zip(features, w_raw)}, b_raw, best, cv, n, float(y.mean()))

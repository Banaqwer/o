import math
import random

import numpy as np

from atm_engine.features.estimators import Ewma, EwmVar, RollingSum, SortedWindow, logistic, norm_cdf


def test_sorted_window_quantiles_match_numpy():
    rnd = random.Random(1)
    w = SortedWindow(50)
    xs = [rnd.gauss(0, 1) for _ in range(200)]
    for x in xs:
        w.push(x)
    tail = np.array(xs[-50:])
    for q in (0.0, 0.1, 0.5, 0.8, 0.95, 1.0):
        assert math.isclose(w.quantile(q), float(np.quantile(tail, q)), rel_tol=1e-12, abs_tol=1e-12)
    assert len(w) == 50


def test_sorted_window_ignores_nan_and_ranks():
    w = SortedWindow(10)
    w.push(float("nan"))
    assert len(w) == 0
    for x in range(10):
        w.push(float(x))
    assert w.rank(5.0) == 0.5
    assert w.rank(100.0) == 1.0


def test_ewmvar_matches_pandas_like_recursion():
    v = EwmVar(half_life=10)
    xs = [1.0, 2.0, 4.0, 8.0, 3.0]
    for x in xs:
        v.update(x)
    # mean recursion check
    a = 1 - math.exp(-math.log(2) / 10)
    m = xs[0]
    for x in xs[1:]:
        m = (1 - a) * m + a * x
    assert math.isclose(v.mean, m, rel_tol=1e-12)
    assert v.var > 0
    assert v.z(100.0, min_n=1) > 0
    assert v.z(100.0, min_n=50) == 0.0  # warm-up guard


def test_ewma_bias_corrected_first_value():
    e = Ewma(half_life=20)
    assert e.update(5.0) == 5.0


def test_rolling_sum():
    r = RollingSum(3)
    for x in (1, 2, 3, 4):
        r.push(float(x))
    assert r.value == 9.0 and len(r) == 3 and r.full


def test_norm_cdf_and_logistic():
    assert math.isclose(norm_cdf(0.0), 0.5)
    assert math.isclose(norm_cdf(1.96), 0.975, abs_tol=1e-3)
    assert math.isclose(logistic(0.0), 0.5)
    assert logistic(-800) == 0.0 or logistic(-800) > 0  # no overflow

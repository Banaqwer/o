"""Small, dependency-free incremental estimators.

All estimators are O(1) or O(log n) per update except ``SortedWindow`` whose
insert/remove is an O(n) memmove on a Python list -- for windows of a few
thousand floats this is far cheaper than recomputing a quantile.
"""

from __future__ import annotations

import math
from bisect import bisect_left, insort
from collections import deque
from typing import Deque, List, Optional


def half_life_to_alpha(half_life: float) -> float:
    if half_life <= 0:
        raise ValueError("half_life must be positive")
    return 1.0 - math.exp(-math.log(2.0) / half_life)


class Ewma:
    """Exponentially weighted mean with bias correction during warm-up."""

    __slots__ = ("alpha", "_m", "_w", "n")

    def __init__(self, half_life: float):
        self.alpha = half_life_to_alpha(half_life)
        self._m = 0.0
        self._w = 0.0
        self.n = 0

    def update(self, x: float) -> float:
        self._m = (1 - self.alpha) * self._m + self.alpha * x
        self._w = (1 - self.alpha) * self._w + self.alpha
        self.n += 1
        return self.value

    @property
    def value(self) -> float:
        return self._m / self._w if self._w > 0 else float("nan")

    @property
    def ready(self) -> bool:
        return self.n > 0


class EwmVar:
    """Exponentially weighted mean and variance (West's algorithm)."""

    __slots__ = ("alpha", "_mean", "_var", "_w", "n")

    def __init__(self, half_life: float):
        self.alpha = half_life_to_alpha(half_life)
        self._mean = 0.0
        self._var = 0.0
        self._w = 0.0
        self.n = 0

    def update(self, x: float) -> None:
        if self.n == 0:
            self._mean, self._var, self._w = x, 0.0, self.alpha
        else:
            diff = x - self._mean
            incr = self.alpha * diff
            self._mean += incr
            self._var = (1 - self.alpha) * (self._var + diff * incr)
            self._w = (1 - self.alpha) * self._w + self.alpha
        self.n += 1

    @property
    def mean(self) -> float:
        return self._mean if self.n else float("nan")

    @property
    def var(self) -> float:
        return self._var if self.n > 1 else float("nan")

    @property
    def std(self) -> float:
        v = self.var
        return math.sqrt(v) if v == v and v > 0 else float("nan")

    def z(self, x: float, min_n: int = 30) -> float:
        """Standardised value; 0 until ``min_n`` observations have been seen."""
        if self.n < min_n:
            return 0.0
        s = self.std
        if not (s == s) or s <= 0:
            return 0.0
        return (x - self._mean) / s


class SortedWindow:
    """Fixed-length FIFO window kept in sorted order for quantile reads."""

    __slots__ = ("maxlen", "_fifo", "_sorted")

    def __init__(self, maxlen: int):
        if maxlen <= 0:
            raise ValueError("maxlen must be positive")
        self.maxlen = maxlen
        self._fifo: Deque[float] = deque()
        self._sorted: List[float] = []

    def __len__(self) -> int:
        return len(self._fifo)

    def push(self, x: float) -> None:
        if x != x:  # NaN never enters the distribution
            return
        if len(self._fifo) == self.maxlen:
            old = self._fifo.popleft()
            del self._sorted[bisect_left(self._sorted, old)]
        self._fifo.append(x)
        insort(self._sorted, x)

    def quantile(self, q: float) -> Optional[float]:
        n = len(self._sorted)
        if n == 0:
            return None
        if not (0.0 <= q <= 1.0):
            raise ValueError("q must be in [0, 1]")
        pos = q * (n - 1)
        lo = int(math.floor(pos))
        hi = min(lo + 1, n - 1)
        frac = pos - lo
        return self._sorted[lo] * (1 - frac) + self._sorted[hi] * frac

    def rank(self, x: float) -> float:
        """Empirical CDF of x in [0, 1]."""
        n = len(self._sorted)
        if n == 0:
            return 0.5
        return bisect_left(self._sorted, x) / n


class RollingSum:
    __slots__ = ("maxlen", "_fifo", "_sum")

    def __init__(self, maxlen: int):
        self.maxlen = maxlen
        self._fifo: Deque[float] = deque()
        self._sum = 0.0

    def push(self, x: float) -> float:
        self._fifo.append(x)
        self._sum += x
        if len(self._fifo) > self.maxlen:
            self._sum -= self._fifo.popleft()
        return self._sum

    @property
    def value(self) -> float:
        return self._sum

    def __len__(self) -> int:
        return len(self._fifo)

    @property
    def full(self) -> bool:
        return len(self._fifo) >= self.maxlen


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def logistic(x: float) -> float:
    if x >= 0:
        e = math.exp(-x)
        return 1.0 / (1.0 + e)
    e = math.exp(x)
    return e / (1.0 + e)


def clip(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x

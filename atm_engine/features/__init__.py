"""Feature components: deviation, order flow, liquidity, structure, regime.

Every component is an incremental estimator with an ``update(bar)`` method
and is driven by the same bar stream in research and live use, so there is a
single code path and no train/serve skew.
"""

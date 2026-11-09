"""ATM reversal engine.

A faithful implementation of the methodology described publicly at
https://atprivate.capital/ :

* a proprietary model that runs continuously and maps, per instrument, the
  prices where the market is most likely to react;
* a four-rung ladder around price -- Omega II and Omega I above (selling
  levels), Alpha I and Alpha II below (buying levels);
* levels derived from statistical deviation analysis, order flow, liquidity
  dynamics and price structure, combined holistically with no fixed
  thresholds and adapting as the market regime changes;
* a reversal engine that reads live price against the ladder, marks every
  level test, and emits (price, direction, timestamp) events, re-evaluating
  live entries against the whole ladder rather than a single level;
* a per-session log of every level and entry with the subsequent reaction.

The site states that the output is analytical only: no position sizing, no
risk parameters and no execution logic are included here either.
"""

from .config import EngineConfig
from .engine.reversal import ReversalEngine
from .research.backtest import replay

__all__ = ["EngineConfig", "ReversalEngine", "replay"]
__version__ = "0.1.0"

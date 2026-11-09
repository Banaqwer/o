# ATM reversal engine

An open implementation of the methodology described at
[atprivate.capital](https://atprivate.capital/): a proprietary model that
maps, per futures contract, the prices where the market is most likely to
react, published as a four-rung ladder around price and read live by a
*reversal engine* that marks every level test and logs how price reacted.

The source material discloses a specification, not formulas. Everything the
site states is implemented as stated; where it is silent, the choices below
are the standard quantitative tools for each named component. Those choices
are documented here so they can be checked, and the whole thing runs on the
same code path in research replay and live streaming.

| Site statement | Implementation |
| --- | --- |
| Four levels per instrument: Ω II, Ω I above price (Selling), α I, α II below (Buying) | `Rung`, `Ladder`; direction belongs to the rung |
| "Statistical deviation analysis" | Session VWAP anchor; dispersion `rho` = volume-weighted std of traded prices around it, floored by one-bar volatility; band multipliers are quantiles of the rolling empirical distribution of standardised deviation |
| "Order flow" | Bid/ask volume when the feed has it, else bulk-volume classification; absorption prints become level proposals; delta divergence and intrabar rejection are scored at each test |
| "Liquidity dynamics" | Amihud illiquidity and Kyle's lambda; volume relative to a time-of-day profile; prior and developing volume profile (POC, value area, high-volume nodes) as level proposals |
| "Price structure" | Prior-session high/low/close, overnight high/low, opening range, developing session extremes, lag-confirmed fractal swings weighted by recency and re-tests |
| "No fixed thresholds ... adapts as the underlying environment changes" | Every knob is in sigma units, probabilities or horizons; a regime component (fast/slow volatility ratio, efficiency ratio, illiquidity) scales ladder width and a confidence term |
| "Weighing the full ladder rather than any single level" | Proposals snap to bands by confluence; a rung steps out to the next band when price is already beyond it; entry scores use the test's position inside the ladder and how many same-side rungs have given way |
| "Marks each point where a level is tested ... price, direction and timestamp" | `ReversalEngine` reads each bar against the ladder published *before* it; touch, re-arm and break tolerances are in sigma units |
| "Every level and entry ... logged ... with how price reacted afterwards" | `SessionLog` writes the ladder at every bar and every event with its forward reaction (MFE, MAE, reversion to anchor at several horizons) |
| "No position sizing, no risk parameters and no execution logic" | None included |

## Data

The engine needs intraday bars with volume. Three free sources are wired in
under `atm_engine/data/sources/`:

| Source | What it gives the engine | Access |
| --- | --- | --- |
| [London Strategic Edge, LSE Data 3.0](https://londonstrategicedge.com/api-documentation) | Intraday candles (`time, open, high, low, close, volume, trades`) for the free `futures`, `indices` and `commodities` markets, e.g. `SP500`; CME Globex contracts such as `NQZ6` need a CME plan | Free key from the Databank in `LSE_API_KEY`; 60 calls/min, one download at a time, 2.5M rows per export, 12.5M rows/day |
| [FRED](https://fred.stlouisfed.org/) | Daily VIX, Treasury spreads, index closes for the regime context | Keyless CSV endpoint |
| [Kenneth R. French library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html) | Daily market, size, value, profitability, investment and momentum factors for the context | Public zip files |

```bash
export LSE_API_KEY=...                                   # free key from the Databank
atm-engine fetch-lse --usage                             # plan and allowances
atm-engine fetch-lse --market futures --search nasdaq    # find the symbol
atm-engine fetch-lse --market futures --symbol SP500 --timeframe 1m \
    --start 2026-01-02 --end 2026-03-31 --out sp500_1m.csv
atm-engine context --start 2015-01-01 --out context.csv  # FRED + French, no key
atm-engine replay sp500_1m.csv --instrument ES --context context.csv --out session_log
```

The LSE client follows the published contract: key in the `X-API-Key`
header, export streamed or prepared as a job that is polled and
checksum-verified, `Retry-After` honoured, ranges bisected by the server's
own row estimate so each export stays under the plan cap. It is exercised
against a scripted server in the tests; a live run needs a key.

The daily context (standardised log-VIX, VIX percentile, 10y-2y spread,
20-day index return and volatility, 63-day drawdown, 20-day market factor
return and volatility) is read for each session from the **previous**
close only. It enters the regime width multiplier through
`RegimeConfig.beta_exogenous` and is attached to every event as `ctx_*`
columns, so reaction statistics can be cut by VIX regime with
`summarize_by(events, "ctx_vix_z")`.

## Layout

```
atm_engine/
  config.py            frozen, scale-free configuration; per-instrument tick sizes
  types.py             Bar, Rung, Level, Ladder, Event, Reaction
  data/                session clock, schema validation, labelled synthetic bars
  data/sources/        LSE Data 3.0 client, FRED and French library fetchers, cached HTTP
  features/            deviation, orderflow, liquidity, structure, regime, estimators
  engine/              ladder builder, reversal engine, reaction tracker, session log
  research/            replay harness, reaction statistics, daily macro context
  cli.py               demo / replay / stats / fetch-lse / context
tests/                 unit and invariant tests (no-lookahead, ordering, determinism)
```

## Use

```bash
pip install -e .[dev]
pytest
atm-engine demo --instrument NQ --sessions 10          # seeded synthetic bars
atm-engine replay bars.csv --instrument NQ --out session_log
atm-engine stats session_log --instrument NQ
```

The CSV needs `ts` (ISO, timezone-aware or UTC), `open`, `high`, `low`,
`close`, `volume`, and optionally `buy_volume`, `sell_volume`.

```python
from atm_engine import EngineConfig, ReversalEngine, replay
from atm_engine.config import config_for

cfg = config_for("NQ")
engine = ReversalEngine(cfg)
for bar in live_bars():            # Bar objects, timezone-aware
    step = engine.on_bar(bar)
    if step.ladder:                # published after each regular-session bar
        print(step.ladder.ordered())
    for ev in step.events:         # level tests: price, direction, timestamp
        print(ev.ts, ev.rung.value, ev.direction.value, ev.level_price, ev.score, ev.is_entry)
```

## Algorithm

1. **Anchor and dispersion.** For each regular session, `A_t` is the
   volume-weighted average of typical prices since the open and
   `rho_t = sqrt(Var_vwap + sigma_bar^2)` where `Var_vwap` is the
   volume-weighted variance of traded prices around `A_t` and `sigma_bar` is
   the EWMA one-bar volatility in points. `z_t = (close - A_t) / rho_t`.
2. **Bands.** `k_inner`, `k_outer` are the 80th and 95th percentiles of the
   rolling |z| distribution (defaults; probabilities, not points). Bands are
   `A ± k · rho · m` with `m` the regime width multiplier, extended outward
   at equal spacing.
3. **Proposals.** Order flow, liquidity and structure each propose prices
   with weights. Each proposal attaches to its nearest band inside a kernel
   window of `0.35 rho` and pulls it with weight
   `component × regime scale × (1 − (d/window)^2)`. The summed weight is the
   band's confluence.
4. **Placement.** Ω I is the first upper candidate clearing price by
   `0.25 rho`; Ω II the first clearing Ω I by `0.45 rho`; α mirrored. A
   published rung is held while its band stays within `0.20 rho`, drifts
   with it otherwise, and is re-placed only after a break. Held rungs can be
   traded through, which is what makes them testable.
5. **Tests and breaks.** On each bar the previous ladder is read: a rung is
   tested when the bar trades within `0.08 rho` of it, re-armed after price
   retreats `0.5 rho`, broken on a close `0.3 rho` through it.
6. **Entry score.** `logistic(bias + Σ w_i c_i)` over confluence,
   historical rank of the deviation at the test, flow divergence, climactic
   relative volume, regime confidence and ladder context. An event is an
   entry when its score clears the rolling 60th percentile of past scores.
7. **Reaction.** For each event: max favourable and adverse excursion and
   whether the anchor was revisited at 5, 15, 30 and 60 bars, in points and
   in sigma units.

## Scope and limitations

Stated plainly, as the source does. The engine is developed against
historical data; nothing about past behaviour obliges future price to do the
same thing. Behaviour is conditional on market regime and can degrade
without any error occurring. The output is analytical: it contains no
position sizing, risk parameters or execution logic. The synthetic data
generator exists for tests and demonstration only; its output is not a
record of trading and the statistics it produces say nothing about live
markets.

The `trading_algo/` directory and the PDF/text files in this repository are
unrelated earlier material and are not used by this package.

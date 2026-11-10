# Results: the ATM reversal engine and the OTE family

Recorded 10 November 2026. Everything below follows the pre-registered
protocol in `docs/protocol.md` and its seven amendments, each logged before
the data it concerns was read. Raw phase outputs are in `docs/record/`.

Data: London Strategic Edge `/vault/candles`, 1-minute continuous
front-month futures with volume, NQ, ES and GC, 2018 to November 2026.
Costs everywhere: 2.50 USD commission per side and one tick of slippage per
side, paid in the fills (15 USD per NQ round trip, 15 USD ES, 25 USD GC).
Inference everywhere: session-level, moving-block bootstrap of five
sessions, annualised session Sharpe. One contract per signal.

## Summary

* **The ladder has no edge out of sample.** On the pre-registered hold-out
  (NQ, January 2024 to October 2025, 474 sessions, run once) the frozen
  configuration lost 51.5 USD per trade at stated costs, 157 USD per
  session with a 95% interval of [-338, +23], Sharpe -1.30. It loses at
  zero costs too (-36 USD per trade), so this is not a cost story. ES and
  GC, run unchanged, lost 34 and 28 USD per trade. The protocol's verdict
  is a failure to show an edge.
* **The validation signal was an opening-minutes fade that reversed.** On
  2022-2023 the chosen cell made +36.5 USD a trade (Sharpe 1.01, interval
  including zero) and 70% of that came from signals in the first five
  minutes of the session. On 2024-2025 the same first five minutes lost
  100 USD a trade and account for 87% of the hold-out loss.
* **The OTE family is null on development**, three times, including once
  after an independent fidelity review and a corrected set of nulls. The
  faithful setup fires about once or twice a month in regular hours and
  loses after costs under every management rule the lesson describes.
* **Two adversarial audits changed the numbers but not the verdicts.**
  Slippage had been counted twice (every costed figure was 10 USD a trade
  too pessimistic on NQ) and the engine's reaction statistics were
  measured from the level rather than from an obtainable price (inflating
  them about threefold). Both were fixed before the hold-out was run.
* **What survives is the engine, the data plumbing and the protocol**, not
  a trading edge: a faithful, look-ahead-free implementation of the
  website's description, free data from the LSE vault, FRED and the
  French library, a costed overlay with session-level inference, and a
  logged research record in which every look is accounted for.

## 1. The ladder (ATM reversal engine)

The engine is the implementation described in the README: a four-rung
ladder around the session VWAP, placed in units of a dispersion `rho`,
pulled by order-flow, liquidity and structure proposals, read bar by bar
for tests and breaks, with an entry score and a reaction log. The costed
overlay used for every verdict enters at the open of the bar after a level
test, holds a stop beyond the level and a target at the anchor, and exits
on the stop, the target, a time limit or the 15:59 ET close.

### Development, NQ 2018-2021 (1,030 sessions)

7,853 level tests, 3,162 entries (3.07 per session). The reversion label
(one rho in the rung's direction before one rho against it, within 60
bars, measured from the next open) has a base rate of 0.44 on entries. An
L2 logistic fit of the six score components on that label beat the
intercept-only model by 0.0018 in grouped-CV log-loss against the
pre-stated 0.005 rule, so the hand-set weights were kept for every later
phase.

Overlay on development entries after amendment 6 (stated costs, USD per
contract per session; the full 12-cell table is in
`docs/record/ladder_dev.md`):

| Cell | Trades | Hit | Net/trade | Session mean | 95% interval | Sharpe | Net per rho |
| --- | --- | --- | --- | --- | --- | --- | --- |
| stop 3, H 60 | 3162 | 0.57 | +5.3 | +16 | [-53, +82] | 0.24 | +0.03 |
| stop 5, H 60 | 3162 | 0.64 | +13.8 | +42 | [-40, +116] | 0.56 | +0.08 |
| stop 5, H 60, 09:30-12:00 | 2807 | 0.65 | +23.9 | +65 | [-5, +133] | 0.92 | +0.17 |
| all tests, stop 3, H 60 | 7853 | 0.55 | -13.8 | -105 | [-213, -2] | -0.92 | -0.06 |
| |z|-matched random baseline, stop 3, H 60 | 3138 | 0.50 | -22.6 | -69 | [-217, +78] | -0.46 | -0.04 |

Every 15-bar cell is negative. Entries beat both nulls (all tests, and
random bars at the same |z|) by 20 to 35 USD a trade; no development cell
has an interval above zero.

### Validation, NQ 2022-2023 (514 sessions), one look

The amended 18-cell grid (entry quantile {0.5, 0.6, 0.7} x stop {2, 3, 5}
rho x horizon {15, 60}), all cells reported in `docs/record/ladder_val.md`.
The pre-specified rule (highest Sharpe among cells with at least 0.5
trades per session) picked q = 0.6, stop 5 rho, H 60, the same cell before
and after the cost correction of amendment 6.

| | Before amendment 6 (slippage counted twice) | After |
| --- | --- | --- |
| Net per trade | +26.5 | +36.5 |
| Session mean, 95% interval | +91 [-80, +258] | +125 [-45, +291] |
| Sharpe | 0.73 | 1.01 |
| Cells positive / interval above zero | 5 / 0 of 18 | 8 / 0 of 18 |
| Secondary 09:30-12:00, session mean, Sharpe | +111 [-49, +269], 0.94 | +141 [-19, +299], 1.20 |

Chosen cell after amendment 6, 1,758 trades, hit rate 0.63, 21% stopped,
50% reach the anchor:

| Costs | Net/trade | Session mean | 95% interval | Sharpe |
| --- | --- | --- | --- | --- |
| stated (1 tick/side) | +36.5 | +125 | [-45, +291] | 1.01 |
| zero | +49.9 | +171 | [+3, +329] | 1.40 |
| 2 ticks/side | +22.9 | +78 | [-92, +245] | 0.64 |
| 3 ticks/side | +10.8 | +37 | [-131, +205] | 0.30 |
| double (2 ticks, 5 USD) | +17.9 | +61 | [-110, +227] | 0.50 |
| matched random baseline, stated | -77.4 | -262 | [-660, +204] | -0.82 |

Where the validation money comes from (chosen cell, by the signal bar's
minute since the open):

| Minute | Trades | Hit | Net/trade | Share of total net |
| --- | --- | --- | --- | --- |
| 0-4 | 817 | 0.64 | +55 | 70% |
| 5-29 | 456 | 0.74 | +67 | 47% |
| 30+ | 485 | 0.53 | -23 | -18% |

Read plainly: on validation the engine's entries make about 36 USD a
trade net at one contract, a session Sharpe of one, and the interval
includes zero. Break-even is about 3.5 ticks of slippage per side. The
edge sits in the first half hour; after that the levels lose.

## 2. The audits

Two independent adversarial reviews were run before the hold-out, each
with several lenses and two referees per finding.

**Pipeline audit** (leakage, overlay, statistics, data, protocol
integrity; 38 agents, 14 claims refuted, 2 confirmed):

* Slippage was counted twice (fills and the cost line), so every costed
  number was 10 USD a trade too pessimistic on NQ. Fixed, development and
  validation re-run mechanically; the chosen cell did not change.
* The engine's reaction statistics (MFE, MAE) were measured from the level
  price, crediting the test bar's own rejection as reaction and inflating
  the engine's "reaction evidence" about threefold. Fixed: measured from
  the next open. The costed overlay never used them.
* Refuted, with the reasons in the record: that the hold-out criterion is
  too weak to be informative (it is conservative, not biased), that the
  fit rejection rule and grid amendment were disguised selection (both
  were logged before validation and re-running the original path does
  not flip the sign of the chosen cell), that the |z|-matched baseline is
  wrong (it is a weaker null than a time-of-day match, and is now
  reported as such), that roll sessions or the gold session clock drive
  the result.
* Stated limitations added to the protocol before the hold-out: the
  object under test is an opening-minutes fade to the session VWAP, the
  USD cost model is harsher in 2018-2019 than in 2024-2025 because rho in
  USD tripled, and the result is for one contract.

**OTE fidelity and look-ahead review** (five lenses, 33 agents, no
look-ahead found, five fidelity gaps confirmed): see section 4.

## 3. Hold-out (one run, 10 November 2026)

Frozen configuration: hand-set weights, entry quantile 0.6, stop 5 rho,
target at the anchor, 60-bar limit, flat at 15:59 ET. Period: 2024-01-01
to 2025-11-01 (the year after it was seen before the protocol and is
reported separately, not as evidence). Full tables in
`docs/record/ladder_holdout.md`.

| Instrument | Sessions | Trades | Hit | Net/trade | Session mean | 95% interval | Sharpe | Net per rho | Zero-cost net/trade |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NQ | 474 | 1447 | 0.63 | -51.5 | -157 | [-338, +23] | -1.30 | -0.16 | -35.8 |
| ES | 474 | 1518 | 0.63 | -33.9 | -109 | [-201, -17] | -1.76 | -0.20 | -5.4 |
| GC | 475 | 1549 | 0.65 | -28.4 | -93 | [-201, +23] | -1.12 | -0.11 | -4.2 |

The pre-registered criterion (NQ interval entirely above zero at stated
costs) is not met. The secondary morning hypothesis fails as well (NQ
09:30-12:00: -49 USD a trade, Sharpe -1.15). Both hold-out years are
negative on all three instruments; no VIX tercile is positive on NQ.

NQ hold-out by minute since the open:

| Minute | Trades | Hit | Net/trade | Share of total net |
| --- | --- | --- | --- | --- |
| 0-4 | 653 | 0.61 | -100 | 87% |
| 5-29 | 363 | 0.75 | +25 | -12% |
| 30+ | 431 | 0.54 | -43 | 25% |

The |z|-matched random baseline lost more than the entries on NQ and ES
(-128 and -66 USD a trade) and about the same on GC, so the entries still
carry some information relative to random bars at the same deviation;
that information is not worth the stop-and-target geometry it is traded
with, and it is not an edge.

The seen year (November 2025 to November 2026, looked at before the
protocol) shows NQ +29 USD a trade with an interval of [-298, +493]; ES
and GC negative. It is reported for completeness and carries no evidential
weight.

## 4. The OTE family

The lesson video's Optimal Trade Entry rules (fib retracement of an
impulsive leg, tap of 0.5 or 0.705, consolidation at the level, entry on
its break with displacement, stop beyond the box, target at the leg's
extreme or its expansion, or trail after expansion, higher-timeframe bias
gate) were extracted from the transcript and frames
(`docs/ote_lesson_extraction.md`), implemented without look-ahead, and
tested on the same development years under their own pre-stated stopping
rule. Three grids, 234 cells, zero passes. The faithful detector, after
the review's fixes, prints at most 0.10 signals per regular session and
every all-signal cell loses after costs (-94 to -258 USD a trade), no
better than a random minute in the same session with the same stop and
target distances. Details and all three grids: `docs/results_ote_dev.md`.

## 5. What this does and does not show

* The website's engine is described, not disclosed. What was tested is a
  faithful implementation of every stated ingredient with standard
  quantitative choices where the site is silent, and the result is
  specific to those choices. A differently specified engine could behave
  differently; nothing here says the site's own levels do or do not work.
* The one effect the development and validation years agreed on, a fade
  of the first minutes of the session toward the session VWAP on NQ,
  reversed in 2024-2025. That is the usual fate of an effect found by
  selection on a few years of one instrument, and the protocol was built
  to expose exactly that.
* The costed numbers are for one contract with fixed USD friction; the
  scale-free rows (net per rho) tell the same story in every period, so
  the conclusion does not depend on the price level.
* The hold-out is consumed. Any revised engine (for instance one whose
  ladder is warm-started at the open from the prior session's dispersion,
  the main design flaw the audit identified) needs new out-of-sample data,
  which from here means a forward period, not another pass over
  2024-2025.
* What the repository delivers: the engine and its tests (89 passing), the
  free-data clients, the research harness (costed overlay, session-level
  bootstrap, matched nulls, protocol phases), the OTE detector, and a
  research record that can be re-run end to end with the commands in the
  README and `docs/protocol.md`.

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

TO FILL AFTER THE HOLD-OUT.

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

## 3. Hold-out

TO FILL.

## 4. The OTE family

TO FILL.

## 5. What this does and does not show

TO FILL.

# OTE family: development-phase result (NQ 2018-2021)

Recorded 10 November 2026. Rules and the stopping rule are in
docs/protocol.md, amendment 5 (first two grids) and amendment 7 (the grid
after the fidelity review), each written before the grid it governs was
read. Data: 1,395,092 one-minute NQ bars, 1,030 regular sessions. Costs:
2.50 USD per side plus one tick of slippage per side, paid in the fills.
Inference: session-level, 5-session block bootstrap. Raw grids are in
`docs/record/ote_dev_grid{1,2,3}.csv`.

**Outcome: null on development, three times.** No cell of any grid met the
pre-stated bar (at least 0.3 trades per session, session-mean interval
above zero, annualised session Sharpe at least 0.7). The family does not
proceed to validation or hold-out.

## Grid 3: the faithful detector (after the independent review)

The review found no look-ahead and five fidelity gaps; the fixes are in
amendment 7 (box at the tapped level, small next to the leg and sideways;
a tapped leg dies once price runs past its extreme; four-hour
break-of-structure bias; an "expand then trail" management; corrected
nulls). With the box tied to the level the setup is rare: 19 to 106
signals in four years depending on leg timeframe, tap level and trigger,
at most 0.10 per session, so the frequency bar alone excludes every cell.
The per-trade numbers are reported anyway.

| Leg | Tap | Trigger | Signals | Aligned (4h) | Counter | BOS triggers | Median reward:risk | Median box / leg |
|---|---|---|---|---|---|---|---|---|
| 5 min | 0.5 | range break | 53 | 20 | 33 | 0 | 1.38 | 0.17 |
| 5 min | 0.705 | range break | 35 | 10 | 25 | 0 | 2.01 | 0.17 |
| 5 min | 0.5 | range or BOS | 106 | 45 | 61 | 54 | 1.04 | |
| 5 min | 0.705 | range or BOS | 75 | 32 | 43 | 41 | 1.29 | |
| 15 min | 0.5 | range break | 31 | 14 | 17 | 0 | 1.38 | 0.17 |
| 15 min | 0.705 | range break | 19 | 9 | 10 | 0 | 2.29 | 0.18 |
| 15 min | 0.5 | range or BOS | 68 | 34 | 34 | 38 | 1.17 | |
| 15 min | 0.705 | range or BOS | 45 | 24 | 21 | 27 | 1.72 | |

All signals, target at the 0.0 level, stop beyond the box, 180-bar limit,
flat at the close (USD per contract):

| Leg | Tap | Trigger | Trades | Hit | Net/trade | Session mean | 95% interval | Sharpe | Random-minute null, same geometry: P(null >= actual) | Flipped direction, net/session |
|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 0.5 | range break | 52 | 0.25 | -228 | -11.5 | [-22.2, -2.1] | -1.06 | 1.00 | +5.6 |
| 5 | 0.705 | range break | 35 | 0.34 | -183 | -6.2 | [-17.6, +4.1] | -0.54 | 0.70 | +11.5 |
| 5 | 0.5 | range or BOS | 103 | 0.42 | -175 | -17.5 | [-32.0, -3.6] | -1.22 | 1.00 | +9.9 |
| 5 | 0.705 | range or BOS | 73 | 0.51 | -94 | -6.6 | [-20.5, +6.5] | -0.48 | 0.80 | +11.6 |
| 15 | 0.5 | range break | 30 | 0.30 | -258 | -7.5 | [-15.8, +0.2] | -0.93 | 0.98 | -1.0 |
| 15 | 0.705 | range break | 19 | 0.37 | -141 | -2.6 | [-11.9, +8.9] | -0.24 | 0.39 | +3.9 |
| 15 | 0.5 | range or BOS | 66 | 0.44 | -233 | -14.9 | [-27.7, -2.9] | -1.19 | 1.00 | +2.6 |
| 15 | 0.705 | range or BOS | 44 | 0.48 | -147 | -6.3 | [-18.0, +7.0] | -0.48 | 0.57 | +6.5 |

* Every all-signal cell loses, several significantly, and most do worse
  than a random minute in the same session with the same stop and target
  distances (the random null, 100 draws, is itself slightly negative
  because of costs).
* The flipped direction, same bars and mirrored geometry, is positive in
  seven of eight cells. That is an observation on consumed development data,
  not a tested hypothesis.
* The same box break with no retracement requirement (tap level 0, box
  anywhere) loses the same way (net per trade -127 to -180 USD), so the
  retracement is not what hurts; box breakouts after a leg on NQ one-minute
  bars simply do not follow through at these horizons.
* The four-hour bias splits do not rescue it: means over all cells are
  -161 USD per trade aligned, -153 counter, -177 all. The 60-minute state
  (diagnostic only) is worse when aligned and roughly flat when counter.
* Management does not rescue it either: means over all cells -172 (target
  at the extreme), -141 (expansion), -134 (15-bar trail), -208 (expand
  then trail, held overnight; 100% of those exits were on the trailed
  stop).
* 11 of 92 cells have a positive session mean; none has an interval above
  zero; the highest Sharpe of any cell is 0.36 on 21 trades. Amendment 7
  pre-registers 96 cells; the four for 15-minute legs, tap 0.705, range
  break, aligned were not computed because the grid script skips any set
  with fewer than 10 signals and that set has 9 (its nulls are absent for
  the same reason). That floor was not pre-registered; at 9 signals in
  1,030 sessions the set fails the frequency bar in any case.

## Grids 1 and 2: the first detector (before the review)

Kept in the record because they were consumed looks. The first detector
let the consolidation form anywhere after the tap and let the leg survive
price running past its extreme; a quarter of its signals fired after the
move had already resumed, with the target behind the entry. It printed
464 signals (5-minute legs, tap 0.5) and 259 (tap 0.705) in four years,
0.45 and 0.25 per session.

| Grid | Cells | Best cell | Trades | Net/trade | Session mean | Sharpe | Cells passing |
|---|---|---|---|---|---|---|---|
| 1 (range break, 5-min legs, 60-minute HH/HL bias) | 40 | tap 0.705, aligned, range stop, expansion target, H 60 | 70 | +91 | +6.2 [-3.1, +16.0] | 0.58 | 0 |
| 2 (adds BOS trigger, 15-min legs, trailing) | 96 | 5-min, tap 0.5, range break, counter-trend, expansion | 152 | +132 | +19.4 [-3.5, +40.9] | 0.85 | 0 |

In grid 2, 25 of 96 cells had a positive session mean, none with an
interval above zero: 15 counter-trend under the 60-minute HH/HL bias, 9
aligned and 1 all-signal. The five largest (+10 to +19 USD per session,
Sharpe 0.53 to 0.85) were all counter-trend at tap 0.5 on 5-minute legs,
the setup the lesson warns against; the best aligned cell (5-min, tap
0.705, range break, expansion target) made +58 USD per trade, +3.9 per
session [-8.3, +16.3], Sharpe 0.28 on 70 trades. The review established
that bias was undefined for 41% of signals and is not the narrator's
reading, which is why it was replaced.

## Reading

The lesson's rules, implemented as stated and checked by an independent
review for fidelity and look-ahead, do not produce a tradable edge on NQ
one-minute data in 2018-2021 at any of the examined settings. The faithful
setup is rare (about one to two a month in regular hours) and loses after
costs, in both management styles the narrator describes (target the 0.0
level or its expansion; trail after expansion). The narrator's examples
are Globex and pre-market trades on 5- and 15-minute charts held for days;
the regular-hours, one-contract, costed replay here is the nearest
testable form of those rules and it is null.

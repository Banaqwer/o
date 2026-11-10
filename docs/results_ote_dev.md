# OTE family: development-phase result (NQ 2018-2021)

Recorded 10 November 2026. Rules and the stopping rule are in
docs/protocol.md, amendment 5, written before this grid was read. Data:
1,395,092 one-minute NQ bars, 1,030 regular sessions. Costs: 2.50 USD per
side plus one tick of slippage per side. Inference: session-level, 5-session
block bootstrap.

## Signal counts

| Leg timeframe | Tap | Trigger | Signals | Bias-aligned | Neutral | Counter | BOS triggers |
|---|---|---|---|---|---|---|---|
| 5 min | 0.5 | range break | 464 | 121 | 191 | 152 | 0 |
| 5 min | 0.5 | range or BOS | 490 | 129 | 201 | 160 | 43 |
| 5 min | 0.705 | range break | 259 | 70 | 108 | 81 | 0 |
| 5 min | 0.705 | range or BOS | 278 | 76 | 116 | 86 | 23 |
| 15 min | 0.5 | range break | 189 | 58 | 74 | 57 | 0 |
| 15 min | 0.5 | range or BOS | 201 | 60 | 77 | 64 | 36 |
| 15 min | 0.705 | range break | 105 | 32 | 44 | 29 | 0 |
| 15 min | 0.705 | range or BOS | 113 | 34 | 47 | 32 | 13 |

Even without the bias gate the family prints under half a signal per
session; the lesson's own filters (aligned bias, 0.705 tap) leave 17 to 30
trades a year.

## Stopping rule

Cells with at least 0.3 trades per session, a session-mean interval above
zero and Sharpe at least 0.7: **none of 96**. The OTE family is null on
development and does not proceed to validation.

## Cells with at least 0.3 trades per session, by Sharpe

| leg | touch | conf | set | mgmt | trades | trades_per_session | hit_rate | avg_net | session_mean | session_ci_lo | session_ci_hi | sharpe | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 0.50 | range_break | all | trail | 464 | 0.45 | 0.38 | 8.04 | 3.62 | -25.83 | 29.83 | 0.12 | 1.04 |
| 5 | 0.50 | range_or_bos | all | trail | 490 | 0.48 | 0.37 | -10.67 | -5.07 | -33.17 | 23.94 | -0.17 | 0.96 |
| 5 | 0.50 | range_break | all | expansion | 464 | 0.45 | 0.39 | -28.02 | -12.62 | -53.80 | 24.33 | -0.35 | 0.92 |
| 5 | 0.50 | range_break | not-counter | trail | 312 | 0.30 | 0.38 | -36.54 | -11.07 | -31.96 | 8.26 | -0.52 | 0.84 |
| 5 | 0.50 | range_or_bos | all | expansion | 490 | 0.48 | 0.38 | -49.41 | -23.51 | -62.15 | 13.79 | -0.63 | 0.86 |
| 5 | 0.50 | range_break | all | extreme | 464 | 0.45 | 0.48 | -42.88 | -19.32 | -48.15 | 8.21 | -0.65 | 0.85 |
| 5 | 0.50 | range_or_bos | not-counter | trail | 330 | 0.32 | 0.37 | -49.21 | -15.77 | -36.29 | 5.52 | -0.70 | 0.80 |
| 5 | 0.50 | range_or_bos | all | extreme | 490 | 0.48 | 0.47 | -69.43 | -33.03 | -61.48 | -6.96 | -1.08 | 0.77 |
| 5 | 0.50 | range_break | not-counter | expansion | 312 | 0.30 | 0.36 | -105.81 | -32.05 | -66.99 | -2.66 | -1.11 | 0.71 |
| 5 | 0.50 | range_break | not-counter | extreme | 312 | 0.30 | 0.47 | -97.36 | -29.49 | -53.63 | -8.40 | -1.29 | 0.68 |
| 5 | 0.50 | range_or_bos | not-counter | expansion | 330 | 0.32 | 0.36 | -121.05 | -38.78 | -73.75 | -7.56 | -1.30 | 0.67 |
| 5 | 0.50 | range_or_bos | not-counter | extreme | 330 | 0.32 | 0.46 | -118.62 | -38.00 | -64.04 | -17.44 | -1.58 | 0.63 |

## Best cells at any frequency

| leg | touch | conf | set | mgmt | trades | trades_per_session | hit_rate | avg_net | session_mean | session_ci_lo | session_ci_hi | sharpe | profit_factor |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 0.50 | range_break | counter | expansion | 152 | 0.15 | 0.45 | 131.64 | 19.43 | -3.48 | 40.92 | 0.85 | 1.45 |
| 5 | 0.50 | range_break | counter | trail | 152 | 0.15 | 0.38 | 99.55 | 14.69 | -1.57 | 33.99 | 0.74 | 1.46 |
| 5 | 0.50 | range_or_bos | counter | expansion | 160 | 0.16 | 0.43 | 98.33 | 15.27 | -6.92 | 36.88 | 0.66 | 1.33 |
| 5 | 0.50 | range_break | counter | extreme | 152 | 0.15 | 0.51 | 68.94 | 10.17 | -7.69 | 30.67 | 0.54 | 1.28 |
| 5 | 0.50 | range_or_bos | counter | trail | 160 | 0.16 | 0.36 | 68.83 | 10.69 | -5.85 | 28.93 | 0.53 | 1.30 |
| 5 | 0.70 | range_break | aligned | expansion | 70 | 0.07 | 0.44 | 57.83 | 3.93 | -8.32 | 16.33 | 0.28 | 1.22 |
| 5 | 0.50 | range_or_bos | counter | extreme | 160 | 0.16 | 0.49 | 32.01 | 4.97 | -13.71 | 24.82 | 0.26 | 1.12 |
| 5 | 0.70 | range_or_bos | aligned | expansion | 76 | 0.07 | 0.46 | 47.66 | 3.52 | -9.02 | 16.13 | 0.24 | 1.18 |

## Means over all cells by bias category

| set | avg_net | sharpe | hit_rate |
|---|---|---|---|
| aligned | -19.13 | -0.12 | 0.45 |
| all | -54.75 | -0.50 | 0.39 |
| counter | 14.46 | 0.11 | 0.37 |
| not-counter | -85.54 | -0.74 | 0.39 |

## Reading

* The all-signal and bias-aligned sets lose after costs under every
  management rule; trailing loses least.
* The only positive point estimates are counter-trend signals, the exact
  setup the lesson warns against (fading a higher-timeframe trend). With
  152 trades in four years and intervals that include zero, this is not
  evidence of an edge either; it is evidence that the 60-minute structure
  bias used here does not carry the information the narrator attributes to
  "higher timeframe bias", or that the lesson's bias rule is wrong.
* The independent fidelity review (docs/results_* to follow) decides
  whether a faithful-but-different bias definition is a legitimate fix to
  re-run, or a new hypothesis that would need its own pre-registration.

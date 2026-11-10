# Development phase: NQ 2018-01-01 to 2022-01-01

1395092 bars incl. warm-up, 1030 sessions, 7879 level tests, replay 247s.

## Reversion label

Amended label: 1 rho favourable before 1 rho adverse within 60 bars, measured from the next bar's open. Labelled events: 7320 (92.9% of tests). Base rate = 0.436. (Original from-level label base rate 0.466, shown alongside for the record.)

## Components by tercile (development data)

| component | tercile | n | p_fav_from_entry | p_fav_from_level | reverted60 |
|---|---|---|---|---|---|
| c_confluence | low | 2627 | 0.424 | 0.455 | 0.611 |
| c_confluence | mid | 2626 | 0.440 | 0.461 | 0.587 |
| c_confluence | high | 2626 | 0.444 | 0.484 | 0.550 |
| c_overshoot | low | 2635 | 0.432 | 0.417 | 0.563 |
| c_overshoot | mid | 2621 | 0.450 | 0.468 | 0.607 |
| c_overshoot | high | 2623 | 0.427 | 0.509 | 0.578 |
| c_divergence | low | 2635 | 0.437 | 0.285 | 0.520 |
| c_divergence | mid | 2618 | 0.428 | 0.415 | 0.541 |
| c_divergence | high | 2626 | 0.442 | 0.696 | 0.687 |
| c_climax | low | 2630 | 0.404 | 0.488 | 0.693 |
| c_climax | mid | 2623 | 0.428 | 0.448 | 0.650 |
| c_climax | high | 2626 | 0.477 | 0.463 | 0.405 |
| c_regime | low | 2627 | 0.445 | 0.384 | 0.587 |
| c_regime | mid | 2626 | 0.433 | 0.481 | 0.597 |
| c_regime | high | 2626 | 0.429 | 0.544 | 0.564 |
| c_ladder | low | 3055 | 0.459 | 0.507 | 0.385 |
| c_ladder | mid | 2198 | 0.454 | 0.429 | 0.581 |
| c_ladder | high | 2626 | 0.398 | 0.455 | 0.814 |

## Fitted weights on the amended label (L2 logistic, grouped 5-fold CV)

lambda = 100.0; CV log-loss by lambda: 0.3: 0.6832, 1.0: 0.6832, 3.0: 0.6832, 10.0: 0.6832, 30.0: 0.6832, 100.0: 0.6831; intercept-only log-loss 0.6849; gain 0.0018; rule needs 0.005.

| feature | weight |
|---|---|
| c_confluence | 0.0861 |
| c_overshoot | -0.7653 |
| c_divergence | 0.2521 |
| c_climax | 0.5170 |
| c_regime | -0.0901 |
| c_ladder | -0.2693 |
| bias | 0.2229 |

**Decision: hand-set weights kept.** Hand-set weights: c_confluence=0.60, c_overshoot=0.80, c_divergence=0.90, c_climax=0.50, c_regime=0.70, c_ladder=0.60, bias=-1.00.

## Calibration of the fitted score by decile (IN-SAMPLE on development data)

| decile | n | p_fav_first | edge15_sigma | reverted60 |
|---|---|---|---|---|
| 1.000 | 788.000 | 0.349 | 0.781 | 0.843 |
| 2.000 | 788.000 | 0.393 | 0.694 | 0.811 |
| 3.000 | 788.000 | 0.401 | 0.231 | 0.750 |
| 4.000 | 788.000 | 0.446 | 0.388 | 0.702 |
| 5.000 | 788.000 | 0.403 | 0.164 | 0.613 |
| 6.000 | 787.000 | 0.474 | 0.226 | 0.545 |
| 7.000 | 788.000 | 0.477 | 0.119 | 0.491 |
| 8.000 | 788.000 | 0.459 | 0.145 | 0.406 |
| 9.000 | 788.000 | 0.506 | 0.219 | 0.363 |
| 10.000 | 788.000 | 0.474 | 0.580 | 0.303 |

## Overlay on development data (hand-set entries, target anchor, stated costs, USD per contract)

| name | sessions | trades | trades_per_session | hit_rate | avg_net | session_mean | session_ci_lo | session_ci_hi | sharpe | max_dd | profit_factor | pct_sessions_positive | exit_stop | exit_target |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| entries stop 2.0 H 15 | 1030 | 3165 | 3.07 | 0.47 | -22.10 | -67.92 | -110.10 | -25.52 | -1.59 | -70742.34 | 0.82 | 0.35 | 0.35 | 0.34 |
| entries stop 2.0 H 15 09:30-12:00 | 1030 | 2807 | 2.73 | 0.48 | -17.34 | -47.26 | -87.23 | -5.65 | -1.17 | -49454.81 | 0.85 | 0.34 | 0.39 | 0.38 |
| entries stop 2.0 H 60 | 1030 | 3165 | 3.07 | 0.47 | -10.94 | -33.63 | -96.30 | 28.09 | -0.53 | -45914.32 | 0.93 | 0.36 | 0.43 | 0.40 |
| entries stop 2.0 H 60 09:30-12:00 | 1030 | 2807 | 2.73 | 0.47 | -2.00 | -5.46 | -61.38 | 51.54 | -0.10 | -28911.44 | 0.99 | 0.35 | 0.46 | 0.44 |
| entries stop 3.0 H 15 | 1030 | 3165 | 3.07 | 0.53 | -19.33 | -59.41 | -102.08 | -16.71 | -1.33 | -62723.99 | 0.85 | 0.37 | 0.25 | 0.39 |
| entries stop 3.0 H 15 09:30-12:00 | 1030 | 2807 | 2.73 | 0.54 | -14.12 | -38.48 | -78.68 | 2.82 | -0.90 | -43301.26 | 0.89 | 0.37 | 0.28 | 0.44 |
| entries stop 3.0 H 60 | 1030 | 3165 | 3.07 | 0.54 | -5.00 | -15.36 | -84.82 | 49.28 | -0.23 | -37558.41 | 0.97 | 0.40 | 0.32 | 0.47 |
| entries stop 3.0 H 60 09:30-12:00 | 1030 | 2807 | 2.73 | 0.55 | 4.50 | 12.27 | -48.88 | 72.95 | 0.20 | -29062.12 | 1.03 | 0.39 | 0.35 | 0.51 |
| entries stop 5.0 H 15 | 1030 | 3165 | 3.07 | 0.58 | -13.85 | -42.57 | -89.88 | 2.58 | -0.87 | -55100.98 | 0.89 | 0.42 | 0.14 | 0.44 |
| entries stop 5.0 H 15 09:30-12:00 | 1030 | 2807 | 2.73 | 0.60 | -8.59 | -23.41 | -69.11 | 18.73 | -0.50 | -39521.67 | 0.93 | 0.42 | 0.16 | 0.49 |
| entries stop 5.0 H 60 | 1030 | 3165 | 3.07 | 0.61 | 3.38 | 10.39 | -71.75 | 83.48 | 0.14 | -32778.56 | 1.02 | 0.45 | 0.21 | 0.52 |
| entries stop 5.0 H 60 09:30-12:00 | 1030 | 2807 | 2.73 | 0.62 | 13.87 | 37.79 | -32.31 | 106.17 | 0.54 | -29248.38 | 1.08 | 0.44 | 0.24 | 0.57 |
| all tests stop 3 H 60 | 1030 | 7879 | 7.65 | 0.53 | -23.82 | -182.23 | -289.86 | -77.92 | -1.59 | -206116.52 | 0.87 | 0.45 | 0.30 | 0.42 |
| matched baseline (entries) stop 3 H 60 | 1030 | 3149 | 3.06 | 0.49 | -32.93 | -100.68 | -248.47 | 42.91 | -0.67 | -141972.68 | 0.88 | 0.42 | 0.10 | 0.13 |

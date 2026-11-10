# Development phase: NQ 2018-01-01 to 2022-01-01

1395092 bars incl. warm-up, 1030 sessions, 7879 level tests, replay 359s.

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
| 1.000 | 788.000 | 0.349 | 0.292 | 0.843 |
| 2.000 | 788.000 | 0.393 | -0.025 | 0.811 |
| 3.000 | 788.000 | 0.401 | -0.137 | 0.750 |
| 4.000 | 788.000 | 0.446 | 0.136 | 0.702 |
| 5.000 | 788.000 | 0.403 | -0.049 | 0.613 |
| 6.000 | 787.000 | 0.474 | 0.015 | 0.545 |
| 7.000 | 788.000 | 0.477 | -0.071 | 0.491 |
| 8.000 | 788.000 | 0.459 | -0.109 | 0.406 |
| 9.000 | 788.000 | 0.506 | -0.028 | 0.363 |
| 10.000 | 788.000 | 0.474 | -0.000 | 0.303 |

## Overlay on development data (hand-set entries, target anchor, stated costs, USD per contract)

| name | sessions | trades | trades_per_session | hit_rate | avg_net | session_mean | session_ci_lo | session_ci_hi | sharpe | max_dd | profit_factor | pct_sessions_positive | exit_stop | exit_target | gross_per_rho | net_per_rho |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| entries stop 2.0 H 15 | 1030 | 3151 | 3.06 | 0.50 | -12.01 | -36.75 | -78.69 | 5.21 | -0.86 | -40434.45 | 0.90 | 0.37 | 0.35 | 0.34 | -0.04 | -0.07 |
| entries stop 2.0 H 15 09:30-12:00 | 1030 | 2796 | 2.71 | 0.51 | -7.42 | -20.16 | -60.32 | 20.98 | -0.50 | -28072.78 | 0.93 | 0.36 | 0.39 | 0.39 | -0.02 | -0.05 |
| entries stop 2.0 H 60 | 1030 | 3151 | 3.06 | 0.49 | -0.76 | -2.31 | -64.48 | 58.93 | -0.04 | -30262.16 | 0.99 | 0.38 | 0.42 | 0.40 | 0.02 | -0.00 |
| entries stop 2.0 H 60 09:30-12:00 | 1030 | 2796 | 2.71 | 0.50 | 7.97 | 21.64 | -33.59 | 78.65 | 0.38 | -22199.22 | 1.06 | 0.37 | 0.46 | 0.44 | 0.09 | 0.06 |
| entries stop 3.0 H 15 | 1030 | 3162 | 3.07 | 0.56 | -9.15 | -28.09 | -71.19 | 14.35 | -0.63 | -36495.52 | 0.93 | 0.40 | 0.25 | 0.39 | -0.02 | -0.05 |
| entries stop 3.0 H 15 09:30-12:00 | 1030 | 2807 | 2.73 | 0.57 | -4.12 | -11.23 | -51.76 | 30.25 | -0.26 | -24170.43 | 0.97 | 0.39 | 0.28 | 0.44 | 0.01 | -0.03 |
| entries stop 3.0 H 60 | 1030 | 3162 | 3.07 | 0.57 | 5.31 | 16.29 | -52.57 | 81.59 | 0.24 | -33347.69 | 1.03 | 0.41 | 0.32 | 0.47 | 0.06 | 0.03 |
| entries stop 3.0 H 60 09:30-12:00 | 1030 | 2807 | 2.73 | 0.58 | 14.50 | 39.52 | -21.67 | 100.22 | 0.63 | -26442.12 | 1.09 | 0.40 | 0.35 | 0.51 | 0.14 | 0.10 |
| entries stop 5.0 H 15 | 1030 | 3162 | 3.07 | 0.61 | -3.67 | -11.25 | -58.47 | 33.77 | -0.23 | -32330.98 | 0.97 | 0.44 | 0.14 | 0.44 | 0.01 | -0.02 |
| entries stop 5.0 H 15 09:30-12:00 | 1030 | 2807 | 2.73 | 0.63 | 1.41 | 3.84 | -42.07 | 45.82 | 0.08 | -20232.27 | 1.01 | 0.43 | 0.16 | 0.49 | 0.05 | 0.01 |
| entries stop 5.0 H 60 | 1030 | 3162 | 3.07 | 0.64 | 13.77 | 42.28 | -39.79 | 115.51 | 0.56 | -29001.03 | 1.08 | 0.47 | 0.21 | 0.52 | 0.11 | 0.08 |
| entries stop 5.0 H 60 09:30-12:00 | 1030 | 2807 | 2.73 | 0.65 | 23.87 | 65.04 | -4.78 | 132.53 | 0.92 | -26188.38 | 1.14 | 0.45 | 0.24 | 0.57 | 0.21 | 0.17 |
| all tests stop 3 H 60 | 1030 | 7853 | 7.62 | 0.55 | -13.77 | -104.98 | -212.92 | -1.79 | -0.92 | -127449.02 | 0.92 | 0.47 | 0.30 | 0.42 | -0.04 | -0.06 |
| matched baseline (entries) stop 3 H 60 | 1030 | 3138 | 3.05 | 0.50 | -22.63 | -68.95 | -216.58 | 77.68 | -0.46 | -129727.68 | 0.92 | 0.43 | 0.10 | 0.13 | -0.03 | -0.04 |

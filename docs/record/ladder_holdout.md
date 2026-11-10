# Hold-out phase

Configuration frozen from development and validation: hand-set weights, q=0.6, stop=5.0 rho, target anchor, H=60. Run once per instrument.

## NQ holdout 2024-01-01..2025-11-01

3575 tests, 1447 entries, 474 sessions.

| name | sessions | trades | trades_per_session | hit_rate | avg_net | session_mean | session_ci_lo | session_ci_hi | sharpe | max_dd | profit_factor | pct_sessions_positive | exit_stop | exit_target | gross_per_rho | net_per_rho |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| stated costs | 474 | 1447 | 3.05 | 0.63 | -51.53 | -157.31 | -338.29 | 22.81 | -1.30 | -91987.67 | 0.86 | 0.41 | 0.21 | 0.52 | -0.14 | -0.16 |
| zero costs | 474 | 1447 | 3.05 | 0.64 | -35.77 | -109.21 | -291.18 | 71.49 | -0.90 | -72434.94 | 0.90 | 0.42 | 0.21 | 0.53 | -0.11 | -0.11 |
| double costs | 474 | 1447 | 3.05 | 0.62 | -66.42 | -202.76 | -380.04 | -24.10 | -1.68 | -111820.42 | 0.82 | 0.39 | 0.21 | 0.52 | -0.17 | -0.20 |
| 2 ticks per side | 474 | 1447 | 3.05 | 0.62 | -61.42 | -187.50 | -365.12 | -9.42 | -1.55 | -105150.42 | 0.83 | 0.39 | 0.21 | 0.52 | -0.17 | -0.19 |
| 3 ticks per side | 474 | 1447 | 3.05 | 0.61 | -76.58 | -233.78 | -407.74 | -50.83 | -1.94 | -123068.82 | 0.79 | 0.38 | 0.22 | 0.51 | -0.22 | -0.23 |
| matched baseline, stated costs | 474 | 1440 | 3.04 | 0.52 | -128.05 | -389.01 | -1593.97 | 386.17 | -0.56 | -289011.30 | 0.80 | 0.43 | 0.04 | 0.15 | -0.13 | -0.13 |
| all tests, stated costs | 474 | 3572 | 7.54 | 0.62 | -60.64 | -456.98 | -804.16 | -66.86 | -1.63 | -236775.71 | 0.85 | 0.49 | 0.19 | 0.50 | -0.14 | -0.15 |
| secondary: 09:30-12:00 ET signals only, stated costs | 474 | 1249 | 2.64 | 0.65 | -49.02 | -129.17 | -284.59 | 38.90 | -1.15 | -81855.66 | 0.86 | 0.41 | 0.24 | 0.58 | -0.17 | -0.19 |

By minute since the open (descriptive):

| minutes_since_open | trades | hit_rate | avg_net | total_net | share_of_total_net |
|---|---|---|---|---|---|
| [0, 5) | 653 | 0.61 | -99.72 | -65118.81 | 0.87 |
| [5, 30) | 363 | 0.75 | 24.78 | 8996.05 | -0.12 |
| 30+ | 431 | 0.54 | -42.79 | -18442.71 | 0.25 |

By year (all sessions of the year, zero when no trade):

| year | sessions | trades | hit_rate | avg_net | session_mean | sharpe | max_dd | net_per_rho |
|---|---|---|---|---|---|---|---|---|
| 2024.00 | 259.00 | 842.00 | 0.63 | -47.10 | -153.13 | -1.39 | -61602.88 | -0.15 |
| 2025.00 | 215.00 | 605.00 | 0.63 | -57.69 | -162.34 | -1.22 | -50392.32 | -0.16 |

By previous-close VIX tercile:

| ctx_vix_z | trades | hit_rate | avg_net | total_net |
|---|---|---|---|---|
| low VIX | 484.00 | 0.64 | -19.41 | -9394.94 |
| mid VIX | 481.00 | 0.63 | -48.66 | -23406.29 |
| high VIX | 482.00 | 0.61 | -86.65 | -41764.23 |

## NQ seen 2025-11-01..2026-11-09 (SEEN before protocol; not evidence)

1835 tests, 726 entries, 262 sessions.

| name | sessions | trades | trades_per_session | hit_rate | avg_net | session_mean | session_ci_lo | session_ci_hi | sharpe | max_dd | profit_factor | pct_sessions_positive | exit_stop | exit_target | gross_per_rho | net_per_rho |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| stated costs | 262 | 724 | 2.76 | 0.66 | 28.72 | 79.36 | -298.48 | 492.51 | 0.43 | -57168.16 | 1.06 | 0.45 | 0.20 | 0.54 | 0.06 | 0.05 |
| zero costs | 262 | 724 | 2.76 | 0.67 | 50.11 | 138.46 | -236.86 | 551.82 | 0.75 | -53433.16 | 1.10 | 0.45 | 0.19 | 0.54 | 0.09 | 0.09 |
| double costs | 262 | 724 | 2.76 | 0.65 | 16.40 | 45.32 | -325.87 | 459.96 | 0.25 | -60903.16 | 1.03 | 0.45 | 0.20 | 0.54 | 0.05 | 0.03 |
| 2 ticks per side | 262 | 724 | 2.76 | 0.65 | 21.40 | 59.14 | -311.81 | 473.45 | 0.32 | -59658.16 | 1.04 | 0.45 | 0.20 | 0.54 | 0.05 | 0.04 |
| 3 ticks per side | 262 | 724 | 2.76 | 0.65 | 11.40 | 31.51 | -339.93 | 446.36 | 0.17 | -62148.16 | 1.02 | 0.45 | 0.20 | 0.54 | 0.03 | 0.02 |
| matched baseline, stated costs | 262 | 722 | 2.76 | 0.52 | 158.39 | 436.48 | -236.89 | 1249.73 | 1.09 | -63953.87 | 1.26 | 0.39 | 0.03 | 0.15 | 0.12 | 0.11 |
| all tests, stated costs | 262 | 1832 | 6.99 | 0.63 | 1.36 | 9.53 | -668.60 | 730.72 | 0.03 | -72600.80 | 1.00 | 0.52 | 0.18 | 0.50 | 0.01 | 0.00 |
| secondary: 09:30-12:00 ET signals only, stated costs | 262 | 658 | 2.51 | 0.67 | 26.45 | 66.43 | -291.60 | 453.14 | 0.38 | -52998.64 | 1.05 | 0.44 | 0.22 | 0.59 | 0.07 | 0.06 |

By minute since the open (descriptive):

| minutes_since_open | trades | hit_rate | avg_net | total_net | share_of_total_net |
|---|---|---|---|---|---|
| [0, 5) | 367 | 0.68 | -40.64 | -14914.53 | -0.72 |
| [5, 30) | 182 | 0.74 | 70.62 | 12852.96 | 0.62 |
| 30+ | 175 | 0.54 | 130.59 | 22853.60 | 1.10 |

By year (all sessions of the year, zero when no trade):

| year | sessions | trades | hit_rate | avg_net | session_mean | sharpe | max_dd | net_per_rho |
|---|---|---|---|---|---|---|---|---|
| 2025.00 | 42.00 | 124.00 | 0.64 | 75.36 | 222.48 | 1.11 | -16426.20 | 0.18 |
| 2026.00 | 220.00 | 600.00 | 0.66 | 19.08 | 52.04 | 0.29 | -57168.16 | 0.03 |

By previous-close VIX tercile:

| ctx_vix_z | trades | hit_rate | avg_net | total_net |
|---|---|---|---|---|
| low VIX | 245.00 | 0.62 | -33.55 | -8220.95 |
| mid VIX | 238.00 | 0.68 | 124.03 | 29518.87 |
| high VIX | 241.00 | 0.68 | -2.10 | -505.89 |

## ES holdout 2024-01-01..2025-11-01

3796 tests, 1523 entries, 474 sessions.

| name | sessions | trades | trades_per_session | hit_rate | avg_net | session_mean | session_ci_lo | session_ci_hi | sharpe | max_dd | profit_factor | pct_sessions_positive | exit_stop | exit_target | gross_per_rho | net_per_rho |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| stated costs | 474 | 1518 | 3.20 | 0.63 | -33.94 | -108.69 | -201.12 | -17.11 | -1.76 | -61267.51 | 0.81 | 0.41 | 0.17 | 0.56 | -0.17 | -0.20 |
| zero costs | 474 | 1518 | 3.20 | 0.66 | -5.44 | -17.41 | -112.68 | 76.15 | -0.28 | -29221.04 | 0.97 | 0.43 | 0.16 | 0.57 | -0.03 | -0.03 |
| double costs | 474 | 1518 | 3.20 | 0.58 | -63.58 | -203.61 | -296.69 | -113.73 | -3.29 | -99990.23 | 0.66 | 0.38 | 0.17 | 0.54 | -0.32 | -0.38 |
| 2 ticks per side | 474 | 1518 | 3.20 | 0.59 | -58.58 | -187.60 | -279.48 | -97.41 | -3.03 | -93410.23 | 0.68 | 0.39 | 0.17 | 0.54 | -0.32 | -0.35 |
| 3 ticks per side | 474 | 1518 | 3.20 | 0.53 | -85.88 | -275.05 | -369.20 | -184.44 | -4.34 | -132053.37 | 0.57 | 0.37 | 0.18 | 0.52 | -0.48 | -0.51 |
| matched baseline, stated costs | 474 | 1522 | 3.21 | 0.49 | -65.75 | -211.12 | -608.93 | 115.14 | -0.95 | -120188.60 | 0.80 | 0.41 | 0.04 | 0.17 | -0.12 | -0.13 |
| all tests, stated costs | 474 | 3781 | 7.98 | 0.61 | -45.39 | -362.08 | -608.51 | -148.86 | -2.20 | -196835.65 | 0.77 | 0.44 | 0.15 | 0.51 | -0.20 | -0.23 |
| secondary: 09:30-12:00 ET signals only, stated costs | 474 | 1284 | 2.71 | 0.64 | -31.46 | -85.21 | -169.74 | -9.08 | -1.55 | -48600.33 | 0.81 | 0.41 | 0.19 | 0.62 | -0.20 | -0.24 |

By minute since the open (descriptive):

| minutes_since_open | trades | hit_rate | avg_net | total_net | share_of_total_net |
|---|---|---|---|---|---|
| [0, 5) | 471 | 0.60 | -52.80 | -24869.82 | 0.48 |
| [5, 30) | 450 | 0.73 | -8.81 | -3962.71 | 0.08 |
| 30+ | 597 | 0.57 | -38.00 | -22685.41 | 0.44 |

By year (all sessions of the year, zero when no trade):

| year | sessions | trades | hit_rate | avg_net | session_mean | sharpe | max_dd | net_per_rho |
|---|---|---|---|---|---|---|---|---|
| 2024.00 | 259.00 | 895.00 | 0.60 | -52.47 | -181.30 | -3.26 | -49042.41 | -0.35 |
| 2025.00 | 215.00 | 623.00 | 0.66 | -7.32 | -21.22 | -0.31 | -13483.96 | -0.04 |

By previous-close VIX tercile:

| ctx_vix_z | trades | hit_rate | avg_net | total_net |
|---|---|---|---|---|
| low VIX | 506.00 | 0.67 | -6.30 | -3186.44 |
| mid VIX | 506.00 | 0.60 | -41.35 | -20924.22 |
| high VIX | 506.00 | 0.61 | -54.16 | -27407.28 |

## ES seen 2025-11-01..2026-11-09 (SEEN before protocol; not evidence)

2060 tests, 827 entries, 262 sessions.

| name | sessions | trades | trades_per_session | hit_rate | avg_net | session_mean | session_ci_lo | session_ci_hi | sharpe | max_dd | profit_factor | pct_sessions_positive | exit_stop | exit_target | gross_per_rho | net_per_rho |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| stated costs | 262 | 823 | 3.14 | 0.63 | -25.12 | -78.90 | -259.07 | 131.60 | -0.91 | -49112.36 | 0.90 | 0.45 | 0.18 | 0.55 | -0.09 | -0.11 |
| zero costs | 262 | 823 | 3.14 | 0.65 | -0.59 | -1.86 | -185.84 | 209.65 | -0.02 | -39295.00 | 1.00 | 0.47 | 0.18 | 0.55 | -0.00 | -0.00 |
| double costs | 262 | 823 | 3.14 | 0.60 | -48.67 | -152.90 | -333.31 | 56.53 | -1.75 | -59697.74 | 0.81 | 0.43 | 0.18 | 0.53 | -0.17 | -0.22 |
| 2 ticks per side | 262 | 823 | 3.14 | 0.61 | -43.67 | -137.19 | -317.83 | 72.98 | -1.57 | -57872.74 | 0.83 | 0.44 | 0.18 | 0.53 | -0.17 | -0.19 |
| 3 ticks per side | 262 | 823 | 3.14 | 0.57 | -67.24 | -211.21 | -390.60 | -3.33 | -2.40 | -68761.60 | 0.75 | 0.43 | 0.18 | 0.52 | -0.28 | -0.30 |
| matched baseline, stated costs | 262 | 827 | 3.16 | 0.51 | 19.40 | 61.23 | -212.33 | 320.30 | 0.43 | -34805.58 | 1.07 | 0.44 | 0.05 | 0.16 | 0.04 | 0.03 |
| all tests, stated costs | 262 | 2053 | 7.84 | 0.62 | -7.94 | -62.19 | -369.09 | 301.19 | -0.37 | -30378.53 | 0.97 | 0.46 | 0.16 | 0.50 | -0.01 | -0.03 |
| secondary: 09:30-12:00 ET signals only, stated costs | 262 | 734 | 2.80 | 0.65 | -23.40 | -65.55 | -234.36 | 123.84 | -0.84 | -39637.02 | 0.90 | 0.43 | 0.20 | 0.59 | -0.10 | -0.13 |

By minute since the open (descriptive):

| minutes_since_open | trades | hit_rate | avg_net | total_net | share_of_total_net |
|---|---|---|---|---|---|
| [0, 5) | 328 | 0.67 | -0.77 | -252.52 | 0.01 |
| [5, 30) | 255 | 0.71 | -28.94 | -7380.89 | 0.36 |
| 30+ | 240 | 0.49 | -54.33 | -13038.19 | 0.63 |

By year (all sessions of the year, zero when no trade):

| year | sessions | trades | hit_rate | avg_net | session_mean | sharpe | max_dd | net_per_rho |
|---|---|---|---|---|---|---|---|---|
| 2025.00 | 42.00 | 116.00 | 0.57 | -168.78 | -466.14 | -6.16 | -19679.60 | -0.94 |
| 2026.00 | 220.00 | 707.00 | 0.64 | -1.55 | -4.97 | -0.06 | -35645.59 | -0.01 |

By previous-close VIX tercile:

| ctx_vix_z | trades | hit_rate | avg_net | total_net |
|---|---|---|---|---|
| low VIX | 275.00 | 0.60 | -16.04 | -4409.85 |
| mid VIX | 273.00 | 0.65 | 11.09 | 3026.29 |
| high VIX | 274.00 | 0.64 | -69.46 | -19031.30 |

## GC holdout 2024-01-01..2025-11-01

3914 tests, 1550 entries, 475 sessions.

| name | sessions | trades | trades_per_session | hit_rate | avg_net | session_mean | session_ci_lo | session_ci_hi | sharpe | max_dd | profit_factor | pct_sessions_positive | exit_stop | exit_target | gross_per_rho | net_per_rho |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| stated costs | 475 | 1549 | 3.26 | 0.65 | -28.44 | -92.73 | -200.59 | 23.18 | -1.12 | -48061.31 | 0.87 | 0.47 | 0.14 | 0.52 | -0.09 | -0.11 |
| zero costs | 475 | 1549 | 3.26 | 0.67 | -4.22 | -13.75 | -121.34 | 101.08 | -0.17 | -24766.03 | 0.98 | 0.49 | 0.13 | 0.53 | -0.02 | -0.02 |
| double costs | 475 | 1549 | 3.26 | 0.62 | -55.41 | -180.68 | -299.64 | -60.33 | -2.13 | -86216.83 | 0.75 | 0.44 | 0.14 | 0.51 | -0.18 | -0.22 |
| 2 ticks per side | 475 | 1549 | 3.26 | 0.63 | -50.41 | -164.38 | -282.20 | -43.99 | -1.94 | -78496.83 | 0.77 | 0.45 | 0.14 | 0.51 | -0.18 | -0.20 |
| 3 ticks per side | 475 | 1549 | 3.26 | 0.61 | -70.67 | -230.44 | -348.55 | -109.52 | -2.71 | -109778.66 | 0.70 | 0.43 | 0.14 | 0.51 | -0.26 | -0.28 |
| matched baseline, stated costs | 475 | 1541 | 3.24 | 0.53 | -2.02 | -6.56 | -152.79 | 165.17 | -0.05 | -31657.27 | 0.99 | 0.51 | 0.03 | 0.16 | 0.01 | -0.00 |
| all tests, stated costs | 475 | 3913 | 8.24 | 0.64 | -17.20 | -141.67 | -348.01 | 69.80 | -0.83 | -90254.41 | 0.92 | 0.54 | 0.13 | 0.50 | -0.04 | -0.06 |
| secondary: 09:30-12:00 ET signals only, stated costs | 475 | 1319 | 2.78 | 0.66 | -42.15 | -117.03 | -232.39 | -6.88 | -1.48 | -59183.91 | 0.81 | 0.47 | 0.16 | 0.58 | -0.17 | -0.20 |

By minute since the open (descriptive):

| minutes_since_open | trades | hit_rate | avg_net | total_net | share_of_total_net |
|---|---|---|---|---|---|
| [0, 5) | 260 | 0.72 | -59.36 | -15433.11 | 0.35 |
| [5, 30) | 584 | 0.68 | -66.09 | -38594.34 | 0.88 |
| 30+ | 705 | 0.59 | 14.16 | 9980.32 | -0.23 |

By year (all sessions of the year, zero when no trade):

| year | sessions | trades | hit_rate | avg_net | session_mean | sharpe | max_dd | net_per_rho |
|---|---|---|---|---|---|---|---|---|
| 2024.00 | 259.00 | 848.00 | 0.66 | -9.39 | -30.73 | -0.50 | -19817.12 | -0.05 |
| 2025.00 | 216.00 | 701.00 | 0.63 | -51.48 | -167.07 | -1.62 | -39506.64 | -0.16 |

By previous-close VIX tercile:

| ctx_vix_z | trades | hit_rate | avg_net | total_net |
|---|---|---|---|---|
| low VIX | 518.00 | 0.65 | 1.97 | 1021.67 |
| mid VIX | 515.00 | 0.66 | -33.28 | -17140.75 |
| high VIX | 516.00 | 0.64 | -54.12 | -27928.04 |

## GC seen 2025-11-01..2026-11-09 (SEEN before protocol; not evidence)

2545 tests, 1042 entries, 262 sessions.

| name | sessions | trades | trades_per_session | hit_rate | avg_net | session_mean | session_ci_lo | session_ci_hi | sharpe | max_dd | profit_factor | pct_sessions_positive | exit_stop | exit_target | gross_per_rho | net_per_rho |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| stated costs | 262 | 1040 | 3.97 | 0.67 | -2.93 | -11.63 | -350.28 | 328.05 | -0.06 | -58223.44 | 0.99 | 0.51 | 0.13 | 0.54 | 0.00 | -0.01 |
| zero costs | 262 | 1040 | 3.97 | 0.68 | 16.29 | 64.67 | -269.65 | 393.14 | 0.33 | -52147.34 | 1.04 | 0.52 | 0.13 | 0.54 | 0.03 | 0.03 |
| double costs | 262 | 1040 | 3.97 | 0.66 | -31.33 | -124.38 | -470.43 | 207.18 | -0.63 | -74754.68 | 0.93 | 0.49 | 0.13 | 0.53 | -0.04 | -0.05 |
| 2 ticks per side | 262 | 1040 | 3.97 | 0.66 | -26.33 | -104.53 | -449.53 | 226.76 | -0.53 | -71444.68 | 0.94 | 0.49 | 0.13 | 0.53 | -0.04 | -0.05 |
| 3 ticks per side | 262 | 1040 | 3.97 | 0.65 | -49.19 | -195.24 | -544.13 | 140.78 | -0.99 | -86162.44 | 0.90 | 0.48 | 0.13 | 0.53 | -0.08 | -0.09 |
| matched baseline, stated costs | 262 | 1040 | 3.97 | 0.51 | -139.32 | -553.03 | -1523.83 | 129.78 | -1.48 | -204403.38 | 0.77 | 0.47 | 0.03 | 0.13 | -0.11 | -0.12 |
| all tests, stated costs | 262 | 2541 | 9.70 | 0.64 | -55.92 | -542.29 | -1807.61 | 373.64 | -0.88 | -168711.69 | 0.90 | 0.49 | 0.13 | 0.50 | -0.08 | -0.08 |
| secondary: 09:30-12:00 ET signals only, stated costs | 262 | 859 | 3.28 | 0.69 | -33.94 | -111.29 | -427.20 | 193.92 | -0.61 | -61303.96 | 0.93 | 0.49 | 0.15 | 0.63 | -0.06 | -0.07 |

By minute since the open (descriptive):

| minutes_since_open | trades | hit_rate | avg_net | total_net | share_of_total_net |
|---|---|---|---|---|---|
| [0, 5) | 211 | 0.75 | -12.97 | -2736.73 | 0.90 |
| [5, 30) | 353 | 0.73 | -56.78 | -20042.16 | 6.58 |
| 30+ | 476 | 0.59 | 41.45 | 19732.29 | -6.48 |

By year (all sessions of the year, zero when no trade):

| year | sessions | trades | hit_rate | avg_net | session_mean | sharpe | max_dd | net_per_rho |
|---|---|---|---|---|---|---|---|---|
| 2025.00 | 42.00 | 180.00 | 0.73 | 110.33 | 472.84 | 3.12 | -15957.85 | 0.24 |
| 2026.00 | 220.00 | 860.00 | 0.65 | -26.63 | -104.12 | -0.51 | -58223.44 | -0.04 |

By previous-close VIX tercile:

| ctx_vix_z | trades | hit_rate | avg_net | total_net |
|---|---|---|---|---|
| low VIX | 353.00 | 0.67 | 24.83 | 8764.14 |
| mid VIX | 342.00 | 0.70 | 33.46 | 11444.41 |
| high VIX | 345.00 | 0.62 | -67.41 | -23255.15 |

## Summary

| instrument | period | sessions | trades | session_mean_usd | ci_lo | ci_hi | sharpe | hit_rate | avg_net | net_per_rho |
|---|---|---|---|---|---|---|---|---|---|---|
| NQ | holdout | 474 | 1447 | -157.31 | -338.29 | 22.81 | -1.30 | 0.63 | -51.53 | -0.16 |
| NQ | seen | 262 | 724 | 79.36 | -298.48 | 492.51 | 0.43 | 0.66 | 28.72 | 0.05 |
| ES | holdout | 474 | 1518 | -108.69 | -201.12 | -17.11 | -1.76 | 0.63 | -33.94 | -0.20 |
| ES | seen | 262 | 823 | -78.90 | -259.07 | 131.60 | -0.91 | 0.63 | -25.12 | -0.11 |
| GC | holdout | 475 | 1549 | -92.73 | -200.59 | 23.18 | -1.12 | 0.65 | -28.44 | -0.11 |
| GC | seen | 262 | 1040 | -11.63 | -350.28 | 328.05 | -0.06 | 0.67 | -2.93 | -0.01 |

# Research protocol (pre-registered)

Written 9 November 2026 before any bar earlier than November 2025 had been
examined. Everything below is fixed in advance; deviations, if any, are
logged in the results document with the reason.

## Question

Does the ATM-style reversal engine, applied to index and metals futures,
produce level tests whose subsequent reversion is (a) better than chance,
(b) better than a naive "fade distance from VWAP" rule at the same distance,
and (c) positive net of realistic costs under a plain execution overlay, on
data it has never been tuned on?

## Data

LSE `/vault` 1-minute continuous front-month candles with volume:
`NASDAQ100.F` (NQ), `SP500.F` (ES), `GOLD.F` (GC), 2018-01-01 to 2026-11-08.
Daily context from FRED (VIX, 10y-2y) and the French library, lagged one
session.

## Splits

| Set | Period | Use |
| --- | --- | --- |
| Development | 2018-01 to 2021-12 | All design decisions. Component diagnostics, weight fitting, sanity checks. May be looked at freely. |
| Validation | 2022-01 to 2023-12 | One pre-specified grid (below). Touched once. |
| Hold-out | 2024-01 to 2025-10 | Final chosen configuration only. Touched once. |
| Seen | 2025-11 to 2026-11 | Already examined with the hand-set engine; reported separately and flagged. |

Each replay starts three months before its period so rolling estimators
are warm; events inside the warm-up are discarded.

## Fixed definitions

* **Dispersion unit** `rho`: volume-weighted std of traded prices around
  session VWAP, floored by one-bar volatility (unchanged).
* **Reversion label** for weight fitting: within 60 bars or the session
  close, price moves 1 `rho` in the rung's direction before it moves
  1 `rho` against it (1), the reverse (0), neither (excluded).
* **Score features**: the six components the engine already computes
  (confluence, overshoot, divergence, climax, regime confidence, ladder
  context). No new features.
* **Weight fitting**: L2-regularised logistic regression on the development
  events, regularisation chosen by 5-fold cross-validation grouped by
  session. Fitted weights replace the hand-set `s_*` and `bias`. Signs are
  not forced.
* **Entry**: score at or above the rolling 500-event quantile `q`.
* **Execution overlay**: enter at the next bar's open after the test bar,
  toward the anchor. Stop at `stop_sigma x rho` beyond the level. Target at
  the anchor in force at the test. Time stop after `H` bars. Flat at the
  regular-session close. If stop and target print in the same bar the stop
  is assumed first. One contract per event; overlapping events are
  independent positions.
* **Costs**: commission 2.50 USD per side per contract plus one tick of
  slippage per side (NQ 5 USD, ES 12.50 USD, GC 10 USD per side).
  Sensitivity at zero and at double costs is reported.
* **Edge**: mean net P&L per session, with a 95% block-bootstrap interval
  (blocks of 5 sessions, 2,000 resamples), annualised session Sharpe, and
  the matched-baseline comparison. Event-level t-statistics are not used
  for inference.
* **Baseline**: for each event, a random regular-session bar from the same
  period whose |z| is within 10% of the event's, faded toward the anchor
  with the same overlay and costs.

## Validation grid (18 cells, all reported)

`q` in {0.50, 0.60, 0.70}; `stop_sigma` in {1.5, 2.0, 3.0}; `H` in {30, 60}.
Selection criterion: highest annualised session Sharpe net of costs with at
least 0.5 trades per session. Ties go to the wider stop and longer horizon.

## Hold-out

The single chosen cell, run once on NQ. The same configuration, including
NQ-fitted weights, is then run on ES and GC without change. Success is
pre-defined as: NQ hold-out mean session P&L whose 95% interval excludes
zero at the stated costs, and a positive point estimate on at least one of
ES and GC. Anything short of that is reported as a failure to show an edge.

## What is not allowed

Re-fitting on validation or hold-out data; adding features after seeing
development results on other sets; choosing costs after seeing results;
dropping instruments or periods that look bad; reporting the best cell
without the grid.

## Amendments logged during the development phase

Recorded 9 November 2026 after the development phase and before any
validation or hold-out bar was examined.

1. **Label contamination (fix).** The pre-registered label measured the
   1 rho race from the *level price*. The divergence component includes the
   test bar's own intrabar rejection, so a large rejection means the close
   already sits well inside the favourable side of the level: the label was
   predictable (divergence terciles 0.29 / 0.42 / 0.70) without being
   tradable. Re-labelled from the executable entry (next bar's open) the
   same terciles read 0.44 / 0.43 / 0.44 and every other component is flat
   too. The label is therefore redefined from the next-open entry.
2. **Weight fitting (decision rule).** With the corrected label the
   cross-validated fit selects the strongest regularisation and its log-loss
   is indistinguishable from an intercept-only model. Rule: the fitted
   weights are used only if their grouped-CV log-loss beats the intercept
   model by at least 0.005; otherwise the hand-set weights stay. On
   development data this rule keeps the hand-set weights. The hand-set entry
   filter does add executable value on development (gross +14 USD per trade
   versus -1 USD for all tests at the default overlay), so it stays.
3. **Validation grid (changed before use).** Development overlays show stop
   rates of 42-60% at 1.5-2 rho, i.e. the levels behave as zones. The grid
   is re-specified as stop_sigma in {2, 3, 5} and H in {15, 60}, with q
   unchanged in {0.50, 0.60, 0.70}: still 18 cells, all reported, same
   selection rule.
4. **One secondary hypothesis.** On development the gross edge of entries
   is concentrated in 09:30-12:00 ET (hours 9-11 positive, 12-16 negative).
   A single pre-stated filter, entries whose signal bar falls in
   09:30-12:00 ET, is evaluated on the chosen cell only as a secondary row
   in validation and hold-out. It does not take part in cell selection.

Nothing else changes. The 2025-11 to 2026-11 period remains flagged as
seen.

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

## Amendment 5: the OTE family (recorded 10 November 2026, before its development grid was read)

A second strategy family was extracted from a lesson video supplied by the
user (see docs/ote_lesson_extraction.md): Optimal Trade Entry retracements
of an impulsive leg with a consolidation-break or break-of-structure
trigger, higher-timeframe bias gate, stop beyond the consolidation or leg
origin, target at the leg extreme or its expansion, or a trailing stop.

Rules for this family:

1. Development only on NQ 2018-2021, the same development years as the
   ladder. Signals are generated once per (leg timeframe in {5, 15} min,
   tap level in {0.5, 0.705}, trigger in {range break, range or BOS}) with
   the bias gate off and the bias recorded, so bias handling is a post-hoc
   split (aligned, neutral, counter) rather than a re-run.
2. Management variants on development: target at the 0 level, target at
   the -0.5 expansion, or no target with a 15-bar trailing stop.
3. **Stopping rule, fixed before the grid is read:** the family proceeds
   to validation only if at least one cell with at least 0.3 trades per
   session has a session-mean 95% block-bootstrap interval above zero at
   stated costs and an annualised session Sharpe of at least 0.7.
   Otherwise the OTE family is recorded as null on development and is not
   taken to validation or hold-out, whatever individual cells show.
4. If it does proceed, validation gets exactly the passing cells (all of
   them reported), and the hold-out gets the single cell with the highest
   validation Sharpe, once, on NQ then ES and GC.
5. Implementation fidelity and look-ahead are checked by an independent
   review before any validation run; confirmed fixes are applied and the
   development grid is re-run before the stopping rule is applied.

The first development grid (range-break trigger only, 5-minute legs,
before the break-of-structure trigger and trailing were added) is kept in
the record: 13 of 16 all-signal cells negative after costs; the best cell
(0.705 tap, bias-aligned, range stop, expansion target, 60-bar horizon)
had 70 trades in four years, +91 USD per trade, Sharpe 0.58, interval
including zero. That look is counted as consumed.

## Amendment 6: confirmed audit fixes and reporting before the hold-out (recorded 10 November 2026, before any re-run was read)

An independent audit of the pipeline (five lenses, every finding
refereed) confirmed two defects and refuted fourteen other claims. The
confirmed ones and the changes made, all before the hold-out is run:

1. **Slippage was counted twice.** Fills were moved one tick per side
   against the trade and the cost line charged two more ticks, so friction
   on NQ was 25 USD per round trip against the stated 15. Fixed: commission
   in the cost line, slippage in the fills. Development and validation are
   re-run mechanically with the same selection rule; the earlier tables
   stay in the record (`proto/`), the re-run lives in `proto_a6/`. The
   chosen cell is whatever the unchanged rule picks on the re-run.
2. **Reaction statistics were measured from the level price.** The
   engine's MFE/MAE/reverted columns credited the test bar's own rejection
   (already inside the divergence component) as reaction. They are now
   measured from the open of the bar after the event, the first obtainable
   price, consistent with amendment 1. The costed overlay never used them.
   Every table built on the old measure is regenerated and labelled; the
   README no longer quotes from-level reaction as evidence.
3. **Overlay hygiene.** A signal on the 15:59 ET bar is skipped when the
   rule is flat at the close (it would fill at 16:00). An explicit target
   already behind the fill skips the trade. The ladder has no explicit
   targets, so only the first applies to it.
4. **Hold-out criterion made one-sided and single-legged.** NQ passes only
   if the stated-cost session-mean interval lies entirely above zero. The
   "positive point estimate on ES or GC" leg is dropped: it passes with
   probability 0.75 under the null. ES and GC are reported descriptively.
5. **Record.** The choice of NQ as primary rested on a seen-period
   comparison made with the from-level measure (NQ +1.59 sigma vs GC +0.35
   at 15 bars). From the next open the same entries show NQ +0.49 sigma
   (t 2.1) and GC -0.07; the ordering survives and NQ stays primary. Two
   consumed looks were not logged earlier: a passive fill-at-level overlay
   tested on development events after validation (not adopted), and the
   development replay ran without the promised three-month warm-up because
   no 2017 bars were fetched (the first weeks of 2018 used fallback band
   multipliers). Development is consumed either way; left as is.
6. **Reporting additions, no selection.** Cost rows at 2 and 3 ticks per
   side; a scale-free edge (points per unit of rho, gross and net); a
   descriptive split by the signal bar's minute since the open ([0,5),
   [5,30), 30+); by-year tables count every session of the year.
7. **Limitations stated before the hold-out is read.** (a) The object
   under test is the engine as coded. Its levels in the first minutes of a
   session are built from one or two bars of session data, and on
   validation 62% of trades and 88% of the chosen cell's net come from the
   first fifteen minutes (audit figures on the pre-amendment overlay; 63%
   and 81% on the re-run). A pass is evidence for an opening-minutes fade to
   the session VWAP on NQ at one contract, not for the website's
   undisclosed engine. (b) Costs are fixed in USD while rho in USD roughly
   tripled from 2018 to 2024, so the USD criterion is easier in later
   years; the scale-free rows are for comparison and the pre-registered USD
   criterion stands. (c) Capacity is one contract; nothing here says what
   size the result survives.

The hold-out runs once after items 1-3 are in the code and the validation
re-run has been read, on NQ then ES and GC.

## Amendment 7: OTE fidelity re-run (recorded 10 November 2026, before the re-run grid was read)

The independent review required by amendment 5 rule 5 found no look-ahead
and five confirmed fidelity gaps. Fixes, all fixed before the re-run and
not tuned on it:

1. **The box sits at the level.** A tapped leg dies when price trades
   beyond its 0.0 level before a trigger ("already broken out of"). The
   consolidation is the last 15 one-minute bars before the trigger bar; it
   must reach within 0.10 of the leg of the tapped level, be at most 0.15
   of the leg and 1.5 rho tall, and be sideways (net drift across it at
   most half its range). The trigger is unchanged: a close beyond the box
   with a body of at least 0.5 rho. Reward-to-risk at the signal is
   recorded.
2. **Bias is the four-hour break-of-structure state**: +1 after a close
   above the last confirmed swing high, -1 after a close below the last
   confirmed swing low, held until the opposite break, never neutral once
   warmed up. The 60-minute state and the sign of the 24-hour change are
   recorded as diagnostics and do not enter the grid.
3. **Management.** The three variants of amendment 5 stay. A fourth,
   "expand then trail", is the narrator's own: no time stop, held through
   the overnight for up to three sessions, initial stop at the box, a
   15-bar trailing stop (less 0.25 rho) armed only once price reaches the
   0.0 level.
4. **Nulls corrected.** The random-minute null now takes the real trade's
   stop and target distances from the fill, is drawn 100 times, and is
   reported as P(null session mean >= actual). Two more nulls: the flipped
   direction at the same bars with mirrored geometry, and the same box
   break with no retracement requirement (tap level 0), which tests whether
   the retracement adds anything to a plain box breakout.
5. **Grid and rule.** Legs {5, 15} min x tap {0.5, 0.705} x trigger {range
   break, range or BOS} x set {all, aligned, counter} x management
   {extreme, expansion, trail, expand-trail} = 96 cells. The stopping rule
   of amendment 5 rule 3 applies unchanged to this grid. Nulls run on the
   "all" and "aligned" sets under the extreme target. The two earlier grids
   are consumed looks and stay in the record.

Addendum to amendment 7 (recorded before any P&L of the re-run was read).
The first re-run crashed on a zero-draw bootstrap after printing its first
signal count: 15 signals in four development years for 5-minute legs, tap
0.5, range break (464 under the old box). A count-only probe on 2019 (no
P&L computed) showed the box-to-leg cap was the binding condition: 5
signals at 0.15, 17 at 0.20, 23 at 0.25, 30 with no leg cap; the level
band, the drift test, the extension rule and the rho cap each changed the
count by at most one. The lesson's own five-minute example (part 2) boxes
about 0.18 of its leg, so the cap is set to 0.20, the value the lesson
supports, and nothing else is changed. The tap-0 null is redefined as the
same box break with no retracement requirement, no level requirement and
no extension rule (its first form produced one signal in four years). The
family is expected to print well under 0.3 signals per session under any
faithful reading; the grid is still run and reported in full.

Verification note (recorded after the hold-out, from an independent check
of the write-ups against the record): the grid-3 script computed a cell
only when its signal set had at least 10 signals, a floor amendment 7 did
not state. One set (15-minute legs, tap 0.705, range break, aligned) had 9
signals, so 92 of the 96 pre-registered cells and 15 of 16 nulls are in
the record; at under 0.01 signals per session that set could not have
passed the frequency bar. Transcription errors found by the same check
(a level-test count, an entry count, a cell count, rounding of three
intervals, the ES round-trip cost) were corrected in the results
documents without changing any verdict.

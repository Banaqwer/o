# Extraction: "How To Properly Use OTE (Optimal Trade Entry)"

Source: four QuickTime parts of one lesson video supplied by the user
(13.5 minutes, 1080p, TradingView replay on Micro E-mini Nasdaq-100
futures). Audio transcribed locally with faster-whisper (medium); charts
read from keyframes. Timestamps are seconds into each part.

## Definitions (slide at 0:21 of part 1)

* "Optimal Trade Entry (OTE) is a sophisticated mechanism used to identify
  the 'Wholesale' price within a trending market. It ensures execution
  occurs at the highest probability retracement node."
* "The model forces traders to wait for price to move deep into the
  0.5 - 0.705 zone ... entering at 'Discount' for buys and 'Premium' for
  sells."
* "Market Equilibrium: the 0.5 level represents fair value. Institutional
  Re-accumulation: where big banks reload positions."

## Fibonacci settings (charts throughout)

Levels drawn on every example: 1 (leg origin), 0.79, 0.705 (red), 0.62,
0.5 (red), 0.25, 0 (leg extreme). The two red levels are the ones the
narrator trades: "these zones are usually the 0.705 level and the 0.5
level, which represents fair value and equilibrium" (part 1, 0:18).

## How the range is drawn

* Shorts: "mark the high ... swing high to the swing low. Now you wait for
  either a retest of 0.5 or a test of 0.705" (part 1, 2:15).
* Longs: "what we look for is a swing low and then a swing high ... put the
  OTE level at the swing low all the way to the swing high and look for
  this range at 0.5 and 0.705" (part 1, 1:13).
* The range must be fresh: a range "we already broke out of" is invalid
  (part 3, 1:50). After a very large move, "I would wait for the lower
  timeframe ... a proper swing low to swing high" rather than the huge
  range (part 4, 1:22).
* While the move continues before the retest, the end of the range is
  dragged to the new extreme: "continues pumping up. This means you drag it
  up" (part 2, 1:25).

## Confluence and bias

* "You'd like to use these with other confluences, such as like VWAP"
  (part 1, 1:00); internal levels: "I would personally use 0.705 here
  because of the internal levels that we have around this area" (part 1,
  2:24).
* Higher-timeframe bias is step one of the checklist and the cause of the
  failure example: "if we're in the four hour timeframe and we clearly see
  that we're continuing to push higher, why look for shorts? That's fighting
  the market" (part 3, 1:30). In the failure replay the 0.5 and 0.705 taps
  of a counter-trend leg "fake people out" and are "completely
  disrespected" (part 3, 0:31-1:08).

## Entry mechanics

* Do not buy or sell the tap itself: "you don't want to really top tick
  this ... instead, I use OTE as a level where I want to see consolidation
  start again and then find shorts" (part 2, 0:08).
* After the tap, go to a lower timeframe and mark the consolidation,
  ideally one that "aligns up with the internal low" (part 1, 2:58).
  Entry is the break of that range in the direction of the leg "with
  momentum and displacement" (part 1, 3:11; part 2, 1:44).
* Alternative trigger when no consolidation forms: a break of structure on
  a large candle, "we didn't have the consolidation, but we did have the
  break of structure ... broke a pre-market high ... this is such a huge
  candle" (part 4, 0:30).
* Within the consolidation one may also trade a lower-timeframe OTE of the
  consolidation itself, which "respects an internal range OTE level at
  0.705 before expanding" (part 3, 2:24).

## Risk and targets

* Stop: "right above" the consolidation for shorts (part 1, 3:27), "stops
  under" for longs (part 2, 1:52). The charts show stops a few points
  beyond the range or at the leg origin (1.0 level) for the scalp example.
* Targets: "with my model, I target expansions" (part 1, 3:30): the higher
  timeframe draw on liquidity beyond the leg extreme (prior lows for
  shorts, prior highs for longs). A scalp to the 0 level is the
  conservative alternative (trade panel at part 4, 2:10 shows target at the
  0 level with risk:reward 1).
* Management: "this is where you start dragging. I would drag it to the
  low right here. Start trailing" (part 2, 2:40); the long example trails
  under successive lows and is "trailed out ... for 3.4K with only using
  five contracts".

## The checklist (on-chart text, part 3)

1. Confirm your HTF bias
2. Mark out a proper OTE zone (no chop)
3. Wait patiently for market to retest into this
4. Wait for consolidation before properly taking a trade
5. Target expansions or scalps (depends on the type of trade)
6. ez win

## What the video does not specify

The swing-detection rule, what counts as a "proper" swing, the lower
timeframe used for the consolidation, how large a candle must be for
displacement, the trailing rule, session hours, and any statistics. All of
those are design choices in the implementation and are documented as
parameters of `OTEConfig` and `ExecutionSpec`.

## Mapping to the implementation (`atm_engine/features/ote.py`)

| Lesson | Code |
| --- | --- |
| Swing low to swing high on the chart timeframe | Fractal swings on 5-minute aggregated bars, confirmed with a lag |
| Proper range, no chop | Displacement between 3 and 30 rho, deepest counter-move inside the leg at most 50% of it |
| Drag the end of the range while the move continues | Extreme updated until the first tap |
| Tap of 0.5 or 0.705 | `touch_level` |
| Lower-timeframe consolidation, then break with displacement | The last 15 one-minute bars before the trigger bar form the box; it must be at most 1.5 rho and 0.20 of the leg tall, reach within 0.10 of the leg of the tapped level, and be sideways (net drift at most half its range); then a close beyond the box with body at least 0.5 rho (amendment 7; the first detector used a greedy window of at least 5 bars within 1.5 rho anywhere after the tap) |
| Break of structure on a huge candle | Close beyond the last 15 bars' extreme with body at least 1 rho |
| Stop just beyond the consolidation / leg origin | `stop_at` = range or origin, buffer 0.25 rho |
| Expansions or scalp | `target` = extreme (0 level), expansion (-0.5) or symmetrical (-1.0) |
| Trail under new lows | `ExecutionSpec.trail_bars` channel trail |
| HTF bias | 60-minute structure: higher highs and higher lows, or lower lows and lower highs |
| Invalidation | Close through the 1.0 level |

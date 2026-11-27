---
name: aftereffects-look-matching
description: Matching the colour look of a reference clip with effects on an adjustment layer in After Effects through the bridge — measuring display-referred values with sampleImage (saveFrameToPng is unusable in a 32 bpc OCIO project), a composition-independent "look signature" for a reference that is a different cut, a closed-loop pattern-search optimiser inside ExtendScript on a sandbox duplicate, Lumetri Color and Color Balance property ids, a verified starting recipe, and the traps. Use when asked to "match the look / grade of this reference with the ADJ layer".
---

# Matching a reference look with an adjustment layer (verified AE 26.5, Windows, through the bridge)

Send everything with `aftereffects-bridge`. Code for the signature, the sampler and the optimiser:
`references/signature-and-search.md`. Nothing here needs a render: the loop runs on `sampleImage`.

## What the user has (typical)
Linear (ACEScg) renders in a comp, an `ADJ` adjustment layer with the grade effects, an **OCIO Display
Transform layer above it**, and the reference clip on top as a colour reference. The goal is the **display
look** (after OCIO), so measure at the top of the stack and change only effects on `ADJ`.
Leave the user's own effects (grain, curves they switched off) as they are; add, do not replace.

## Measure with `sampleImage`, not with PNGs
- `layer.sampleImage(point, radius, true, time)` on a **precomp layer** (a comp that holds the one to
  measure) returns the exact display-referred floats of the comp's output, OCIO included. Validated
  against a render-queue PNG (code = display x 255): mean abs diff 0.0008, correlation 0.99995.
- Put it in a **text layer expression** that loops over a grid and returns `"r,g,b;r,g,b;..."`, then read
  it from the script with `textProp.valueAtTime(0, false).text`. 24 x 16 blocks x 3 times = 1152 samples
  per evaluation, ~0.6 s; 384 samples ~0.2 s. Use a 120 x 80 grid only for a preview image.
- `comp.saveFrameToPng` in a 32 bpc OCIO project gave near-black frames (codes ~ float x 25.5), unusable
  for numbers. A render-queue PNG is exact but **running `rq.render()` inside the bridge** left the modal
  "Undo group mismatch, will attempt to fix" warning for the user to click away, and cost ~2 s per frame
  of overhead. Avoid it; if a real render is needed, save the project and use `aerender`.
- **A reference layer that is enabled in the comp is what the sampler reads**, not the render. Always
  measure a `comp.duplicate()` with the reference layer disabled (`resolutionFactor = [1,1]`), and
  delete the duplicate afterwards. Reading the real comp "worked" with a cost of ~10 because it
  measured the reference against itself (that number is also the noise floor of the metric).

## The reference is usually a different cut
No pixel alignment, different objects, so compare **composition-independent statistics** of block means
(same 24 x 16 grid on both sides; extract reference frames with ffmpeg and use the same function in numpy):
- Luma percentiles [3, 10, 25, 50, 75, 90, 97] of block means, **excluding saturated blocks**
  (HSV saturation >= 0.30: a coloured product cap or label would drive the fit).
- Tint (R-G, B-G) of the blocks in three luma bands (<0.30, 0.30-0.65, >=0.65): the colour of shadows,
  mids, highlights.
- Mean saturation of the kept blocks.
- Pool the reference over 10-15 frames of a clean stretch (no logo or end card).
Cost = weighted sum of squared errors, each normalised (percentiles /0.03, tints /0.015, sat /0.04).
Weights per percentile [2, 1, 0.25, 0.25, 1, 1.5, 2]: the ends count most and the **p25 / p50 low**: they
depend on how much object vs background is in frame, not on the grade. Add a soft quadratic penalty on
the distance of every parameter from neutral, otherwise the fit finds green casts and extreme sliders.

## Optimiser (inside ExtendScript, on a sandbox duplicate)
Coordinate pattern search: for each parameter try +/- step, keep an improvement and keep walking that way
(up to 6 more steps), then halve all steps when a full round gives nothing. Cache evaluated vectors. One
bridge call has a ~200 s budget; save the result JSON and start the next call from it (continues the
search). ~220 evaluations in 200 s. Sandbox first, then copy the values to the real comp in one script.
Two stages worked: (1) Lumetri only, (2) Lumetri + Color Balance with penalties and lower mid weights.

## Property ids (flat children of the effect; verified)
Lumetri Color (`ADBE Lumetri`): Temperature `-0007`, Tint `-0008`, Exposure `-0011`, Contrast `-0012`,
Highlights `-0013`, Shadows `-0014`, Whites `-0015`, Blacks `-0016`, Saturation `-0020` (100 = neutral),
Faded Film `-0028`, Vibrance `-0030`, Creative Saturation `-0031`. Wheels, curves and the Curves effect
points are custom values: **not scriptable**, so use the effects below for colour in shadows/highlights.
Color Balance (`ADBE Color Balance 2`, -100..100): `-0001..-0003` = Shadow R/G/B, `-0004..-0006` = Midtone
R/G/B, `-0007..-0009` = Highlight R/G/B. Add with `fx.addProperty("ADBE Color Balance 2")`, then
`moveTo(2)` to sit after Lumetri and before grain.
Display Transform OCIO layer behaves like an SDR tone-map (verified display floats for scene values
0.02 / 0.18 / 0.5 / 1.0: 0.041 / 0.356 / 0.647 / 0.812), so scene 1.0 is already only 0.81 on screen.

## Verified starting recipe (lifted blacks, soft highlights ~0.85, blue-teal shadows, cream-green highlights)
Lumetri: Temperature +8, Tint -27, Exposure +1.7, Contrast +20, Highlights +15, Shadows -17.5, Whites +25,
Blacks +5, Saturation 95, Vibrance -7. Color Balance: Shadow R -1.5 / B +18, Mid R +1.5 / B +3, Highlight
R +3 / G -3. Signature cost 182 -> 19 (noise floor ~10); highlights still ~0.05 below the reference (p97 0.80 vs 0.85).
Faded Film was not part of the search.

## Check, then hand back
1. Numbers on a duplicate of the real comp with the reference layer off (cost, percentiles, tints).
2. Pictures: a 120 x 80 `sampleImage` grid at 3 times, turned into a PNG with numpy/Pillow and put beside
   reference frames (do not use the render queue). Judge blacks, highlight colour, cast.
3. Remove every temporary comp (`zz_` prefix makes them easy to find), save the project if allowed.
Tell the user what was not matched: grain/halation/blur of the reference, hue differences that come from
different objects, anything composition-dependent, and the original values of every changed property.

## Traps
- After `addProperty` + `moveTo` the earlier effect references are dead ("Object is invalid"): re-fetch
  every effect by name. A script that threw halfway keeps the added effect; the rerun finds it by name.
- ES3: no reserved words as variable names (`short`), no backslashes or regex literals through the bridge.
- Do not trust a first look at a reference frame for tint: measure it (the same function on both sides).

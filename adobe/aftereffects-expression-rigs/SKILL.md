---
name: aftereffects-expression-rigs
description: Controller-driven expression rigs in After Effects built through the bridge — one CONTROLLER null with sliders (counts, seed, speed, focal length), layers indexed by their name, derived values stored in per-layer slider effects, seamless loops, coprime-stride shuffles, 3D helix / spiral flythroughs with a real camera, depth fog with Fill + CC Composite, a guide layer for the paths, and offline checks (expression errors, loop seam, toComp projection, preview frames). Use when the request is "make N layers fly / orbit / loop with sliders for number, density, seed, camera".
---

# Expression rigs in After Effects (verified AE 26.5, Windows, through the bridge)

Send everything with `aftereffects-bridge` (signed scripts, no backslashes, `String.fromCharCode(10)` for
newlines in expression text). This skill is the *how to build a rig* layer on top of it.
Full worked recipe with the expressions: `references/spiral-flythrough.md`.

## The pattern
- **One `CONTROLLER` null** (2D, top of the stack) carrying Slider / Color Control effects. Every other
  expression reads `thisComp.layer("CONTROLLER").effect("Name")("Slider")`. Sliders cannot be clamped by
  script, so clamp in the expression: `Math.max(1, Math.min(16, Math.round(v)))`.
- **Capacity layers + active slots**, never a changing layer count: build the maximum (here 16 x 8 = 128
  layers, extra ones are `duplicate()` of configured layers, which keeps expressions and effects), and let
  each layer decide `active = slot < paths * perPath`; inactive layers get opacity 0.
- **Index from the layer name** (`"PIC 007 | file.png"` → `parseInt(thisLayer.name.substring(4, 7), 10)`).
  Stable when layers are reordered or the controller / camera are inserted above them.
- **Derived values live in slider effects on the layer** (`Slot`, `Arm`, `U`), each with its own
  expression; Position / Scale / Opacity / fog read them with `effect("U")("Slider")`. One place per idea,
  and you can read them back from a script for checks.
- Configure the stack **in place** on the user's existing layers (rename with a prefix, make them 3D, add
  effects) after saving a duplicate of the comp into `_old`; changing the comp duration is part of the job.

## Seamless loop
`u = phase + offset + laps * time / thisComp.duration; u - Math.floor(u)` with `laps` an **integer**
(negative reverses). Everything periodic in `u` repeats exactly at the comp duration. Check with
`prop.valueAtTime(0, false)` vs `valueAtTime(thisComp.duration, false)`: identical to the last digit.
Phases: `(j + stagger * arm / arms) / perArm` keeps arms interleaved instead of lined up.

## Shuffle that never repeats
`slot = (k * stride) % N` with `stride = 1 + shuffle` bumped until `gcd(stride, N) == 1` gives a different
but complete permutation per slider value. Only permute the *unique* sources (k < N); duplicates take slots
N..cap so repeats appear only when more slots are asked for than there are pictures.

## 3D flythrough (details in the reference)
Camera at z = 0 looking +z (two-node camera, POI at z = 1000), layers at `z = d(u)`. Exponential depth
`d = dFar * (dNear / dFar)^u` spaces layers evenly in size; world helix `(R cos th, R sin th)` with
`th = arm * 360 / arms + twist * u` projects to a logarithmic spiral. Screen position is
`centre + offset * zoom / d`, matched to `layer.toComp()` to 0.1 px. `zoom = focalMm / 36 * compWidth`.
Pick `dNear` so layers are completely outside the frame at `u = 1`
(`rExit = halfDiagonal / (1 - 0.7071 * size / R)`, `dNear = R * zoom / rExit`) and the wrap is invisible.
With a static camera focal length is only a zoom; it changes the look because `dFar` is fixed in world units
(wider lens = stronger growth between far and near).

## Depth fog with Fill + CC Composite (tested numbers)
Add `ADBE Fill` (colour = background colour from the controller) then `CC Composite`. In the default
**Composite Original = 3** the result is `lerp(fill, original, Opacity)`: **Opacity 0 = pure fill, 100 = the
untouched picture** (orange over blue fill: 0 → blue, 25 → 63,31,198, 50 → 127,63,140, 100 → orange).
So drive Opacity with *visibility*, not fog: `100 * t*t*(3-2*t)` with `t = clamp(u / fadeLength)`.
Modes 1 and 2 ignore Opacity (1 = original, 2 = fill). The layer stays opaque, so overlapping pictures keep
their depth order (fading with layer opacity would show the ones behind).

## Guide layer for the paths
Shape layer (2D, at the comp centre) with a Path expression `createPath(points, [], [], false)` built from the
same maths (80 points of `r = R * zoom / d` at angle `twist * u`), a Stroke and a **Repeater**
(copies = arms, rotation = 360 / arms; the Repeater's default Position is `[100, 0]`: set it to `[0, 0]`).
`guideLayer = true; enabled = false`: invisible in renders, one click to show.

## Checks that caught real mistakes
- Scan `prop.expressionError` over every layer after building (0 errors, 128 layers x 8 props).
- Read values at t = 0 and t = duration (loop), and `toComp(anchorPoint)` through a temporary Slider
  expression (`p[0]`, `p[1]` in two sliders, a string result makes a slider error), then delete the temps.
- Render frames with `comp.saveFrameToPng` (async; poll for the files). It renders at the comp's resolution
  factor (Quarter = 480 px of 1920) and never renders guide layers.
- Test an unknown effect's semantics on a small temp comp first (squares in a grid, one per setting, read the
  PNG pixels). The CC Composite test above reversed my assumption and explained why half the layers vanished.
- Always remove temp comps *and* their solids (`it.remove()` on the solid footage items with `usedIn.length == 0`).

## From a user's older expression notes (not re-tested here)
`loopIn() + loopOut() - value` (ping-pong-free cycle on a keyed layer); `(((v - 1) % n + n) % n) + 1`
(wrap into 1..n, safe for negatives); horizontal FoV `2 * Math.atan((thisComp.width / 2) / zoom) * 180 / Math.PI`;
object on a path `path.pointOnPath(p)` then `layer.toWorld(local)` with `p = master/100 + index * spacing/100`;
closest layer to the camera with `length(sub(cardPos, camPos))` in a loop; trigger on the last marker with
`marker.nearestKey(time)`; count layers by name with `RegExp(pattern)` over `thisComp.numLayers`.
Note: a shape path is 2D, so a spiral *in depth* is easier to write as maths than to sample from a path.

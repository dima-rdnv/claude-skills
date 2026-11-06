# Cleaning up and animating a Figma HUD imported with Overlord (verified AE 26.5, Windows, 6 Nov 2026)

## What the import looks like
- Each Figma frame/group becomes a **guide shape layer** used only as a parent; the board's root group
  sits at the comp centre with scale 200 % when the comp is 2× the Figma frame. Children keep Figma
  units in their parent's space. Names repeat ("micro", "( )", "Image", "Caption") — rename by text
  content / parent, not by index.
- Image fills arrive as PNG footage (in an `Overlord/` folder) with a child rectangle shape as alpha
  track matte (`<name>_mask`, off). They come in **Normal**; a Figma image that read as blended needed
  `BlendingMode.SCREEN`. A FILL-cropped image can arrive fitted instead (box not covered): set
  scale `s = max(boxW/srcW, boxH/srcH)·100` and its matte child to `10000/s`.
- **Open L-paths each followed by Merge Paths** (corner brackets, reticles) render as closed triangles.
  Disabling the `ADBE Vector Filter - Merge` entries restored the L shapes.
- **Rotated text lands far off** (here 1100–3000 px, incl. a ±1.6° one); unrotated text was exact.

## Putting labels back where Figma has them
- Measure comp-space bounds without touching the layer: add a Point Control, re-fetch it by
  `propertyIndex`, expression `var r = sourceRectAtTime(t, false); toComp([r.left, r.top])` (and the
  opposite corner), read `valueAtTime(t, false)`, remove it. A script that throws between add and
  remove leaves the effect behind — clean it up in the next run.
- Move by the centre difference ÷ parent scale (0.5 under a 200 % root), re-measure, repeat ≤ 3×:
  error 0 px.
- Figma MCP `get_metadata` for a **rotated** node: `width/height` are the axis-aligned box, but `x/y`
  is the node's own origin (its rotated top-left corner), not the box corner. Centre = `(x, y) +
  R(θ)·(w/2, h/2)` with θ = AE rotation (clockwise, y down) and w, h the unrotated size, solved from
  the box: `W = w|cos| + h|sin|, H = w|sin| + h|cos|` (±90°: w = H, h = W). Using the box centre
  instead left them 10–45 Figma px off.

## Precomposing parts (box + label) without moving them
- `comp.layers.precompose(indices, name, true)` keeps parenting and track mattes when parents and
  mattes are in the selection. For a parent outside the selection, first `layer.parent = null`: AE
  keeps the layer where it is (measured drift 0). The new comp has the old comp's size.
- Crop: set `nc.width/height`, shift the unparented layers by `−x0, −y0`, then on the precomp layer
  anchor `[W/2, H/2]`, position `[x0 + W/2, y0 + H/2]` — box corners identical before/after.
- Expressions that read `thisComp.layer("HUD Controls")` break inside the new comp: replace with
  `comp("<parent comp>").layer("HUD Controls")` (precomp time = parent time with startTime 0).
- Screen-blended layers inside a precomp only blend with what is inside it; set the precomp layer to
  Screen too so dark feed pixels don't cover what's behind.

## Build-on rig that stays editable
- One null "HUD Controls" (Build Start (s), Build Speed, Data Flow, Flow Speed, Idle Motion); every
  property expression starts with `t = (time − Build Start)·Build Speed` and carries its own delay
  and duration as constants, so the whole build retimes from two sliders. 266 expressions on ~180
  layers evaluated without errors and AE stayed responsive.
- Draw-on: `L.property("ADBE Root Vectors Group").addProperty("ADBE Vector Filter - Trim")` at the root
  (applies to all groups above it); expression on Trim End (or Trim Start 100→0 to draw from the end).
- Type-on: add `"ADBE Text Animator"`, re-fetch by index, add `"ADBE Text Opacity"` (set 0), add a
  `"ADBE Text Selector"` if the animator has none, expression on `"ADBE Text Percent Start"` 0→100.
- Decode/scramble: a Source Text expression using `String(value)` returns the layer's text in 26.5
  (line breaks kept, style kept); build the string with charAt/indexOf — no regex, no backslashes
  (the bridge mangles them). Check with `sourceText.valueAtTime(t, false).text`.
- Packets travelling along a line: `duplicate()` the line **before** adding its build expressions,
  thicker round-capped stroke, Trim Start/End = a 9 % window sliding with `(t − T0)/period + phase`.
- Rotating an arc around another element: set its anchor to `anchor + (pivot − position)` and its
  position to the pivot (same parent, scale 100) — the render doesn't change.

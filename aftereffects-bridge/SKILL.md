---
name: aftereffects-bridge
description: Driving Adobe After Effects from Claude without an MCP server, through a file-based ExtendScript bridge (a ScriptUI panel that runs .jsx files dropped into an inbox folder and writes JSON results). Covers finding and starting the bridge, sending scripts safely, inspecting comps/layers/keys/expressions, rendering preview frames, retiming keyframes to a voice-over, building UI elements (shape/text layers with expression-driven interactions), and verified traps. Use whenever a task touches After Effects / AE / .aep comps.
---

# After Effects via the file bridge (verified AE 2026 / 26.5, Windows)

There is no AE MCP server. `scripts/ClaudeBridge.jsx` is a ScriptUI palette that, while open,
checks `<ROOT>/inbox` every second, runs each `*.jsx` there inside `(function(){ ... })()` (so a
top-level `return` works) as **one undo step named `Claude: <file>`**, writes
`<ROOT>/outbox/<file>.json` = `{file, ok, result | error+line, ms}` and moves the script to `done/`.
Default `ROOT` is `D:/WORK/Claude/ae-bridge` (edit the `ROOT` line to move it).
`$.global.ClaudeBridge` exposes `ROOT`, `stringify`, `readText`, `writeText`, `log` to scripts.

## Finding / starting it
- When the user says "AE is running the bridge": the panel reads `Listening… (inbox: …)`. If you
  don't know ROOT, look for `ClaudeBridge.jsx` (Windows: `%APPDATA%\Microsoft\Windows\Recent\ClaudeBridge.jsx.lnk`
  resolves to it) and read its `ROOT`. Old `done/` + `outbox/` files show what earlier sessions did.
- Start: File › Scripts › Run Script File… › `ClaudeBridge.jsx`. Needs Preferences › Scripting &
  Expressions › *Allow Scripts to Write Files and Access Network*.
- A script that sits in `inbox/` for more than a few seconds means the panel is **paused or
  closed** (AE itself still reports "Responding"). Ask the user to press Resume / Check now or
  re-run the script; don't resend.

## Sending scripts — never write straight into inbox/
The bridge polls every second and can grab a file while it is still being written: it then runs
an **empty script**, reports `"ok": true, "result": null, "ms": 0`, and `done/<name>.jsx` is 0 bytes.
Write the script elsewhere, copy it in under a non-`.jsx` name, then rename:
`scripts/send.sh NAME [timeout]` does this (env `STAGE` = folder with `NAME.jsx`, `BRIDGE` = ROOT)
and waits for the JSON. Number scripts (`057_render.jsx`) so `done/` reads as a history.

## Rendering preview frames
- `comp.saveFrameToPng(t, file)` is **asynchronous**: the script returns (ms ≈ 1) and the JSON
  arrives before the PNGs are on disk. Poll until all expected files exist (and a beat more for
  the last one) before reading them.
- It renders at the comp's **resolution factor** (a Quarter-res comp gives a 665 px PNG of a
  2658 px comp). Set `comp.resolutionFactor = [1,1]` (or `[2,2]`/`[4,4]` for speed) in `try`,
  restore it in `finally`.
- **Guide layers are not rendered** into the parent: a precomp layer with `guideLayer = true` is
  invisible in `saveFrameToPng` of the parent comp. Check `L.guideLayer` before concluding
  something is missing; render the precomp itself instead, or ask the user to toggle it.
- In a 32-bpc project (working space None) the PNGs come out 16-bit RGBA and look far darker than
  AE's viewer; lifting with gamma 2.2 (`255*(v/255)**(1/2.2)`) made them readable (cause unverified).
  UI precomps with transparency also need compositing over black before viewing.
- Contact sheets: Pillow (`uv run --with pillow python -I sheet.py …`) worked. Windows ffmpeg 7.1
  segfaulted / heap-crashed on `color`+`overlay`+`vstack` graphs fed with these rgba64 PNGs, and
  `drawtext` fails without a fontconfig file — don't bother.
- To time an event to footage (a hand gesture, a cut), render the parent at `[4,4]` every 0.04 s
  around it and grid the frames; crop the region of interest.

## Inspecting
- Find comps by name over `app.project.item(i)` (`CompItem`), use ids afterwards (`itemByID`).
- `comp.usedIn` + the layer's `startTime`, `stretch`, `timeRemapEnabled` give the time mapping. A
  precomp layer with `startTime 0`, stretch 100, no remap ⇒ **precomp time == parent time**. If one
  precomp is used by several parents, retiming its insides changes all of them — check first.
- Generic walker (verified): recurse `layer.property(i)` while `propertyType !== PROPERTY`; on a
  PROPERTY skip `NO_VALUE`/`CUSTOM_VALUE` value types and `ADBE Marker`; record `numKeys`,
  `keyTime(k)`, `keyValue(k)`, `expressionEnabled`/`expression`. Skip `ADBE Layer Styles`,
  `ADBE Material Options`, `ADBE Audio Group` etc. to keep output small. Text: `value.text/font/
  fontSize/fillColor`. Dump to JSON and summarise with Python — results get large fast.
- Rigged UI comps often drive everything from a few **control nulls with slider keys**
  (e.g. "open %" / "progress %") and expressions like `t0 = slider.key(1).time + delay + stagger`.
  Then retiming = moving those few keys; the expressions follow. Find the keyed props first.

## Retiming keys (verified)
Per property: grab every key (`keyTime`, `keyValue`, `keyIn/OutInterpolationType`,
`keyIn/OutTemporalEase`, `keyTemporalContinuous/AutoBezier`, and for spatial props
`keyIn/OutSpatialTangent`, `keySpatialContinuous/AutoBezier`), then:
1. **add the new keys first** (`addKey(t)` + `setValueAtKey`), 2. remove the old ones by time
(never empty a Time Remap property — add-then-remove avoids it), 3. restore per key in this order:
`setTemporalEaseAtKey` → `setInterpolationTypeAtKey` → continuous/auto-bezier → spatial tangents.
- Snap new times to the comp frame grid: `Math.round(t * fps) / fps` (precomp fps may differ
  from the parent's).
- Map times with an explicit per-property function and **report anything it can't map** instead
  of guessing; keep offsets for choreography that should keep its rhythm, stretch linearly only
  where the VO needs it.
- Holding a value across a long gap (e.g. Time Remap between two scenes): give the key before the
  gap `KeyframeInterpolationType.HOLD` out, add a key with the same value where motion resumes.
  Otherwise a slow drift interpolates across the gap.
- Easing a key you created: `setTemporalEaseAtKey(k, [new KeyframeEase(0, 50)], [...])` — one
  `KeyframeEase` per dimension (1 for sliders/time remap).
- Everything a bridge script does is one undo step, so a bad retime is one Ctrl+Z.

## Building UI elements (verified)
- Shape layer: `comp.layers.addShape()`; `contents.addProperty("ADBE Vector Group")`, inside its
  `"ADBE Vectors Group"` add `"ADBE Vector Shape - Rect"` (Size, Roundness 999 = pill),
  `"ADBE Vector Shape - Group"` (set a `Shape` with `vertices`, `inTangents`, `outTangents`,
  `closed`), `"ADBE Vector Graphic - Fill"` / `"- Stroke"`. The first group in the list draws on top.
- Text: `comp.layers.addText(str)`, edit a copy of the `TextDocument` (`font` = PostScript name,
  `fontSize`, `fillColor` [r,g,b], `justification`), `setValue` it back; centre it with
  `sourceRectAtTime(0,false)` → anchor `[left + w/2, top + h/2]`; the same rect gives the width
  to size a button around the label.
- Parenting: set `layer.parent = X` **first**, then write the position (it is then in X's space).
- Order: `layer.moveBefore(otherLayer)`; new layers land at index 1.
- Match the existing design: read colours, font, sizes, corner roundness and the reveal
  expression of a similar element (e.g. an existing primary button) and reuse them.
- Interaction driven by a time **slider** on a control layer (e.g. `"Tap (s)"`), so the user can
  nudge it without touching keys. Recipe used for a tap on a button:
  scale dip 100→92 over 0.1 s before the tap, 92→104→100 over 0.3 s after; fill brightens
  briefly; a pill-shaped stroke ripple scales `[100+22u, 100+90u]` (u = cubic ease-out over
  0.6 s) while fading; the button fades and shrinks to 90 % 0.35–0.7 s after the tap.
  Child layers don't inherit opacity — link it: `thisComp.layer("Button").transform.opacity`.
- Effects by match name: `"ADBE Slider Control"`, `"ADBE Gaussian Blur 2"` (`-0001` = blurriness).

## Keeping this skill current
After a session that used the bridge, add only what was tested in a real project (mark the rest
*(unverified)*), correct wrong entries instead of appending, keep this file under ~300 lines,
commit and push the skills repo. Project-specific facts (comp names, timings, client) go to that
production's notes (see `project-notes`), never here.

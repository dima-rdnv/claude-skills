---
name: aftereffects-bridge
description: Driving Adobe After Effects from Claude without an MCP server, through a file-based ExtendScript bridge (a ScriptUI panel that runs .jsx files dropped into an inbox folder and writes JSON results). Covers finding and starting the bridge, sending scripts safely, inspecting comps/layers/keys/expressions, rendering preview frames, retiming keyframes to a voice-over, building UI elements (shape/text layers with expression-driven interactions), and verified traps. Use whenever a task touches After Effects / AE / .aep comps.
---

# After Effects via the file bridge (verified AE 2026 / 26.5, Windows)

There is no AE MCP server. `scripts/ClaudeBridge.jsx` is a ScriptUI panel (dockable when installed,
a minimizable window when run as a plain script) that, while open, checks `<ROOT>/inbox` every second, runs
each `*.jsx` there inside `(function(){ ... })()` (so a top-level `return` works) as **one undo
step named `Claude: <file>`**, writes `<ROOT>/outbox/<file>.json` = `{file, ok, result | error+line, ms}`
and moves the script to `done/` (without its signature line).
**Signed scripts only:** `scripts/send.sh` signs each script with `~/.claude/ae-bridge.key` (created
on first use; AE reads it from `Folder("~")/.claude`). Anything unsigned, changed after signing,
older than an hour or already run is refused: `{"ok": false, "rejected": true, "error": "Rejected: …"}`,
and the file goes to `rejected/`. This keeps other programs and synced folders from running code in
AE; it does not limit what a signed script can do. Scripts that `$.evalFile` a library skip the
check for that file, so keep such libraries out of synced folders.
`ROOT` is the folder last set with `ClaudeBridge.useFolder(path)` (the panel has no folder button;
you switch it when the user asks), remembered in AE's settings (`app.settings`, section
`ClaudeBridge`, key `root`). Until then: the script's own folder, or `Documents/ClaudeBridge` when
the script sits in one of AE's Scripts folders (AE lists every script under them, so inbox/done
must not live there) or its folder is read-only. The panel has one **Stop / Start** button and a
status line showing the inbox. `$.global.ClaudeBridge` exposes `ROOT`, `stringify`, `readText`,
`writeText`, `log`, `useFolder`, `win` to scripts.

## Finding / starting it
- When the user says "AE is running the bridge": the panel reads `Listening… (inbox: …)`. If you
  don't know ROOT, ask the user what the status line says. Old `done/` + `outbox/` files show
  what earlier sessions did.
- Install once: File › Scripts › Install ScriptUI Panel… › `ClaudeBridge.jsx` (it lands in
  `%APPDATA%\Adobe\After Effects\<ver>\Scripts\ScriptUI Panels\`; copying it there by hand works
  too, no admin needed), restart AE, Window › ClaudeBridge.jsx, dock it. A docked panel reopens
  with the workspace. The folder is per AE version, so a new AE version needs it again *(unverified)*.
  After changing the installed file, closing and reopening the panel from the Window menu loads
  it (no restart).
- No minimize button is possible for the panel: AE draws panel frames (floating or docked) with
  only a close button, and `win.size = …` on a Panel is ignored. To tuck it away, dock it as a
  tab. Palettes are Windows tool windows, so `minimizeButton: true` shows nothing there; a
  `new Window("window", …, {minimizeButton: true})` is a normal window owned by AE with a
  minimize button and its own taskbar button, and `show()` doesn't block.
- Or once: File › Scripts › Run Script File… › `ClaudeBridge.jsx`. Either way needs Preferences ›
  Scripting & Expressions › *Allow Scripts to Write Files and Access Network*.
- You can't start it yourself: `AfterFX.exe -r <ClaudeBridge.jsx>` against an already running AE
  2026 did nothing (no second instance, script never ran; AE was on the Home screen). Ask the user.
- A script that sits in `inbox/` for more than a few seconds means the panel is **stopped**
  (status reads `Stopped…`: ask the user to press Start) or **closed** (AE itself still reports
  "Responding"), or listening in another folder (the user may have started a different copy: ask
  what the status line says). Don't resend; it runs as soon as the bridge is back. After an
  hour its signature has expired and it is rejected; then send it again.
- Wrong folder: a script calling `$.global.ClaudeBridge.useFolder(path)` switches and remembers it.
  It returns `""` or the reason (it refuses AE's Scripts folders and unwritable folders). The
  calling script's own JSON still lands in the folder it came from.
- Loading a changed `ClaudeBridge.jsx` into a running AE without the user: a script that runs
  `var old = $.global.ClaudeBridge.win; $.evalFile(file)`. The new panel cancels the old task and
  opens a window. Close `old` from a delayed `app.scheduleTask("…close()…", 2000, false)`, never
  directly: the old panel is still inside its tick and writes to its own log after your script
  returns *(closing via `win` unverified)*. Don't use `Window.find("palette", "Claude Bridge")`
  for this: it returned an already-closed palette and left the visible one open. A palette started
  this way once stopped on its own within ~5 min (cause unknown), so prefer asking the user to
  close and reopen the panel (Window › ClaudeBridge.jsx loads the new file, no restart needed).
- The bridge keeps running while AE is in the background (a ping answered in 0.6 s with the
  Claude app in front).

## Sending scripts — only through send.sh
`scripts/send.sh NAME [timeout]` (env `STAGE` = folder with `NAME.jsx`, `BRIDGE` = ROOT) signs the
script, copies it in under a non-`.jsx` name, renames it and waits for the JSON. Never write into
`inbox/` yourself: the panel would reject it as unsigned, and the bridge polls every second, so a
file grabbed while still being written fails too. `send.sh` needs `openssl` (Git for Windows and
macOS have it). Number scripts (`057_render.jsx`) so `done/` reads as a history.

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

## Render queue exports (verified, AE 2026)
- `rq.items.add(comp)`, `item.setSettings({"Time Span": "Work Area Only", "Quality": …})` and
  `om.file = new File(".../name_[#####].png")` work. **Format, Channels, Depth and Color are not
  scriptable**: `om.setSettings({"Format": …})` throws "read-only", and
  `getSettings(GetSettingsFormat.STRING_SETTABLE)` lists only crop/resize/audio/file info/video output.
- To copy an existing item's format: `saveAsTemplate(name)` on its output module, then
  `applyTemplate(name)` on the new one. AE refuses `saveAsTemplate` on a DONE item, so
  `ref.duplicate()` first, save from the duplicate, `remove()` it. The template **persists** in the
  user's list (no API to delete it), so ask before creating one.
- Compare `getSettings(GetSettingsFormat.STRING)` of both items afterwards (Format, Channels,
  Depth, Color, Use Comp Frame Number, Time Span…) to prove they match before rendering.
- `rq.render()` is synchronous: the bridge's JSON arrives when it's done (347 frames of a 2658 px UI
  comp ≈ 100 s); give `send.sh` a long timeout. Only QUEUED items render; DONE ones are skipped.
- A script that throws midway keeps its earlier edits (e.g. a half-configured queue item) — check
  the queue before retrying, and guard against adding a second copy.

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

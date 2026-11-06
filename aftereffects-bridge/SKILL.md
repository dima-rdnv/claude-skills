---
name: aftereffects-bridge
description: Driving Adobe After Effects from Claude without an MCP server, through a file-based ExtendScript bridge (a signed CEP panel that runs signed .jsx files dropped into an inbox folder and writes JSON results). Covers finding and starting the bridge, sending scripts safely, inspecting comps/layers/keys/expressions, rendering preview frames, retiming keyframes to a voice-over, building UI elements (shape/text layers with expression-driven interactions), and verified traps. Use whenever a task touches After Effects / AE / .aep comps.
---

# After Effects via the file bridge (verified AE 2026 / 26.5, Windows and macOS)

There is no AE MCP server. `panel/` is a CEP extension ("Claude Bridge", Window › Extensions):
while it is open, `index.html` (Node enabled) checks `<ROOT>/inbox` itself once a second and
writes `<ROOT>/heartbeat.json`, and calls into AE (`ClaudeBridge.tick()` in `panel/host.jsx`) only
when a script is waiting, so AE is left alone while idle. Each tick takes every `*.jsx` in
`<ROOT>/inbox`, checks its signature, **moves it to `done/` first** (without its signature line,
so a script that takes AE down doesn't rerun after the restart), runs it inside
`(function(){ ... })()` (so a top-level `return` works; `err.line` = line in your file) as **one
undo step named `Claude: <file>`**, and writes `<ROOT>/outbox/<file>.json` =
`{file, ok, result | error+line, ms}`.
**Signed scripts only:** `scripts/send.sh` signs each script with `~/.claude/ae-bridge.key` (created
on first use; AE reads it from `Folder("~")/.claude`). Anything unsigned, changed after signing,
older than an hour or already run is refused: `{"ok": false, "rejected": true, "error": "Rejected: …"}`,
and the file goes to `rejected/`. This keeps other programs and synced folders from running code in
AE; it does not limit what a signed script can do. Scripts that `$.evalFile` a library skip the
check for that file, so keep such libraries out of synced folders.
`ROOT` is the folder last set with `ClaudeBridge.useFolder(path)` (the panel has no folder button;
you switch it when the user asks), remembered in AE's settings (`app.settings`, section
`ClaudeBridge`, key `root`), else `Documents/ClaudeBridge`. The panel has one **Stop / Start**
button, a status line showing the inbox, and a log. `$.global.ClaudeBridge` exposes `ROOT`,
`VERSION`, `runs`, `stringify`, `readText`, `writeText`, `log` (shown in the panel and
`bridge.log`), `useFolder` and `info()` to scripts.

**On macOS read `references/macos.md` first.** Those notes were verified with the earlier ScriptUI
panel, not yet with this CEP panel, and `install.ps1` is Windows-only.

## Installing / finding it
- When the user says "AE is running the bridge": the panel reads `Listening… (inbox: …)`. If you
  don't know ROOT, ask the user what the status line says. Old `done/` + `outbox/` files show
  what earlier sessions did.
- Install (verified AE 2026, Windows): `scripts/install.ps1` self-signs `panel/` with
  `ZXPSignCmd.exe` from `-SigningDir` (default `D:\WORK\Claude\premiere-bridge-signing`, shared
  with the Premiere bridge; CEP 12 refuses unsigned panels and ignores PlayerDebugMode), copies it
  to `%APPDATA%\Adobe\CEP\extensions\com.claude.aebridge`, and removes the old ScriptUI panel
  (`ClaudeBridge.jsx` in AE's ScriptUI Panels folders) so two bridges never share an inbox.
  `-ShareTo <dir>` also writes the signed copy colleagues install (they copy that folder into their
  CEP extensions folder; Mac: `~/Library/Application Support/Adobe/CEP/extensions/`). AE finds new
  extensions only at start-up: restart, Window › Extensions › Claude Bridge, dock it.
- Every edit to a panel file breaks the signature: re-run `install.ps1`. The panel loads
  `host.jsx` each time it opens (and again whenever it finds the bridge code missing), so a new
  `host.jsx` takes effect when the user closes and reopens the panel; a bridge script can also
  `$.evalFile(Folder.userData.fsName + "/Adobe/CEP/extensions/com.claude.aebridge/host.jsx")`
  (keeps `runs` and the already-run signatures). A changed `index.html` needs the panel reopened.
- You can't start it yourself: `AfterFX.exe -r <script>` against an already running AE 2026 did
  nothing (no second instance, script never ran; AE was on the Home screen). Ask the user.
- **AE dialogs don't stop it** (verified 4 Nov 2026): a script sent while Project Settings was
  open ran within a second. So a script can change things under an open dialog, and the user's
  OK may then overwrite them; if the user mentions a dialog is open, ask them to close it first.
- A script that sits in `inbox/` for more than a few seconds means the panel is **stopped**
  (status `Stopped…`: ask the user to press Start), **closed** (ask them to open Window ›
  Extensions › Claude Bridge), busy with an earlier long script, or listening in another folder
  (ask what the status line says). Don't resend; it runs as soon as the bridge is back. After an
  hour its signature has expired and it is rejected; then send it again.
- **Diagnosing:** `send.sh`'s timeout message prints `<ROOT>/heartbeat.json` (written by the panel
  every 5 s, independent of AE) and the last lines of `<ROOT>/bridge.log` (loads, every script,
  rejections, Stop/Start, panel open/close; trimmed to 7 days). Stale = the panel or AE is closed.
  Fresh + `paused: true` = the user pressed Stop. Fresh + `aeWaiting` > a few s = AE hasn't answered
  the panel's call for that long: a long script (the log shows `run X` without its `OK`/`FAIL`)
  or AE is busy or hung. `lastAeAnswer` = when AE last finished a call.
- **Quitting AE** (verified 4 Nov 2026): with a big EXR-heavy project AE showed "Not
  Responding" for 12 s to 2 min while quitting, then closed by itself, with no bridge call pending.
  Tell the user to wait it out rather than kill it. AE 26.5 never sent CEP's
  `ApplicationBeforeQuit` event to the panel; its page unloads about a second before AE exits.
- Wrong folder: a script calling `$.global.ClaudeBridge.useFolder(path)` switches and remembers it.
  It returns `""` or the reason (it refuses AE's Scripts folders and unwritable folders). The
  calling script's own JSON still lands in the folder it came from.
- Why not a ScriptUI panel (the bridge was one until 4 Nov 2026, verified): an
  `app.scheduleTask` timer that fires while any AE dialog is open is dropped for good, silently, so
  the bridge died at the first Project Settings / Save / warning dialog while still showing
  "Listening…"; its buttons don't respond while a dialog waits; and AE re-running a ScriptUI panel
  with a dialog open fails with "Unable to execute script at line N … Cannot run a script while a
  modal dialog is waiting for response". Keep that in mind for any ScriptUI tool you build.

## Sending scripts — only through send.sh
`scripts/send.sh NAME [timeout]` (env `STAGE` = folder with `NAME.jsx`, `BRIDGE` = ROOT) signs the
script, copies it in under a non-`.jsx` name, renames it and waits for the JSON. Never write into
`inbox/` yourself: the panel would reject it as unsigned, and the panel checks the inbox every
second, so a file grabbed while still being written fails too. `send.sh` needs `openssl` (Git for Windows and
macOS have it). Number scripts (`057_render.jsx`) so `done/` reads as a history.

## Traps hit in practice
- **No backslashes in bridge scripts**: a script with `/\/g` failed with "SyntaxError: Unterminated
  string constant" at that line (the bridge's handling mangles them). Match paths with
  `File.fullName` (forward slashes, e.g. `/d/WORK/...`) instead of `fsName`.
- Multilayer (single-part) EXR sequences from Unreal: `canImportAs(COMP_CROPPED_LAYERS)` says true, but
  the import came back as one footage item — the extra layers stay inside (EXtractoR), so ship mattes as
  their own image sequence.
- After the user restarts AE, check which project is open (`app.project.file`) before running anything
  that looks for comps by name; the unsaved state of the previous session is gone. Seen 4 Nov 2026:
  a fresh panel ran queued scripts against an empty Untitled project, then the heartbeat stalled
  until the user had the real project open and AE idle.
- ExtendScript is ES3: unquoted `in` / `out` / `native` (any ES3 reserved word) as object keys fail
  with "SyntaxError: Illegal use of reserved word" — write `{"in": L.inPoint, "native": …}`.

## Cinema 4D → AE 3D data (verified 4 Nov 2026, to 0.04 px)
- Positions: AE = `[W/2 + x·s, H/2 − y·s, z·s]` (C4D cm, s = compWidth / C4D render width; C4D origin
  at comp centre). Camera: `layers.addCamera`, position the same way, `pointOfInterest` = position +
  forward with Y negated, `cameraOption.zoom` = compWidth · focal / aperture (horizontal gate). Exact
  for bank 0 (POI cameras can't roll).
- 20 nulls × 841 keys via `position.setValuesAtTimes` + effects took 26 s. Check with an
  `ADBE Point Control` whose expression is `thisLayer.toComp(thisLayer.anchorPoint)`, read with
  `valueAtTime(t, false)` and compared with the C4D projection.
- Comp fps ≠ C4D fps or a still render in the comp: key at C4D seconds (f / fps_c4d) and drive the
  position with an expression `valueAtTime(f / fps)` where f comes from a control null (checkbox
  Animate → `time·fps + offset`, else a Still Frame slider). Expressions on a property with keys can
  `valueAtTime` their own keys; a checkbox works the same way (behind-the-globe visibility).

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
- In a 32-bpc OCIO/ACEScg project they came out **8-bit** RGBA, also far darker than the viewer, even
  for a comp ending in an OCIO Display Transform. A comp of **raw linear EXRs** (no display transform)
  puts a night sky on codes 0–2, so the gamma lift shows hard ovals and arcs that are pure 8-bit
  rounding, not in the footage. Check the code values (`np.unique`) before reporting banding, and
  judge gradients in the graded comp, not a raw layout comp.
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

## Swapping and adding renders (verified, AE 2026, 32 bpc OCIO project)
- A new version of a render already in comps: `footageItem.replaceWithSequence(new File(".../x.0000.exr"),
  false)` swaps the files under the same item; every comp layer, effect and timing stays. Re-set
  `mainSource.conformFrameRate` afterwards.
- To keep the previous version for A/B (re-render into a new folder, verified 5 Nov 2026): import the
  new sequence as its own item, copy the interpretation as below, check width/height match, then
  `layer.replaceSource(newItem, false)` — the layer keeps its anchor/position/scale/start; the old item
  stays in the project with `usedIn.length === 0`, so the user can swap back with Alt-drag.
- Footage colour management (input colour space) is not exposed to scripting (`mainSource.reflect`
  shows only alpha / premul). Copy it from a footage item the user set up: deselect all items, select
  that one, `app.executeCommand(app.findMenuCommandId("Remember Interpretation"))` (2254), select the new
  ones, `"Apply Interpretation"` (2255). It also copies alpha and frame-rate interpretation, so
  re-set `conformFrameRate` and `alphaMode` (EXR: `AlphaMode.PREMULTIPLIED`) after applying.
- New EXR sequence (verified 5 Nov 2026, ACEScg 16 bpc project): `io = new ImportOptions(new
  File(first.exr)); io.sequence = true; p.importFile(io)` gives one item named `x_[0000-0242].exr`.
- **List the target comp's layers right before adding**: the user may have put their own plate in
  meanwhile (here a `.mov` with OCIO/Adj above it). Take the plate layer's anchor/position/scale for
  the CG layer and `moveBefore(plate)` instead of adding a second plate. A `.mov` reporting 30.124 fps
  to OpenCV was interpreted by AE at native 30.
- `layer.copyToComp(comp)` keeps the source layer's index rather than landing on top: copying two
  adjustment layers came out in the wrong order. List the order afterwards and `moveToBeginning()`.
- A multilayer EXR imported as `ImportAsType.FOOTAGE` is one item showing the main RGBA; extra layers
  (depth, mattes) are read with the EXtractoR effect on a layer of it.
- On macOS `replaceWithSequence` kept `conformFrameRate` and `alphaMode` too; check them anyway.
- Movie → another movie: import it, then `layer.replaceSource(newItem, false)` per layer.
- Dropping time remap: `layer.timeRemapEnabled = false` removes the keys; set `inPoint` / `outPoint`
  back afterwards. A luma-matte layer of the same clip needs the same swap.
- Before moving or deleting old render folders, look for **symlinked version folders**
  (`find -L <dir> -type l` lists broken links): a `…_v003` folder was a symlink to `…_v002`, and moving
  v002 broke footage the project used. Re-check AE's missing footage afterwards.

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
- **Enabling Time Remap by script puts the end key at value = source duration.** For a precomp that
  time is past every layer's out point, so a "hold the last frame" extension showed an empty frame.
  Set the end key to the last frame (`duration - 1/fps`) and extend the out point; the value holds
  after the last key.
- Re-cutting an edit to a new VO (verified): per reused layer `startTime += delta` (keys and text
  animators move with it), then in/out; slow a clip with `layer.stretch` first, then `startTime`
  (`new_in - (old_in - old_start) * stretch/100`), then in/out; non-linear slow-downs with Time Remap
  keys (comp-time keys via `setValueAtTime`, add first, remove the old ones). Text layers whose
  animators animate out keep their own length — a longer out point doesn't keep them on screen.
- Before moving things, assert each captured layer's name (index → expected prefix) and stop if the
  comp changed; rename reused layers by the new shot (`F03 | …`) and park unused ones (`enabled =
  false`, `x unused | …`) instead of deleting.
- A reused title can end up under opaque footage (`duplicate()` lands right above its original,
  `layers.add` at index 1): check the stack and `moveBefore` the footage.
- Save-As: `app.project.save(new File(path))` switches the open project to the new file.
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

## HUD precomps with Essential Properties (verified 4 Nov 2026)
- Controls on a guide null inside the precomp; text/shapes read them by expression; expose with
  `prop.canAddToMotionGraphicsTemplate(comp)` + `prop.addToMotionGraphicsTemplateAs(comp, name)`.
  On an instance they live in `layer.property("ADBE Layer Overrides").property(name)` and accept
  expressions (e.g. a value computed from another layer). They list in reverse order of adding.
- Re-fetch effect properties by name after every `addProperty` (old references go invalid).
  `setPropertyParameters([...])` on a Dropdown Control replaces the effect: a lookup by its new name
  came back null — find it by `matchName === "ADBE Dropdown Control"` / `propertyIndex`, set the
  items, then set `name`, then the value.
- Corner brackets that follow a size slider: open paths with expressions
  `createPath([[-h,-h+L],[-h,-h],[-h+L,-h]], [], [], false)` in one group + one stroke. Hatch: a line
  + Repeater in a group rotated 45°, clipped by `layer.setTrackMatte(matte, TrackMatteType.ALPHA)`
  (matte `enabled = false`). One "ADBE Fill" effect per layer with its colour linked to the Color
  control tints text and strokes alike.
- A Point Control exposes fine as an Essential Property; on an instance give it the expression
  `thisComp.layer("Null").transform.position` and the precomp's text shows that layer's comp X/Y.

## Tracking footage for HUDs outside AE (verified 5 Nov 2026, EXR outro, 267 frames 4K)
- AE's tracker isn't scriptable; track in Python instead: `os.environ["OPENCV_IO_ENABLE_OPENEXR"]="1"`
  before `import cv2`, read EXRs with `IMREAD_UNCHANGED`, luminance → `L/(1+L)` → gamma → uint8.
- Candidates = blob centroids at the first frame; `calcOpticalFlowPyrLK` (31 px window, 4 levels)
  forward + backward, drop a point when the forward-backward error > 0.8 px. Then score per track
  (bright outline under the point, NCC vs the first-frame patch) — a smooth track can still sit on
  empty space after a sparkle fades, or between two icons merged into one blob. Check by eye with
  crop sheets at intervals.
- Re-centre with template matching (icon from frame 1, ±16 px around the LK prediction, sub-pixel
  peak, slow template update when score > 0.85), then Savitzky–Golay 7/2 (jitter 0.4 → 0.2 px).
- Prove the footage→comp mapping by rendering the comp itself with the HUDs off and circling the
  track points. `saveFrameToPng` is async, so toggle layers on a `comp.duplicate()`, render that, and
  delete it in a later script — never restore the user's layer switches in `finally` right after.

## Keeping this skill current
After a session that used the bridge, add only what was tested in a real project (mark the rest
*(unverified)*), correct wrong entries instead of appending, keep this file under ~300 lines,
commit and push the skills repo. Project-specific facts (comp names, timings, client) go to that
production's notes (see `project-notes`), never here.

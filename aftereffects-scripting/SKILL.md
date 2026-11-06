---
name: aftereffects-scripting
description: Read and build After Effects projects from a macOS shell via osascript + ExtendScript — comps, layers, markers, shot tables, review comps, importing passes from other apps, render-queue frame checks, cache purge, Save-As. Use when a task needs data from AE or should put renders into AE.
---

# After Effects scripting from the shell (verified AE 2026, macOS)

There is no AE MCP here. A shell on the Mac (e.g. a MacOS `Shell` tool) can drive the running AE
with AppleScript → ExtendScript. Works while AE is open with the project; no prefs had to be changed.

## Run a script and get results back
```bash
cat > /tmp/x.jsx <<'EOF'
(function(){
  var out = [];
  out.push("PROJECT: " + (app.project.file ? app.project.file.fsName : "unsaved"));
  // ... work ...
  var f = new File("/tmp/x_out.txt"); f.encoding = "UTF-8"; f.lineFeed = "Unix";
  f.open("w"); f.write(out.join("\n")); f.close(); return 1;
})();
EOF
osascript -e 'tell application "Adobe After Effects 2026" to DoScriptFile (POSIX file "/tmp/x.jsx")'
sleep 1; cat /tmp/x_out.txt
```
- **`DoScript` / `DoScriptFile` always return `0`** to osascript — the script's return value is lost.
  Write results to a file from the JSX and read that.
- Write the result file to an absolute path such as `/tmp/...`. A `new File("~/...")` path produced
  no file once (cause unclear).
- Without `f.lineFeed = "Unix"` the file has `\r` line endings.
- The app name includes the year (`"Adobe After Effects 2026"`). Check with
  `ps -axo comm | grep "After Effects"`.
- Wrap edits in `app.beginUndoGroup("…") / app.endUndoGroup()` so the user can undo in one step.
- A script that renders or imports a lot can outlast a remote shell's ~60 s limit: launch it in the
  background, `( osascript -e '…' >/dev/null 2>&1 & )`, then poll for the output file.
- **Memory:** `app.purge(PurgeTarget.ALL_CACHES)` took AE from 58 GB to 4 GB (it regrows while the
  user previews). Nothing in the project changes.
- **A stale "Executing Script …" window blocks every later script.** A check script that was running
  when the Mac's display went to sleep finished (its output file was written) but its progress window
  stayed open; AE then silently ignored new `DoScriptFile` calls (osascript returned, no output) until
  the user woke the display — and the ignored calls were NOT run afterwards: re-run them. With the
  screen locked and no stale window, scripts ran normally. If a script writes no output, list AE's
  windows (computer-use `computer_app_list_windows`; System Events shows none) and look for that title.

## Reading (verified)
```javascript
var p = app.project;
for (var i = 1; i <= p.numItems; i++) {            // 1-based
  var it = p.item(i);
  if (it instanceof CompItem)   { /* it.name, width, height, frameRate, duration, workAreaStart/Duration, numLayers */ }
  if (it instanceof FootageItem && it.file) { /* it.file.fsName, it.mainSource.conformFrameRate */ }
}
var L = comp.layer(n);  // L.name, L.inPoint, L.outPoint, L.startTime, L.enabled, L.hasAudio, L.audioEnabled
                        // L.source (item), L instanceof TextLayer -> L.property("Source Text").value.text
var mk = comp.markerProperty;  // mk.numKeys, mk.keyTime(k), mk.keyValue(k).comment; layer markers: L.property("Marker")
var rq = p.renderQueue.item(r); // rq.comp.name, rq.status, rq.outputModule(1).file.fsName
```
- A storyboard comp with one image layer per shot gives the edit directly: sort layers by `inPoint`
  and use **the next shot's in-point as the out-point** (layers often overlap by a frame).
- Audio offsets live in `startTime` (e.g. a mix layer at −4.017 s): comp time = audio time + startTime.
  Check `audioEnabled` to see which mix is live.
- Snap times to the delivery rate when it differs from the comp rate: frame = floor(s × fps + 0.5).
  Cuts on odd 60 fps frames fall between 30 fps frames.
- Print key and layer times in frames (`t * fps`, 3 decimals) when debugging — seconds rounded to
  2 decimals hide sub-frame offsets.
- Writing JSON: build the strings yourself. Reading it back inside JSX with a regex
  (`/"shot":"([^"]+)","in_s":([0-9.]+)/g`) worked. (unverified whether `JSON` exists in this ExtendScript.)

## Building a review comp (verified)
```javascript
var ft = p.importFile(new ImportOptions(new File(path)));      // mp4 / image sequence
var folder = p.items.addFolder("Animatic"); ft.parentFolder = folder;
var c = p.items.addComp("Animatic", 3840, 2160, 1, durationSec, 30); c.parentFolder = folder;
var base = c.layers.add(storyboardComp); base.audioEnabled = false;   // nested comps bring their audio
var v = c.layers.add(ft); v.property("Scale").setValue([200, 200]);   // 1080p render in a 4K comp
var op = v.property("Opacity");
op.setValueAtTime(frame / 30, 100);                                   // per shot: 100 or 0 — time from a frame number
for (var k = 1; k <= op.numKeys; k++) op.setInterpolationTypeAtKey(k, KeyframeInterpolationType.HOLD);
c.markerProperty.setValueAtTime(t, new MarkerValue("F03"));           // shot markers
var a = c.layers.add(audioComp); a.moveToEnd();                       // one audio layer only
c.openInViewer(); c.time = 55;
```
- Layers added later go on top. `layer.moveToEnd()` sends one to the bottom.
- Hold-keyed opacity is a simple way to show a render only in some shots, without splitting layers.
- **Put hold keys exactly on frames (`frame / fps`), never on rounded seconds.** A key at 9.17 s
  landed at 275.001 f, so frame 275 still showed the previous value (one frame of the layer below).
  Fix existing keys: for each key with `|t·fps − round(t·fps)|` between 1e-6 and 0.01, remember the
  value, `removeKey`, `addKey(round/fps)`, `setValueAtKey`, set HOLD in/out (loop from the last key).
- Don't import a render that's still being written (an mp4 has no index until it is finished).
  Wait until its size and mtime stop changing.
- **Never re-render over a file the open project uses.** AE's "Auto Reload Footage On Application
  Focus" (on for movie files) re-read mp4s while another app was overwriting them; its importer
  deadlocked (main thread in `CReloadUpdatedFootageFromDisk`) and AE had to be force-quit — twice.
  Render to a new versioned name, then swap by script once the file is finished:
  `item.replace(new File(path))` (movie) or `item.replaceWithSequence(firstFrameFile, false)`
  (sequence). Layers, timing, blend modes stay.
- Check the result with a background `computer_app_screenshot` of the AE window.

## One layer per shot instead of one long render (verified)
When each shot is rendered separately with handles (e.g. +6 frames each side):
```javascript
var item = p.importFile(new ImportOptions(new File(dir + "Proj_F02_VP.mp4"))); item.parentFolder = old.source.parentFolder;
var L = comp.layers.add(item); L.name = "VP F02"; L.moveBefore(old);   // same place in the stack as the long layer
L.startTime = firstRenderedFrame / 30;     // the handle frames sit before the cut
L.inPoint = cutIn / 30; L.outPoint = cutOutExclusive / 30;
L.property("ADBE Transform Group").property("ADBE Scale").setValue(oldScale);   // copy from the long layer
old.enabled = false;                       // keep the long layer, renamed, for rollback
```
- Re-runnable: if the footage item exists, `item.replace(new File(path))` instead of importing again;
  find the layer by name before adding.
- A shot that was hidden by opacity keys on the long layer gets `L.enabled = false`.

## Compositing passes from other apps (verified)
```javascript
var io = new ImportOptions(new File(base + "pass/pass.1046.png"));   // first frame of the sequence
io.sequence = true; io.forceAlphabetical = false;
var f = p.importFile(io); f.parentFolder = folder;
f.mainSource.conformFrameRate = 30;
f.mainSource.alphaMode = AlphaMode.STRAIGHT;     // straight-alpha PNG; AlphaMode.IGNORE for an additive EXR
var L = comp.layers.add(f);
L.startTime = 1046 / 30;                          // files numbered by 30 fps frame land at their time
L.moveBefore(baseLayer);                          // directly above it
L.blendingMode = BlendingMode.ADD;                // glow / emission passes
L.outPoint = shotEnd;                             // trim to the shot
```
- Match the transform of the render the pass sits on: `layers.add` gives 100 %, while a 1080p render
  in a 4K comp was at 200 % — the passes first came out half size in the middle of the frame.
- Several layers added with `moveBefore(x)` stack with the LAST one lowest (each goes right above x).
- Read transforms via match names: `L.property("ADBE Transform Group").property("ADBE Scale").valueAtTime(t, false)`.
  (Concatenating a plain `.value` into a string once threw "invalid numeric result (divide by
  zero?)" — cause unclear.)
- Make scripts re-runnable: remove the layers / footage they created before re-adding them.
- Reloading a finished re-render under the same name works (`item.replace(new File(item.file.fsName))`
  for mp4, `item.mainSource.reload()` for sequences), but prefer versioned names (see above).
- Pass types and modes (verified): multiply pass with white = untouched → straight-alpha PNG,
  `BlendingMode.MULTIPLY`; emission → linear EXR, `AlphaMode.IGNORE`, `BlendingMode.ADD`; light haze
  that must only brighten → `BlendingMode.SCREEN`. Copy the base layer's `startTime`, `inPoint`,
  `outPoint`, Scale and Position onto each pass layer.

## Time remapping: hold, play, hold (verified)
```javascript
L.startTime = f0 / fps; L.timeRemapEnabled = true;
var tr = L.property("ADBE Time Remapping"), autoEnd = tr.keyTime(tr.numKeys);   // AE adds keys at 0 and the end
tr.setValueAtTime(fPlay / fps, 0);                         // hold source frame 0 until fPlay
tr.setValueAtTime((fPlay + last) / fps, last / fps);       // then play 1:1 (last = source frames - 1)
// remove AE's automatic end key if it isn't one of yours, set all keys LINEAR,
// then L.outPoint = fEnd / fps — the last frame holds past the end of the clip
```

## Split screen with a transition (verified)
- One precomp per side (render + its passes, same size as the main comp), each added as a layer with
  a rectangular mask (`L.property("ADBE Mask Parade").addProperty("ADBE Mask Atom")`, `Shape` with
  `vertices` and `closed = true` on `"ADBE Mask Shape"`) and Position offset by ±¼ width.
- Transition: keyframe Position (one side slides out, the other to the centre) and the surviving
  side's mask shape from half to full frame; ease with `setTemporalEaseAtKey(k, [ease], [ease])`,
  `ease = new KeyframeEase(0, 75)` (one ease for Position and mask shapes; non-spatial array
  properties such as Scale want one per dimension — try one, fall back). A thin solid travelling with
  the seam hides the edge.

## Checking the comp with render-queue frames (verified)
```javascript
var rq = p.renderQueue;
for (var i = 1; i <= rq.numItems; i++) if (rq.item(i).status == RQItemStatus.QUEUED) rq.item(i).render = false;
var r = rq.items.add(comp);
r.timeSpanStart = t; r.timeSpanDuration = comp.frameDuration;
r.setSettings({"Resolution": [2, 2]});                   // half resolution
var om = r.outputModule(1);                              // pick a PNG template from om.templates
om.applyTemplate(pngTemplate); om.file = new File(dir + "check_[#####].png");
rq.render();                                              // blocking; then r.remove()
```
- These PNGs come out colour-managed like a real render (a viewer snapshot via `saveFrameToPng` did
  not in an ACEScg project). The frame number is appended to the name.
- Check frames at the cuts (first and last frame of each shot) after any change to layer timing;
  tile them into one contact sheet with ffmpeg (`-pattern_type glob -i 'check_*.png' -vf tile=2x4`).
- Review movies the same way: `timeSpanStart/Duration` = the segment, an H.264 template from
  `om.templates` (e.g. "H.264 - Match Render Settings - 5 Mbps"), half resolution — ~1,000 frames of
  a 4K comp with EXR/PNG passes rendered in about 1.5 min, audio included.

## Saving (verified)
- Save-As under the user's versioning convention, never over their file:
  `p.save(new File(".../Project 261008.aep"))` makes the open project the new file and leaves the old
  one untouched. Check `new File(path).exists` first, so nothing is overwritten.

## Keeping this skill current
After any session that used it, or whenever something new is verified:
1. Add gotchas/recipes ONLY if tested and working in a real project; mark anything else "(unverified)".
2. Correct entries that proved wrong — don't append contradictions.
3. Project-specific facts go to that project's notes (see `project-notes`), never into a skill.
4. Keep this SKILL.md under ~300 lines; split into `references/` when it grows.
5. Re-package every changed skill (keep names) and, if the skills live in a git repo, commit and push;
   in a public repo keep personal names and client details out of the text. Tell the user in one line
   what changed.

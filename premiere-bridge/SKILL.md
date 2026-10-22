---
name: premiere-bridge
description: Driving Adobe Premiere Pro from Claude without an MCP server, through a file-based ExtendScript bridge (a self-signed CEP panel that runs .jsx files dropped into an inbox folder and writes JSON results). Covers installing and signing the panel, sending scripts safely, inspecting projects/sequences/clips/bins, exporting preview frames, relinking media (e.g. to transcoded .mp4) with before/after verification, transcoding settings that keep Premiere's picture identical, and verified traps. Use whenever a task touches Premiere Pro / .prproj projects.
---

# Premiere Pro via the file bridge (verified Premiere 2026 / 26.5.2, Windows, CEP 12.0.1)

There is no Premiere MCP server here. `panel/` is a CEP extension ("Claude Bridge"): while it is
open, `index.html` calls `ClaudeBridge.tick()` in `host.jsx` about once a second. Each tick takes
every `*.jsx` in `<ROOT>/inbox`, **moves it to `done/` first**, runs it inside `(function(){ ... })()`
(so a top-level `return` works) and writes `<ROOT>/outbox/<name>.json` = `{file, ok, result |
error+line, ms}`. `<ROOT>/status.json` is rewritten every ~5 s: `{state: listening|paused|running,
time, file (while running), premiere, project, runs}`. Default `ROOT` is `D:/WORK/Claude/premiere-bridge`
(the `ROOT` line in `host.jsx`). `$.global.ClaudeBridge` exposes `ROOT`, `stringify`, `readText`,
`writeText`, `log` (shown in the panel) and `exportFrame` (below).

**Premiere has no scriptable undo groups**: a bridge script is not one Ctrl+Z. Before anything
destructive, work on a copy (`app.project.saveAs`, see Relinking) or have the user save first.

## Installing (verified)
- `scripts/install.ps1` sets `HKCU\Software\Adobe\CSXS.12\PlayerDebugMode = "1"` (string), self-signs
  the panel when `D:\WORK\Claude\premiere-bridge-signing\ZXPSignCmd.exe` exists, and copies it to
  `%APPDATA%\Adobe\CEP\extensions\com.claude.premierebridge`. Then Window › Extensions › Claude Bridge
  (with a project open; whether the Home screen offers it is unverified). Keep it docked so it stays
  open; whether it reopens by itself after a restart is unverified.
- **CEP 12.0.1 ignores PlayerDebugMode.** An unsigned panel just doesn't open: no window, no
  CEPHtmlEngine process. `%TEMP%\CEP12-PPRO.log` (needs `LogLevel` ≥ 1 under the same key) says
  `Signature verification failed for extension com.claude.premierebridge.panel`. Self-signing fixes
  it: `ZXPSignCmd.exe` 4.1.3 x64 from Adobe-CEP/CEP-Resources (`ZXPSignCMD/4.1.3/x64`, git blob
  `f5df2ed8…`; it has no Authenticode signature, so check the hash). The certificate and its
  password are created in the signing folder on first install. Never commit them.
- Premiere discovers new extensions only at start-up. After signing a panel Premiere had already
  discovered (and refused), clicking the menu item again loaded it without a restart.
- Every edit to a panel file breaks the signature: re-run `install.ps1`. A new `host.jsx` then loads
  via the panel's **Reload host**, or from a bridge script:
  `$.evalFile(Folder.userData.fsName + "/Adobe/CEP/extensions/com.claude.premierebridge/host.jsx")`
  (keeps the run count). A changed `index.html` needs the panel closed and reopened.

## Sending scripts
- Never write straight into `inbox/`: `scripts/send.sh NAME [timeout]` stages `$STAGE/NAME.jsx`
  under a non-`.jsx` name, renames it, waits for the JSON (env `BRIDGE` = ROOT). Number scripts
  (`023_snapshot.jsx`) so `done/` reads as a history.
- On a timeout `send.sh` reads `status.json`: `running X (started N s ago)` = Premiere is stuck in
  that script; a stale heartbeat = panel closed. A call that never returns (seen with QE
  `exportFramePNG`, below) leaves Premiere idle at 0 % CPU with a responsive UI, but the bridge is
  blocked until Premiere restarts. Scripts are claimed before they run, so the restart won't rerun it.
- `err.line` is the line in the script file. `JSON` exists in Premiere 26.5's ExtendScript.
- DOM objects stringify as `"<Project>"`, `"<Sequence>"`: copy the fields you need into plain objects.
- The regex literal `/\\/g` is a **SyntaxError** in ExtendScript; use `s.split("\\").join(...)` or
  `new RegExp("\\\\", "g")`. ExtendScript is ES3: a reserved word as an object key (`{ in: … }`)
  is a SyntaxError too ("Illegal use of reserved word"). Backslash paths written through sed/heredocs get mangled easily
  (`"y:\bbc"` is a backspace): build them with `String.fromCharCode(92)` or `File.fsName`.
- After only read-only scripts (plus `enableQE`, `exportFramePNG`, `openSequence`,
  `setPlayerPosition`) the title bar showed the project as modified (`*`); which call does it is
  unverified. Tell the user rather than letting them wonder about unsaved edits.

## Inspecting (verified)
- Time: 254016000000 ticks per second. `seq.timebase` = ticks per frame (string); `seq.end`,
  `seq.zeroPoint` = tick strings. Clip `start/end/inPoint/outPoint` are Time objects (`.seconds`,
  `.ticks` string). `seq.getInPoint()/getOutPoint()` return **seconds as strings**, `"-400000"` =
  not set. `seq.getSettings().videoFrameRate.seconds` = frame duration; `audioSampleRate` is a Time
  (1/48000 s). `seq.getPlayerPosition()` → Time; `seq.setPlayerPosition(ticksString)`.
- Tracks: `seq.videoTracks[i].clips[j]` (`numTracks`, `numItems`); `clip.projectItem`, `clip.nodeId`,
  `clip.mediaType`, `track.isMuted()`. Higher track index = on top.
- `ProjectItemType`: CLIP 1, BIN 2, ROOT 3, FILE 4. Sequences are CLIP items with `isSequence()`;
  map them via `app.project.sequences[i].projectItem.nodeId`. Walk bins via `rootItem.children`;
  `item.treePath`, `item.getMediaPath()`, `item.isOffline()`.
- "Used in these timelines, including nested ones": recurse through `clip.projectItem.nodeId` →
  sequence. Subclips (`X.mp4.Subclip01`) are separate items sharing the master's media path, so
  count a media path as used when any used item has it. `getInPoint()/getOutPoint()` on a subclip
  *project item* returned the whole file (0 to full length), not the subclip's range: take used
  source ranges from the track items' `inPoint/outPoint` (master-media time, timecode-based).
- `clip.getSpeed()` (1, 2, 0.75…) and `clip.isSpeedReversed()` (0/1) work on track items.
  `seq.getWorkAreaInPoint()/getWorkAreaOutPoint()` return seconds as strings, like `getInPoint`.
- **Timelines often park material after the edit.** One 1-minute edit ran to 94 minutes, with two
  full 30-minute B-roll files laid end to end after its out point. Before calling anything "used",
  compare clip positions with the sequence's out point and look for a big gap, and ask which
  counts. In that project the master items and their subclips were both used, several of them at
  far-apart points. An item links to one file only, so cutting a source into separate pieces
  cannot serve such an item. *(Unverified idea: re-encode at full length
  with unused stretches blacked out, which keeps timing and every link intact.)*
- ProjectItem in 26.5 has no delete for clips (`deleteBin` only), plus `moveBin`, `changeMediaPath`,
  `canChangeMediaPath`, `findItemsMatchingMediaPath`, `isMergedClip`, `isMulticamClip`,
  `setOffline`, `createSubClip`, `saveProjectSnapshot` (list from `item.reflect.methods`).
- `app.project.openSequence(sequenceID)` activates a sequence (returns true); `qe.project
  .getActiveSequence()` follows it within the same script.

## Exporting frames (verified)
- `ClaudeBridge.exportFrame(timecode, name)` → `<ROOT>/frames/<name>.png` at full sequence size,
  synchronously (4K ≈ 0.3–1 s), from the active sequence. Timecode as QE gives it (`"00:00:26:11"`).
  For an exact moment: `openSequence(id)`, `setPlayerPosition(ticks)`, then
  `qe.project.getActiveSequence().CTI.timecode`. The time argument is honoured.
- Why the helper exists: QE `exportFramePNG(timecode, pathWithoutExtension)` appends `.png` and
  **escape-processes its path**. After a backslash, a digit starts an octal escape (`\009_cti` cut the
  path, so `…\frames\009_cti` wrote `…\frames.png`; `\123` became `S`). Lowercase a–e lose the
  backslash (`…\frames\d2\abc_def` wrote `…\framesd2abc_def.png`). **`\F` hung Premiere for good.**
  Forward slashes, a `.png` ending or doubled backslashes throw "Unknown error exception".
  Lowercase f–z and uppercase A–E survive. The helper allows names `[f-z][a-z0-9_-]*` only and
  refuses folders with an unsafe segment.
- Look at frames with Pillow (`uv run --with pillow python -I …`): before|after side by side plus a 1:1
  centre crop shows both framing and fine detail.

## Relinking media (verified on a 249-item, 17-sequence project)
- Work on a copy: `app.project.saveAs(fsPath)` saves the open state to the new file **and switches
  the open project to it**. The original file keeps its old save (mtime unchanged).
- `item.changeMediaPath(newPath, false)` relinked ProRes/MJPEG `.mov` → HEVC `.mp4` and NAS → local
  paths for 225 items without the override flag. `canChangeMediaPath()` is false for Motion Graphics
  Template items (`.aegraphic`): they can't be relinked by script.
- Premiere keeps linked media open. To replace an `.mp4` in place, relink the item elsewhere (e.g.
  back to the `.mov`), overwrite the file, then relink again.
- An image-sequence item (`X.0001.png`) relinks to a movie with `changeMediaPath` too. A 172-frame
  RGBA PNG sequence became a lossless PNG-in-MOV (`ffmpeg -framerate 25 -start_number 1 -i
  X.%04d.png -c:v png -pix_fmt rgba -f mov`, the same 102 MB as the frames). It kept its 25 fps
  interpretation, length and alpha settings, and the composite check frames were pixel-identical.
  Check alpha before choosing MP4: `getFootageInterpretation()` gives `frameRate`, `alphaUsage`,
  `ignoreAlpha`, and Pillow shows whether alpha really drops below 255.
- `changeMediaPath` also works on items that went offline (files removed outside Premiere).
  `item.isOffline()` finds them. Check `isOffline` after any file moves the user may make too.
- **Prove nothing moved**: before and after, snapshot every clip in the affected sequences (seq, track,
  index, name, start/end/in/out ticks) and export a check frame mid-clip for each changed medium.
  Ticks must be identical. Compare frames with numpy: PSNR plus mean level shift. Healthy HEVC
  re-encodes gave 35–48 dB with a shift of about −0.3. An edge-glow effect on a clip amplified the same
  compression to about 26 dB (identical framing). A levels problem shows as a steady shift (+9).

## Transcoding for a relink (verified, ffmpeg 7.1.1, RTX 4090)
- HEVC 10-bit on NVENC: `-map 0:v:0 -map 0:a? -map_metadata 0 -c:v hevc_nvenc -preset p7 -tune hq
  -rc vbr -multipass fullres -b:v 40M -maxrate 60M -bufsize 120M` (HD: 20M/30M) `-profile:v main10
  -pix_fmt p010le -tag:v hvc1 -c:a aac -b:a 320k -movflags +faststart`, plus `-timecode <source tc>`
  when the source has one. Write `.part` and rename on success. 17.7 GB of 4K ProRes LT (Topaz
  upscales) became 1.1 GB in about 2.5 min. Premiere read the timecode: in/out stayed identical,
  including sources starting at 01:40:00:00 and 21:55:31:16.
- Before relinking, check every output against its source with ffprobe: `nb_frames`, rate, size,
  timecode, audio streams.
- **MJPEG sources** (`yuvj422p`: full range, BT.601 matrix). A plain `-pix_fmt p010le` writes
  video-range pixels but keeps the `pc` flag, and Premiere showed lifted blacks. Use
  `-vf scale=in_range=pc:out_range=tv:in_color_matrix=bt601:out_color_matrix=bt709,format=p010le,setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv`.
  The `-color_trc`/`-color_primaries` output options do **not** override tags carried by the
  frames; `setparams` does. A leftover sRGB transfer tag (`iec61966-2-1`) on the HEVC made Premiere 26
  render it brighter than the MJPEG with the same tag; forcing bt709 matched.
- Leave alpha sources alone (ProRes 4444 `yuva…`, QuickTime RLE `argb`): MP4 drops the alpha.
  Re-encoding small or already-H.264 `.mov` files saves little and costs a generation.

## Keeping this skill current
After a session that used the bridge, add only what was tested in a real project (mark the rest
*(unverified)*), correct wrong entries instead of appending, keep this file under ~300 lines, and
commit and push the skills repo. Project-specific facts (sequence names, paths, clients) go to that
production's notes (see `project-notes`), never here.

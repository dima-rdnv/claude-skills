# After Effects bridge on macOS (verified AE 2026)

These notes were verified with the earlier ScriptUI panel (`ClaudeBridge.jsx`), which uses the same
inbox, outbox, signing and `send.sh` as the CEP panel in `../SKILL.md`. **The CEP panel has not been
tested on macOS yet**, and `install.ps1` is Windows-only.

## The panel
- CEP (untested on macOS): a signed copy made with `install.ps1 -ShareTo <dir>` on Windows goes into
  `~/Library/Application Support/Adobe/CEP/extensions/`; AE finds it at start-up, under Window › Extensions.
- ScriptUI (verified, with the limits listed under "Why not a ScriptUI panel" in `../SKILL.md`): the file
  is in this repo's history, `git show afc3c01^:aftereffects-bridge/scripts/ClaudeBridge.jsx`. It lands in
  `~/Library/Preferences/Adobe/After Effects/<ver>/Scripts/ScriptUI Panels/` (File › Scripts › Install
  ScriptUI Panel…), and needs Preferences › Scripting & Expressions › *Allow Scripts to Write Files and
  Access Network*. Restart AE, Window › ClaudeBridge.jsx, dock it.
- To reach AE with no panel at all, see `aftereffects-scripting` (AppleScript → ExtendScript).

## Starting and sending
- **AE not running:** `open -a "Adobe After Effects 2026"` from the shell brought AE up with the
  docked panel listening; a ping answered ~1 min later without the user. The project opens from a
  bridge script (`app.open`) — check `app.project.dirty` first.
- Default ROOT `~/Documents/ClaudeBridge` (inbox / outbox / done). Keep a copy of `send.sh` and the
  scripts in a local, non-synced stage folder and run from the Mac shell:
  `STAGE=<stage> BRIDGE=~/Documents/ClaudeBridge ./send.sh 010_name 120`. The first call creates
  `~/.claude/ae-bridge.key`; the panel accepted the signed scripts straight away.
- A shared include (`$.evalFile(new File("~/stage/shots.jsxinc"))`) keeps tables (shot list, paths)
  in one place; keep it out of synced folders (evalFile'd files skip the signature check).
- `$.global.ClaudeBridge.writeText(pathString, text)` failed ("Function f.open is undefined"). For
  big results write your own file (`new File(path)`, `encoding = "UTF-8"`, open/write/close) and read
  it from the shell; return only a short summary.

## Preview frames
- 32-bpc project: the 16-bit RGBA PNGs looked dark too; Homebrew ffmpeg handled them fine:
  `ffmpeg -pattern_type glob -i 'v2_*.png' -vf "format=rgb48le,lutrgb=r=gammaval(0.4545):g=gammaval(0.4545):b=gammaval(0.4545),scale=480:270,format=rgb24,tile=5x6:padding=4:color=gray" -frames:v 1 sheet.jpg`.
- Seeing the sheet from a cloud sandbox with only a shell to the Mac: `base64 -i sheet.jpg`; when the
  result is too long for the reply it is saved as a JSON file in the sandbox's tool-results folder —
  decode its `result` string there (worked up to ~310 kB of base64).

## Render queue
- **`rq.render()` from a bridge script rendered nothing** — it returned after a few seconds with every
  item still QUEUED (status 3015). The same queue code run through AppleScript rendered normally:
  `( osascript -e 'tell application "Adobe After Effects 2026" to DoScriptFile (POSIX file "/tmp/x.jsx")' >/dev/null 2>&1 & )`,
  the JSX writes its result to a file; poll the output file. Remove the queue items your attempt
  left behind. For still frames use `saveFrameToPng` instead.

## Rendering without the GUI: aerender
- `aerender -project "<aep>" -rqindex N -mem_usage 30 50 -mfr ON 90 > log 2>&1 &` renders render-queue
  item N in a separate background AE that quits when done; the GUI instance stays usable. Set the
  item's output path and settings in a bridge script first, Save-As a render copy, close it in the GUI.
  Progress = `PROGRESS:  <frame>` lines in the log. 6021 frames, half-res 4K, 32 bpc in 16 min.
- A Windows output path stored in the item (`H:/…`) was remapped by AE to the same relative place on
  the Mac; still point outputs at a new local file (never over footage the project uses).
- **Footage on Google Drive (File Provider):** cloud-only files are fetched on read, one by one — the
  render stalled at the first frame of every new sequence (~1.5 files/s with 8 parallel `cat`s).
  Count them first (`stat -f %Sf * | grep -c dataless`), then prefetch in frame order with a
  48-thread Python reader (`open(p,'rb').read()` per file): 12–15 files/s, 8000 files in 11 min.

## Storyboard PDF pages as images
Render every page with JXA + PDFKit (no extra tools):
`osascript -l JavaScript pdf2png.js <pdf> <outdir> 4000` where the script does
`$.PDFDocument.alloc.initWithURL($.NSURL.fileURLWithPath(pdf))`, and per page an
`NSBitmapImageRep` (W × H), `NSGraphicsContext.graphicsContextWithBitmapImageRep`, white fill,
`CGContextScaleCTM` to the page box, `page.drawWithBoxToContext(kPDFDisplayBoxMediaBox, ctx.CGContext)`,
`representationUsingTypeProperties(NSBitmapImageFileTypePNG)` → `writeToFileAtomically`. Crop the
picture areas with Pillow (16:9 cover crop for full pictures, fit + white pad for split panels),
import them as placeholders and the full pages as a timed storyboard precomp.

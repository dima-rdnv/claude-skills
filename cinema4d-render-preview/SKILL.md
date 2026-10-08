---
name: cinema4d-render-preview
description: "Look at Cinema 4D renders from the sandbox: render a stepped clone to a base64 JPEG, crops and contact sheets, isolate one effect, compare with reference footage, viewport screenshots. Load with cinema4d-mcp."
---

# Render previews from Cinema 4D (verified C4D 2026.1 Windows, Redshift, dual RTX 4090)

## Rule of thumb
Check numbers first (particle counts, lit-pixel count and bbox), then pay for an image. Render a
**clone** of the active document so the user's scene, time and selection stay untouched.

## One frame, cropped/downscaled, over a background colour
```python
import base64
def main():
    FRAME, W, H = 45, 1920, 2700                 # full render size (keep the scene aspect)
    X0, Y0, X1, Y1, S = 0, 700, 1920, 2300, 2    # crop box + downscale step
    BG = (27, 56, 42)                            # composite colour for alpha renders
    doc = c4d.documents.GetActiveDocument().GetClone(c4d.COPYFLAGS_DOCUMENT)
    pv = doc.SearchObject("Preview")             # hide reference planes etc. in the clone only
    if pv: pv[c4d.ID_BASEOBJECT_VISIBILITY_RENDER] = 1
    fps = doc.GetFps()
    for f in range(0, FRAME + 1):                # simulations must be stepped from 0
        doc.SetTime(c4d.BaseTime(f, fps)); doc.ExecutePasses(None, True, True, True, 0)
    rd = doc.GetActiveRenderData().GetClone()
    rd[c4d.RDATA_XRES], rd[c4d.RDATA_YRES] = W, H
    rd[c4d.RDATA_FRAMESEQUENCE] = c4d.RDATA_FRAMESEQUENCE_CURRENTFRAME; rd[c4d.RDATA_SAVEIMAGE] = False
    bmp = c4d.bitmaps.MultipassBitmap(W, H, c4d.COLORMODE_RGB); bmp.AddChannel(True, True)
    res = c4d.documents.RenderDocument(doc, rd.GetDataInstance(), bmp,
            c4d.RENDERFLAGS_EXTERNAL | c4d.RENDERFLAGS_NODOCUMENTCLONE)   # keep the stepped sim state
    a = bmp.GetInternalChannel()
    cw, ch = (X1 - X0) // S, (Y1 - Y0) // S
    out = c4d.bitmaps.BaseBitmap(); out.Init(cw, ch, 24)
    for y in range(ch):
        for x in range(cw):
            px, py = X0 + x * S, Y0 + y * S
            r, g, b = bmp.GetPixel(px, py); k = bmp.GetAlphaPixel(a, px, py) / 255.0
            out.SetPixel(x, y, int(min(255, r + BG[0]*(1-k))), int(min(255, g + BG[1]*(1-k))), int(min(255, b + BG[2]*(1-k))))
    mfs = c4d.storage.MemoryFileStruct(); mfs.SetMemoryWriteMode()
    out.Save(mfs, c4d.FILTER_JPG); data, size = mfs.GetData()
    print("res", res); print("B64:" + base64.b64encode(bytes(data)[:size]).decode())
    c4d.documents.KillDocument(doc)
main()
```
- `res` 0 = OK. `MemoryFileStruct` avoids the file system, which gives the same path on Windows and Mac.
- Rendering the clone at render resolution with RENDERFLAGS_NODOCUMENTCLONE kept the particle
  sim. Redshift rendered native Particle Groups and Cloner instances correctly this way.
- Point sampling (S > 1) drops fine dust. For contact sheets, box-filter S×S blocks (average RGB and
  alpha) so fine dust survives the downscale.

## Contact sheet of several frames in one call
Step 0 → max frame once, and at each wanted frame render and paste into a
`BaseBitmap(cw * len(FRAMES), ch)` at x offset `i * cw`. Verified inside the 60 s limit: 5 frames at
1152×1620 with a 3×3 box filter, plus a 105-frame sim of ~12k particles.
- Rough cost: the Python pixel loop is ~1–2 s per 300k output pixels. The Redshift render itself
  took a few seconds at 1920×2700.

## Isolating one effect / finding an event (verified)
- To show only some particle groups, hide the rest **in the clone**: RS Object tag `3000=0` on the
  groups, render visibility off on Cloners. Don't zero rig user data: it may be keyframed, and the
  track overrides the value on every ExecutePasses.
- Find the event while stepping (e.g. the first frame a group's count jumps), take the centroid of
  the newborn particles (age < 1.5/fps), project it with `loc = ~cam.GetMg() * p`,
  `px = W/2 + loc.x/loc.z * W * focal/aperture`, `py = H/2 - loc.y/loc.z * W * focal/aperture`
  (verified with focal = aperture = 36 mm), then render crops around it at event+N frames.

## Getting the image into the sandbox
- Replies above ~50k characters are saved to
  `/root/.claude/projects/.../tool-results/<tool>-<id>.txt` (JSON `{"result": "..."}`). Smaller
  replies come back inline and are hard to decode: end the script with `print("#" * 60000)` to
  force the file.
- Decode:
```python
import json, base64, re, sys
t = json.load(open(sys.argv[1]))['result']
open(sys.argv[2], 'wb').write(base64.b64decode(re.search(r'B64:([A-Za-z0-9+/=]+)', t).group(1)))
```
  then `Read` the JPEG to look at it. Deliverable previews go to `/mnt/user-data/outputs/`.

## Cheap numeric check (no image)
Render small (480×675), loop every 2nd pixel, and count `r+g+b > 40` plus the bbox of lit pixels.
This confirms something rendered, and where, before spending tokens on an image.

## Reference footage and PSDs in the sandbox
- ProRes 4444 with alpha over a colour, as a contact sheet:
  `ffmpeg -f lavfi -i color=c=0x1a3a2a:s=1920x1080 -i ref.mov -filter_complex "[0][1]overlay=shortest=1,select='not(mod(n\,16))',scale=480:-1,tile=4x4" -frames:v 1 -vsync vfr sheet.png`
- A single frame: `select='eq(n\,40)'`. A detail: add `crop=w:h:x:y`.
- PSD: `pip install psd-tools --break-system-packages`, then `PSDImage.open(p).composite()`. Use
  `p.descendants()` for layer names and bboxes (smart objects are listed but render only in the composite).
- Measure in the reference (element sizes in px, trail width, timing in frames), convert with the
  scene's px/cm (camera focal, distance, render width), and compare with the same frames of yours.

## Viewport screenshot (computer use)
- `computer_resolve_access(["Maxon Cinema 4D 2026"])` → `computer_request_access` → `computer_screenshot`
  / `computer_zoom`. Other apps get hidden while granted.
- After a script changes time, call `c4d.EventAdd()` before the screenshot. The viewport draws
  particles (dots) and Cloner instances. A timeline click at "|<" etc. may start playback: check
  the play button state and stop it.
## Keeping this skill current
After any session that used Houdini/Cinema 4D via MCP, or whenever something new is verified:
1. Add gotchas/recipes ONLY if tested and working in a real scene; mark anything else "(unverified)".
2. Correct entries that proved wrong — don't append contradictions.
3. Put each finding in the skill it belongs to (see the indexes in `houdini-mcp` and `cinema4d-mcp`);
   project-specific facts go to that project's notes (see `project-notes`), never into a skill.
4. Keep each SKILL.md under ~300 lines; split into a new sub-skill or `references/` when it grows.
5. Re-package every changed skill (keep names) and, if the skills live in a git repo, commit and push.
   Tell the user in one line what changed.
---
name: houdini-flipbook
description: Rendering Houdini viewport flipbooks and OpenGL ROP passes to image sequences through MCP / hython — real alpha from hython, a camera copied from Cinema 4D, volume visualization for smoke / fire passes. Use for flipbooks, playblasts, OpenGL renders or Houdini passes to composite. Load with houdini-mcp.
---

# Viewport flipbooks and OpenGL passes (verified Houdini 21 Indie, macOS)

## Flipbook from the GUI (verified: 1920×1080 PNGs)
```python
sv = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
vp = sv.curViewport()
prev = vp.settings().colorScheme()
vp.settings().setColorScheme(hou.viewportColorScheme.Dark)   # dark background
s = sv.flipbookSettings().stash()
s.frameRange((start, end)); s.frameIncrement(1)
s.output(os.path.join(out_dir, 'name_$F4.png'))
s.outputToMPlay(False)
s.useResolution(True); s.resolution((1920, 1080))
sv.flipbook(vp, s)
# vp.settings().setColorScheme(prev)   # restore, unless the user prefers it dark
```
- A dark background reads better for particles. If the user wants it kept dark, set it on all
  SceneViewer viewports: `for vp in pt.viewports(): vp.settings().setColorScheme(Dark)`.
- Flipbooks the CURRENT viewport view and the displayed node — set the display node first.
- It cooks frames in order (sims build correctly) but blocks the bridge for minutes. Monitor from a
  shell: file count in the output folder, `sips -g pixelWidth -g pixelHeight`.
- Output folders: follow the user's convention (see the project's notes), e.g. a new
  `<YYMMDD HHMM> <index>` folder per flipbook built from `datetime.now()`.

## OpenGL ROP passes for compositing (verified)
- `/out` → `opengl` ROP. Parms: `camera`; `vobjects` '' + `forceobjects` (renders only these objects,
  their display flag off is fine); `alights` '' + `forcelights`; `trange` 1, `f1/f2/f3` (delete their
  keyframes before `set()`); `picture`; `mkpath` 1; `aamode` 'aa8'; `colorcorrect` 'lut_gamma'
  (gamma 2.2) or 'none' (linear); `volumequality`; `particle` ('points', 'discs', 'litsphere', …).
- **For alpha, render with hython.** The same ROP rendered from the GUI wrote alpha = 1 everywhere
  (opaque viewport background, PNG and EXR). Rendered by `hython` (`rop.render()` in a script, see
  `houdini-mcp`) it wrote a transparent background: PNG = straight (unpremultiplied) RGBA, alpha =
  volume coverage. It ran headless on macOS at ~2–4 fps for 1080p volume frames; two jobs in parallel.
- GUI-only fallback for a matte: a second object with the same volume, albedo 0 and **emission =
  extinction** (`emitfield` density with the same scale and ramp mode as the density) → RGB equals
  coverage (its mean matched the hython alpha within ~2 %). Lit pass + matte = a premultiplied pair.
- Emission-only passes (fire glow): an 8-bit straight-alpha PNG clamps them (glow turned into white
  fog). Render linear EXR (`colorcorrect` none) with almost no absorption and add it in the
  compositor (AE: blending Add, alpha Ignore).
- **A SOP Solver feeding two ROPs: render each ROP in its own hython process.** Rendered one after
  the other in one session, the second ROP's first frames came out with the solver's state (and
  geometry) from a much later frame — the solver cache had dropped the early frames during the first
  ROP (long shots only: 400+ solver steps; short shots were fine). Check: the alpha of two passes of
  the same geometry must match (`hoiiotool a.exr --ch A b.png --ch A --diff` → mean error ~1e-6).
  Separate processes (or a file cache of the solver) fixed it; they can run in parallel.
- 30 fps edit from a 60 fps scene: `f3` = 2 and `picture` ending `` .`padzero(4, $F/2)`.png `` → file
  numbers are the 30 fps frames.
- Geometry passes (particles as small instanced octahedra): object `shop_materialpath` →
  `principledshader::2.0` with `reflect` 0, `rough` 1; delete point `Cd` so the material colour wins.
- **The OpenGL ROP ignores emission from point colour** (`emitcolor_usePointColor`): a pass meant to
  show per-point colours as emission came out plain white.
- **Flat point-colour pass (verified):** material `basecolor` (1,1,1) + `basecolor_usePointColor` 1,
  `reflect` 0, `rough` 1, `emitint` 0; light it with ONE `ambient` light object through
  `forcelights`, `light_intensity` **10**. GL ambient contributes 0.1 × intensity (measured: 1 → 0.10,
  9.66 → 0.962), so 10 gives rendered RGB = Cd exactly, with no shading falloff. ROP: `shadows` 0,
  `hqlighting` 0, `colorcorrect` 0 (raw values). Lighting clamps at 1.0, so keep Cd ≤ 1 (scale a
  glow up in the compositor, or write it as EXR and Add it).
- Pass types built this way: a **multiply pass** (white = untouched, tint/char darker; straight-alpha
  PNG, Multiply in the compositor) and an **emission pass** (black = nothing; linear EXR, Add) — two
  ROPs on the same geometry with different Cd.
- **Houdini 22 (Vulkan viewport): an OpenGL ROP in hython crashed on the 2nd frame** of a mesh whose
  topology changes per frame (`GR_FillAttributesVK::createNormalAttribute`); the first frame always
  rendered. Workaround: one hython process per frame (verified Nov 2026).

## Same camera as Cinema 4D (verified)
- Map the world spaces first by comparing a few parts' bboxes in both apps. Seen: C4D → Houdini =
  ×0.1 (a transform on the imported Alembic) and **z negated** (C4D's Alembic export flips handedness).
- C4D cameras look down +Z, Houdini cameras down −Z. With z flipped, a C4D camera with identity
  rotation maps to a Houdini camera with rotation 0 at (x, y, −z) × scale.
- **Rotated / moving cameras (verified, pass matched the C4D render exactly):** export the camera's
  global matrix per frame from C4D (`off, v1, v2, v3`). In Houdini, with F = diag(1, 1, −1):
  rows = (v1·F, v2·F, −(v3·F)), translate = (x, y, −z) × scale → `hou.Matrix4(...).explode()` →
  linear keys on tx…rz.
- Lens: Houdini `focal` = C4D focal length; `aperture` = sensor width when the camera fits
  horizontally. Redshift Camera object (type 1057516) ids: 500 focal (mm), 7002 sensor size (vector,
  36×24), 7005 Fit (0 Fill-Crop, 1 Horizontal, 2 Vertical, 3 Overscan-Fit, 4 Square), 7012 shift.
- Bake the animation per frame: in C4D sample `track.GetCurve().GetValue(c4d.BaseTime(f, fps))` for
  every frame and write JSON with `open()`; in Houdini `parm.setKeyframes([...])` with `linear()` keys
  (9001 keys in one call, instant).
- Verify framing: render the same frame of an engine part in both and compare silhouettes (matched
  within a few pixels at 1080p).
- **Cutaway views:** geometry hidden in the C4D render (a cut-open liner) still exists as a Houdini
  collider. Drop points the cut view can't show (front half, behind solid moving parts — e.g. below
  the piston crown via a `bbox()` spare parm) before rendering.

## Volume visualization for GL passes (verified)
`volumevisualization` SOP after the cache reader (`object_merge` of the sim's `file` SOP):
- `densityfield` density. `densityrampmode` 'none' = raw density × `densityscale`; 'clamp' with
  `rangemin/rangemax` = min(d / range, 1) × scale (tames very dense frames, e.g. a burn at density 90).
- Albedo: `cdfield` + `cdramp` (black smoke ~0.07–0.12 grey; white haze ~0.8).
- Glow: `emitfield` (e.g. temperature) + `emitrangeoverride`, `emitrange1/2`, `emitrampmode`,
  `emitscale`; colour from `emitcdfield` + `emitcdramp` (dark red → orange → pale yellow).
- Lights: a distant `hlight::2.0` (`light_type` 'distant') + a dim `envlight`, via `forcelights`.
- Starting values for a ~1-unit chamber at 0.01 voxels: black smoke (density 1–4) raw ×1.5; white
  haze clamp 0..2 ×2; glow temperature 0..1 ×3–4.
- **White haze over a dark plate:** thin lit haze averages to grey over a dark background and reads
  as soot/black smoke (turning shadows off and albedo up barely changed it). Verified fix: make it
  self-lit — `emitfield` density, `emitscale` ~0.9, `densityscale` 3, white albedo and emission ramps,
  `shadows` 0 — and put the layer on **Screen** in the compositor so it can only brighten.

## Checking passes
- Alpha present? `ffmpeg -i f.png -vf "alphaextract,format=gray,signalstats,metadata=mode=print" -f null - 2>&1 | grep YAVG`
- Over the other app's frame: `ffmpeg -i bg.png -i pass.png -filter_complex "[0]scale=1920:1080[b];[b][1]overlay=format=auto" out.png`
  (straight alpha). Look at it before rendering the full range.

## Keeping this skill current
After any session that used Houdini/Cinema 4D via MCP, or whenever something new is verified:
1. Add gotchas/recipes ONLY if tested and working in a real scene; mark anything else "(unverified)".
2. Correct entries that proved wrong — don't append contradictions.
3. Put each finding in the skill it belongs to (see the indexes in `houdini-mcp` and `cinema4d-mcp`);
   project-specific facts go to that project's notes (see `project-notes`), never into a skill.
4. Keep each SKILL.md under ~300 lines; split into a new sub-skill or `references/` when it grows.
5. Re-package every changed skill (keep names) and, if the skills live in a git repo, commit and push;
   in a public repo keep personal names and client details out of the text. Tell the user in one line
   what changed.

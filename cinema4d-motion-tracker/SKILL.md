---
name: cinema4d-motion-tracker
description: Cinema 4D Motion Tracker through Python/MCP - reading 2D tracks and the 3D solve, diagnosing why a solve stops (occlusion, missing overlap), re-running the solver from a script, segment solves, extending a camera solve past an occlusion with PnP + triangulation + bundle adjustment, setting real-world scale from a person or object of known size, baking the result to a clean camera, footage backgrounds. Load with cinema4d-mcp.
---

# Motion Tracker via Python (verified C4D 2026.4, Windows, Maxon MCP adapter)

## Reading the tracker
- `from c4d.modules import motiontracker` exists. On the Motion Tracker object:
  `td = mt.Get2dTrackData()` → `GetTrackCount()`, `GetTrackByIndex(i)`, `GetTrackByName(n)`;
  `fd = mt.GetFootageData()`.
- Track: `GetName()` ("Auto 0139"), `GetStatus()`, `GetFramesWithTrackData()` returns a
  **BaseSelect** (not a list — use `bs.IsSelected(f)`), `GetDataForFrame(f).GetPixelPosition(fd, True)`
  (both arguments required; pixels, origin top-left). `fd.GetResolutionWidthPix(True)` likewise needs the flag.
- 3D features are nulls under `Motion Tracker/Auto Features`, **named after their 2D track**, so a
  feature and its track pair up by name. The camera is `Motion Tracker/Solved Camera` (RS camera in
  a Redshift doc), keyed once per solved frame (Focal + Pos + Rot tracks) — key range = solved range.
- Parameter ids: footage path 10500 · frame start/stop 10509/10510 · focal mode 43001
  (43002 Unknown, 43003 Unknown but Constant, 43004 Known and Constant) · focal 43005 · sensor 43006 ·
  solve mode 43450 · lock solved data 43038 · **Run 3D Solver = CallButton(mt, 43032)**.
- Projection that reproduces the tracks (checked to ~5 px): `q = (P − c)·[v1 v2 v3]` (camera matrix
  columns, normalised), `u = W/2 + f_px·qx/qz`, `v = H/2 − f_px·qy/qz`, `f_px = focal/aperture·W`.

## Why a solve stops, and what to check
- Count alive tracks per frame and, more importantly, **tracks that span the problem frames**
  (`first ≤ a and last ≥ b`). An occluder sweeping across (car pillar) leaves enough tracks per
  frame but very few that bridge it, and the solver ends the solve there. A re-solve with identical
  settings returns the identical range — the solver is deterministic, don't retry blindly.
- The solve range is the camera key range; frames before the first key (often black/slate frames)
  simply aren't solved.

## Running the solver from a script
- `c4d.CallButton(mt, 43032)` returns at once; the solver runs in the background: the camera's
  tracks are cleared immediately and filled 30–90 s later. Poll (key count / feature count) from
  later calls; you can't wait inside `exec_python`. Do it on a **copy document**
  (`doc.GetClone()` + `InsertBaseDocument`, keep the user's doc active), close it with `KillDocument`.
- Segment solve: set frame start (10509) on the copy and re-run — the solver then only uses that range.
- **Lock the focal length for short segments.** A 60-frame interior segment solved "Unknown but
  Constant" came back at 11.4 mm vs 34.4 mm from the long solve of the same lens — too little
  parallax. Set 43001 = 43004 and 43005 = the long solve's focal.
- `CallButton(mt, 20009)` (Create Background Object) did nothing from a script.
- Stitching two independent solves via shared features failed (8 shared points, 148° error) —
  extend the trusted solve instead (next section).

## Extending a solve past an occlusion (verified: 29–183 → 29–241, 2–8 px median)
1. `scripts/export_solve.py` (in C4D, edit OUT) → solves.json: solved cameras, 3D features, every 2D track.
2. `scripts/extend_solve.py solves.json extended.json [END_A]` (local, `uv run --with numpy --with scipy
   --with opencv-python-headless python -I …`). Per frame after END_A: triangulate new tracks seen in
   ≥ 6 posed frames of the last 25 (parallax ≥ 0.7°, reprojection ≤ 2.5 px), then `solvePnPRansac`
   (4 px, seeded with the previous pose) + `solvePnPRefineLM`; finally a sparse bundle adjustment
   (vectorised residuals + `jac_sparsity`, Huber) over the tail with frames ≤ END_A−15 fixed, which
   keeps the original solve's gauge and scale. A Python-loop residual with dense finite differences
   is far too slow — keep it vectorised.
   - C4D's world is left-handed; for OpenCV mirror world points with `S = diag(1,1,−1)`:
     `R_cv = diag(1,−1,1)·Rᵀ·S`, `t_cv = −diag(1,−1,1)·Rᵀ·c`; back: `c = S·(−R_cvᵀ t)`, `R = S·R_cvᵀ·diag(1,−1,1)`.
3. Check per-frame reprojection and frame-to-frame rotation steps. An isolated jolt (1–2° in one
   frame) whose slerp-interpolated replacement reprojects better (3.6 vs 10.2 px) is a solver glitch —
   interpolate it. Global Gaussian smoothing did not help overall.
4. `scripts/bake_camera.py` (in C4D, undo=true): clones the Solved Camera (keeps lens/sensor),
   strips Protection + tracks, keys pos/rot per frame (`MatrixToHPB` + `GetOptimalAngle` against the
   previous frame to avoid flips, linear keys), adds feature nulls. Leave the Motion Tracker untouched.
5. Verify inside C4D: re-project the baked feature nulls through the baked camera against the 2D tracks.

## Real-world scale
- Scaling every position (camera path + points) about the origin by K leaves the image identical
  (focal unchanged), so scale is one factor chosen at bake time.
- From a person: measure a body size in pixels (head crown→chin ≈ 22–23 cm incl. hair, ear→nose tip
  ≈ 11 cm, glasses temple hinge→ear ≈ 10 cm), `Z_real = f_px · size / px`; take the solved depth of
  feature points on that body part (+ half the head depth for profile measurements); `K = Z_real / Z_solved`.
  The three head measures spread ±15 % — average them.
- Verify with a wireframe sphere of known size (20 cm ≈ a head) placed at the points' centroid and a
  viewport capture through the baked camera.
- A car in the same shot gave K ≈ 18 against 11.5 from the person: the car is **driving** while the
  camera follows it, so its points are wrongly triangulated. Scale from what is static relative to
  where you'll place things; say so when references disagree.

## Footage background for a new camera (viewport only)
`Mmaterial` with luminance = `Xbitmap` (BITMAPSHADER_FILENAME = the tracker's footage path, then
`CallButton(shader, c4d.BITMAPSHADER_CALCULATE)` sets movie timing/fps), on an `Obackground` with a
frontal Texture tag, render visibility off. Switch the view: `doc.GetActiveBaseDraw().SetSceneCamera(cam)`.
Hide the Motion Tracker in the editor while checking — its track-path display clutters the view.

## Keeping this skill current
Add only what was tested in a real scene (mark the rest *(unverified)*), correct wrong entries,
keep under ~300 lines, commit and push the skills repo. Shot-specific numbers go in project notes.

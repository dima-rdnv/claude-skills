---
name: unreal-led-volume-rig
description: Multi-screen LED box / CAVE camera rigs in Unreal Engine 5.8 — reading an existing Cinema 4D rig (one eye point, one off-axis camera per wall) with c4dpy, converting C4D film offsets to UE CineCamera sensor offsets, rebuilding the frusta so the walls meet edge to edge, keeping the rig level on a moving rail, one shot sequence + Movie Render Queue preset per screen (different resolutions), and checking the five views. Load with unreal-mcp and unreal-sequencer-python when a render must play on several screens of a room.
---

# LED box / CAVE rigs (one eye, one off-axis camera per screen)

Verified Oct 2026: a 5-screen LED room (front, left, right, ceiling, floor) rebuilt in UE 5.8.4 from
the C4D rig that rendered the room's precomps.

## Find the real rig
- The playback project (e.g. an Unreal VR walkthrough of the room) usually only *plays* the videos
  (FileMediaSource → MediaPlayer → MediaTexture). Read the media sources' file paths (strings inside the
  .uasset) → the delivered videos → their resolutions (`tkhd` box of the .mp4) — and look next to the
  render logs for the scene that made them (C4D batch-render XML logs name the take, camera, render
  setting, resolution, fps).
- An unfolded test video (e.g. 8000x7020 = side+front+side wide, ceiling+front+floor tall) confirms the
  layout.

## Read a C4D rig headless (c4dpy, read-only)
`c4dpy g_licenseModel=LICENSEMODEL::MAXONAPP dump.py scene.c4d out.json < /dev/null` (see the user's
c4dpy memory). Load with `SCENEFILTER_OBJECTS`; for each `CAM*` object: parents, `GetMl()`, `GetMg()` at a
few frames, `CAMERA_FOCUS`, `CAMERAOBJECT_APERTURE` (sensor width), `CAMERAOBJECT_FILM_OFFSET_X/Y`;
render data (`RDATA_XRES/YRES/FILMASPECT/FRAMERATE`); takes (`GetCamera(td)`, `GetRenderData(td)`).
A 750 MB scene loaded in ~40 s.

## Film offsets C4D → Unreal (derived from a consistent room, then from UE source)
- C4D: X = fraction of the film WIDTH, + shifts the view right; Y = fraction of the film HEIGHT,
  + shifts the view DOWN. (Checked by rebuilding the room: with this convention every wall edge meets
  its neighbour within 0.1 %, and each wall's aspect equals its render aspect.)
- UE CineCamera filmback `SensorHorizontalOffset` / `SensorVerticalOffset` (mm, 5.8): becomes
  `OffCenterProjectionOffset = 2·offset / sensor size` and the projection uses `M[2][0] = -offX` →
  + looks right / up.
- So `h_mm = X · sensor_w`, `v_mm = −Y · sensor_h`, `sensor_h = sensor_w · res_y / res_x`.
- Orientation C4D (X right, Y up, Z forward) → UE (X forward, Y right, Z up): front (0,0,0), left
  yaw −90, right yaw +90, ceiling pitch +90 (image up = backwards), floor pitch −90 (image up = forward).

## Rig on a rail
- All cameras at one eye point on the mount, relative location 0. Keep the box LEVEL: world rotation =
  `compose_rotators(screen_rotation, Rotator(yaw=rail_yaw))`, set with `set_actor_rotation` after
  attaching (a rail locked to a climbing spline would tilt the room's horizon). Re-level after moving
  the rail.
- Eye height matters: in the room the eye sits at the wall-height ratio (e.g. 0.425 × front distance
  above the floor ≈ 1.8 m); a virtual eye 30 cm above the ground reads as crawling.

## One video per screen
- One shot sequence per screen: the main sequence as a SubTrack section + a CameraCut to that screen's
  camera. **The main sequence must have no camera cut** — MRQ used the inner sequence's cut over the
  shot's (all five renders came out as the front view, letterboxed).
- One `MoviePipelinePrimaryConfig` per screen (`AssetTools.create_asset(..., MoviePipelinePrimaryConfig,
  MoviePipelinePrimaryConfigFactory())`) with that screen's `output_resolution` — one job per screen
  (a job has one resolution; "render all cameras" can't mix sizes).
- Checking: render one frame per screen (custom playback range, quarter scale) and paste them into the
  unfolded layout. `AutomationLibrary.take_high_res_screenshot(camera=...)` ignored the camera while
  the viewport piloted another one and forced the viewport aspect — not usable for this.
- Quick look through one off-axis camera without rendering: `CaptureViewport` (90° horizontal FOV, viewport
  aspect) from the camera's location, pitched to the frame's centre angle (atan(sensor_v_offset /
  focal)), then crop columns ±(sensor_w/2)/focal and rows to tan range [(-h/2 + v_off)/focal,
  (h/2 + v_off)/focal] (px = W/2 per tan unit, rows through the pitch). Matched an MRQ frame of the same
  shot within ~8 %. No DoF, and editor-preview lighting.

## A rig that moves (camera path from C4D, verified Nov 2026)
- When the C4D rig null is animated, skip the parent actor: read the null's world matrix every frame (c4dpy, frames stepped
  in order) and each camera's local matrix once, then key every CineCamera's own transform per frame in the master
  sequence (`MovieScene3DTransformTrack`, channels loc x/y/z, rot roll/pitch/yaw;
  `ch.add_key(unreal.FrameNumber(f), v, 0.0, unreal.MovieSceneTimeUnit.DISPLAY_RATE, unreal.MovieSceneKeyInterpolation.LINEAR)`).
  Rotation from the C4D camera axes through the import's axis mapping: `make_rot_from_xz(M(v3), M(v2))`.
- With an FBX/Interchange-imported scene the mapping is UE = C4D (x, -z, y) (not the (z, x, y) of a hand-built room): the
  front camera faces -Y (yaw -90), left -X, right +X - build the cameras with the same mapping as the geometry.
- **Spatial effects per wall in After Effects (glow, blur) break the seams** (verified Nov 2026, AE 2026, Optical Glow):
  an effect inside each wall comp only sees its own wall, so a halo stops dead at the edge. Fix: per wall a pad comp =
  the wall + its neighbours **laid flat** around it (the walls share one pixel pitch, so each neighbour is a 0/90/270-degree
  rotation + translation, anchored at the shared corner; compute it from the rig: one eye, Front plane at distance 1,
  every other plane through the Front frustum edge it shares), the effect on a pad-sized adjustment layer (copy every
  parameter value), and the pad comp centred in the wall comp in place of source + effect (originals switched off).
  Both pads at a seam then hold the same picture around it and the glow meets. Seam steps measured on one frame went
  from 2-4x the no-glow step back to it.
  - Pad size: the halo's tail sets it; Optical Glow Size 176 still added ~30 % of its seam value 1000 px in, so pad 1024.
    Pad-sized glow costs ~1 s/frame per wall at ~5000 px squares.
  - Perspective strips (neighbour warped into the wall's extended image plane with a homography / Corner Pin) are
    worse: the two cameras' pixel densities differ 1.8-3.9x at a seam, so the two pads see the seam differently.
  - Walls overlap by ~2 px at the seams. With semi-transparent layers (a light-trail pass) a neighbour under the wall
    doubles the alpha into a bright 2 px line: put the neighbours in their own comp with a pixel-exact Subtract mask over
    the wall's rectangle.
  - **Check the effect settings on every wall first.** One seam kept a step until it turned out that wall's glow had
    different values (Amount / Highlights Only) - per-wall settings can't meet at a seam whatever the padding.
  - Measure seams on exported frames: compare the last pixel row/column of one wall with the first of its neighbour
    against the step between two neighbouring rows inside a wall, with and without the effect.
- **Unfolded check**: render one frame per wall at full size and paste them into the unfolded box - the walls tile at one
  pixel density (e.g. 2884 px over a front of 2 x 0.5473 eye-units = 2635 px/unit; side walls 2560 px over depth
  0.0284..1.0, ceiling 2882 px over -0.0939..1.0, floor 2342 px over 0.1118..1.0): front at (side_w, top_h), left at
  (0, top_h), right at (side_w + front_w, top_h), top at (side_w, 0), floor at (side_w, top_h + front_h). Lines must run
  straight across every edge.

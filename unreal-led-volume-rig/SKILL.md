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

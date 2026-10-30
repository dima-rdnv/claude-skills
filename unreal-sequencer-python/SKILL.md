---
name: unreal-sequencer-python
description: Building Unreal Engine 5.8 Level Sequences from Python — cine camera with keyed transform, a camera on a movable Camera Rig Rail (key only the rail position), camera cut track, animating a Material Parameter Collection value, a LevelSequenceActor that auto-plays on Play, re-running the build safely, and checking the result in Play-In-Editor through the Unreal MCP. Load with unreal-mcp.
---

# Level Sequences from Python

Verified Oct 2026, UE 5.8.4, run through `ue_exec.py` (see `unreal-mcp`). Checked in PIE: the
camera cut took over the view and the MPC value drove the material.

## Create or reuse the sequence
```python
AT, EAL = unreal.AssetToolsHelpers.get_asset_tools(), unreal.EditorAssetLibrary
seq = EAL.load_asset(path) if EAL.does_asset_exist(path) else \
      AT.create_asset(name, folder, unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
for b in list(seq.get_bindings()): b.remove()
for t in list(seq.get_tracks()): seq.remove_track(t)
seq.set_display_rate(unreal.FrameRate(24, 1))
seq.set_playback_start(0); seq.set_playback_end(720)      # display-rate frames
```
**Don't delete and recreate a sequence (or material) that is loaded/used:** `delete_asset` fails
with "Failed to unload all packages during ForceDeleteObjects" (an Ensure in the log) and the
following `create_asset` returns None. Reuse and clear it instead.

## Camera with keyed transform
```python
cam = eas.spawn_actor_from_class(unreal.CineCameraActor, start)
cc = cam.get_cine_camera_component()
cc.set_editor_property("current_focal_length", 24.0)
fs = cc.get_editor_property("focus_settings")
fs.set_editor_property("focus_method", unreal.CameraFocusMethod.DISABLE)   # no depth of field
cc.set_editor_property("focus_settings", fs)

binding = seq.add_possessable(cam)
sec = binding.add_track(unreal.MovieScene3DTransformTrack).add_section()
sec.set_range(0, 720)
ch = {c.get_name().rsplit("_", 1)[0]: c for c in sec.get_all_channels()}
ch["Location.Y"].add_key(unreal.FrameNumber(0), -34000.0, 0.0,
                         unreal.MovieSceneTimeUnit.DISPLAY_RATE, unreal.MovieSceneKeyInterpolation.LINEAR)
```
- Channel names carry a numeric suffix (`Location.X_1`, `Rotation.Z_3` ...) — strip it.
  Rotation.X = roll, .Y = pitch, .Z = yaw.
- `unreal.Rotator(roll=, pitch=, yaw=)` — use keywords; the positional order is roll, pitch, yaw.

## Camera on a rail the user can move (Camera Rig Rail)
Better than keyed transforms when the user wants to place the path themselves: the sequence keys only
the rail position, so moving / rotating / stretching the rail never breaks the animation.
```python
rail = eas.spawn_actor_from_class(unreal.CameraRig_Rail, start)
rail.set_editor_property("lock_orientation_to_rail", True)      # camera looks along the rail
rail.set_editor_property("show_rail_visualization", False)      # see below
# convention: actor at the start, facing along the path; spline along local X -> moving, rotating or
# piloting the rail actor moves the whole path
rail.set_actor_location_and_rotation(start, unreal.MathLibrary.find_look_at_rotation(start, end), False, False)
sp = rail.get_rail_spline_component()
sp.clear_spline_points(False)
for x in (0.0, (end - start).length()):
    sp.add_spline_point(unreal.Vector(x, 0, 0), unreal.SplineCoordinateSpace.LOCAL, False)
for i in range(2): sp.set_spline_point_type(i, unreal.SplinePointType.LINEAR, False)
sp.update_spline()
snap = unreal.AttachmentRule.SNAP_TO_TARGET
cam.attach_to_actor(rail, "", snap, snap, unreal.AttachmentRule.KEEP_WORLD, False)  # -> RailCameraMount
t = seq.add_possessable(rail).add_track(unreal.MovieSceneFloatTrack)
t.set_property_name_and_path("Current Position On Rail", "CurrentPositionOnRail")
s = t.add_section(); s.set_range(0, 480)
ch = s.get_all_channels()[0]          # key (f/480)**3 on every frame, LINEAR
cam_binding = seq.add_possessable(cam)  # no transform track; use it for the camera cut
```
From the engine source (`CameraRig_Rail.cpp`): position is **by distance**
(`GetLocationAtDistanceAlongSpline(CurrentPositionOnRail * SplineLength)`), so an eased key curve keeps
its speed profile whatever the rail length. The mount is updated in the rail's **Tick**
(`ShouldTickIfViewportsOnly` = true) and on PostEditChange/Move — after moving the playhead from
Python, read the camera's transform in a LATER remote call. To predict the camera's path without the
editor (e.g. to bake something along it): `get_location_at_distance_along_spline` /
`get_rotation_at_distance_along_spline` (WORLD) composed with the camera's transform relative to the
`RailCameraMount` component (`MathLibrary.compose_transforms(rel, at)`) — matched the scrubbed camera
to the centimetre.
- `show_rail_visualization` also drives the preview mount mesh (`SM_RailRig_Mount`), which sits right
  in front of the lens when you look through the camera in the editor (hidden in game/MRQ anyway).
  Off = no track mesh, but selecting the rail still draws its spline and points to drag.
- **Trap — Sequencer restores the old transform after you re-parent:** the camera had a keyed transform
  track; the script removed the bindings, attached the camera to the rail (snap = zero offset), and on
  the next evaluation Sequencer restored the camera's pre-animated transform — its old WORLD location
  landed as the RELATIVE offset (camera 1 km away, moving with the rail). Zero the relative
  location/rotation in a later call (`set_actor_relative_location/rotation`); it doesn't recur once
  no transform track is left.

## Camera cut
```python
cut = seq.add_track(unreal.MovieSceneCameraCutTrack).add_section()
cut.set_range(0, 720)
cut.set_camera_binding_id(seq.get_portable_binding_id(seq, binding))
```

## Animating a Material Parameter Collection value
```python
t = seq.add_track(unreal.MovieSceneMaterialParameterCollectionTrack)
t.set_editor_property("mpc", unreal.load_asset("/Game/.../MPC_X"))
s = t.add_section(); s.set_range(0, 720)
s.add_scalar_parameter_key("Time", unreal.FrameNumber(0), 0.0)   # creates the channel ("Time_1")
c = [c for c in s.get_all_channels() if "Time" in c.get_name()][0]
for k in list(c.get_keys()): c.remove_key(k)                      # then key it like any channel
```

## Play it on Play
```python
lsa = eas.spawn_actor_from_class(unreal.LevelSequenceActor, loc)
lsa.set_sequence(seq)
ps = lsa.get_editor_property("playback_settings")
ps.set_editor_property("auto_play", True)
lsa.set_editor_property("playback_settings", ps)
```
The camera cut track takes over the player's view during playback. To keep free control of the
player camera while the sequence still animates everything else (e.g. a material parameter), set
`ps.set_editor_property("disable_camera_cuts", True)` on the same playback settings (verified).

## Easing and hard cuts
- Non-linear motion (e.g. an accelerating camera, distance ~ (t/T)^3): key the channel on every
  frame with LINEAR interpolation — exact and simple (481 keys for 20 s at 24 fps is fine).
- Hard switches of a parameter: keys with `unreal.MovieSceneKeyInterpolation.CONSTANT`
  (0 at frame 0, 1 at the switch frame).

## Previewing a moment in the editor
```python
LSE = unreal.LevelSequenceEditorBlueprintLibrary
if LSE.get_current_level_sequence() != seq: LSE.open_level_sequence(seq)
LSE.set_current_time(frame)            # deprecated overload but works in 5.8; display-rate frames
LSE.refresh_current_level_sequence()
```
This evaluates every track on the editor world (camera position, MPC values). **While a sequence
is open in Sequencer, it re-evaluates its MPC track and overwrites values you set directly with
`MaterialLibrary.set_scalar_parameter_value`** — preview through the playhead instead (verified:
a direct preview got reset to frame-0 values before the capture).

## Reading it back
`seq.get_bindings()` → `b.get_tracks()` → `t.get_sections()` → `s.get_all_channels()` →
`c.get_keys()` → `k.get_time().frame_number.value`, `k.get_value()`.
`MovieSceneObjectBindingID` prints as an empty struct from Python — verify the cut in PIE.

## Checking in Play-In-Editor through the Unreal MCP
`EditorAppToolset.StartPIE` with `{"options": {"bSimulate": false, "playMode":
"PlayMode_InViewPort", "warmupSeconds": 6}}` (returns after warm-up), then
`EditorAppToolset.CaptureEditorImage` (whole editor window, ~350 KB → decode with
`unreal-mcp/scripts/decode_capture.py`), later captures after a background `sleep`, then
`StopPIE`. CaptureViewport needs a capture pose and would not show the sequence camera.

## Related traps
- `/Engine/BasicShapes/Plane` has **no collision** — a pawn falls through a floor made of it; use
  a thin scaled Cube.
- The Film/Video template's `DefaultInput.ini` has `bAlwaysShowTouchInterface=True` (on-screen
  joysticks in Play). The joystick check (`SVirtualJoystick::ShouldDisplayTouchInterface`) reads
  the in-memory config, not the settings object, so editing the ini or the CDO alone needs an editor
  restart. Without restarting: set it on the CDO and call `save_key_mappings()` (= SaveConfig):
  ```python
  s = unreal.InputSettings.get_default_object()
  s.set_editor_property("always_show_touch_interface", False); s.save_key_mappings()
  ```
  (verified: joysticks gone in the next PIE). Also set it in `Config/DefaultInput.ini` to persist.

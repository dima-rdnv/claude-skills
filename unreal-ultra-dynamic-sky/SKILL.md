---
name: unreal-ultra-dynamic-sky
description: Ultra Dynamic Sky (UDS, Fab plugin content) in Unreal Engine 5.8 driven from Claude — adding the Ultra_Dynamic_Sky actor in place of a template sun/sky/fog, reading and setting its ~1000 Blueprint variables through the Unreal MCP ObjectTools, and locking exposure for renders (Manual mode goes black; lock the Histogram range instead). Load with unreal-mcp.
---

# Ultra Dynamic Sky from Claude

Verified Oct 2026, UE 5.8.4, UDS content in `/Game/UltraDynamicSky` (Blueprints:
`Ultra_Dynamic_Sky`, `Ultra_Dynamic_Weather`, `Configuration_Manager`, `Volumetric_Cloud_Painter`).

## Adding it to a level
UDS brings its own sun, moon, sky light, sky atmosphere, height fog, volumetric clouds and a
post-process component. Remove the level's DirectionalLight, SkyLight, SkyAtmosphere,
ExponentialHeightFog, VolumetricCloud and any sky-sphere mesh first, then:
```python
cls = unreal.EditorAssetLibrary.load_blueprint_class("/Game/UltraDynamicSky/Blueprints/Ultra_Dynamic_Sky")
uds = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(cls, unreal.Vector(0, 0, 0))
```
Defaults seen on spawn: Time of Day 960, Sky Mode "Volumetric Clouds", Cloud Coverage 3.8, Fog 1,
Sun Light Intensity 5 (UDS's own scale, not physical lux), exposure = Histogram auto exposure.
The actor draws an editor-only sun/moon target gizmo that shows up in MCP viewport captures even
with `bShowUI false` (not in renders).

## Reading and setting its variables
Python `get_editor_property("time_of_day")` does NOT find Blueprint variables with spaces. Use the
Unreal MCP ObjectTools with the display name, lower-case first letter:
- `ObjectTools.list_properties` → JSON schema of every variable (~1000 keys, 330 KB; parse from the
  saved tool-result file). Keys look like `"time of Day"`, `"cloud Coverage"`, `"exposure Bias Day"`.
- `ObjectTools.get_properties(instance, ["time of Day", "fog"])`
- `ObjectTools.set_properties(instance, values='{"time of Day": 1030}')` — `values` is a JSON
  *string*. Enums are passed by name (`"AEM_Histogram"`); FloatRange as
  `{"lowerBound": {"type": "Inclusive", "value": -1}, "upperBound": {"type": "Inclusive", "value": -1}}`.
  The change applies in the editor right away (construction script reruns).

## Locked exposure for renders
Auto exposure changes the brightness of everything (e.g. as a graphic colour fills the frame), so
lock it for final renders:
- `exposure Metering Mode = AEM_Manual` → black frame: UDS's lights are scaled for auto exposure,
  while manual mode applies the physical camera EV (~10). Bias -10 still gave black in the editor
  capture *(why not further explored)*.
- **Works:** keep `AEM_Histogram` and set `exposure Brightness Range` lower = upper (e.g. -1.0 →
  fixed EV100 -1, a good daylight value at Time of Day 960 with default sun). `exposure Bias Day`
  0. EV100 1.5 was far too dark.
- Other exposure keys: `exposure Bias Dawn/Dusk`, `exposure Bias Night`, `exposure Bias Cloudy`,
  `exposure Bias Foggy`, `exposure Compensation Curve`, `apply Exposure Settings`.

## Other keys worth knowing
`animate Time of Day`, `sun Light Intensity`, `sky Light Intensity`, `sky Light Mode`,
`render Exponential Height Fog`, `base Fog Density`, `scale Fog Density`, `use Volumetric Fog`,
`dust Amount`, `enable Sun Lens Flare`, `enable Sun Light Shaft Bloom`, `simulate Real Sun`,
`cinematic Clouds ...` (sample counts used when the project mode is Cinematic/Offline).

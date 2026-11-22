---
name: cinema4d-to-unreal
description: Moving a Cinema 4D + Redshift scene into Unreal Engine 5.8 for Path Tracer renders - baking and exporting the geometry (FBX, not USD), keeping material slots, translating Redshift node graphs into Unreal material instances by script, MoGraph animation as Alembic geometry caches, camera-invisible emitters, the axis mapping, and calibrating the Unreal look against a Redshift frame. Load with unreal-mcp (and cinema4d-mcp for the c4dpy side).
---

# Cinema 4D + Redshift -> Unreal 5.8 (Path Tracer)

Verified Nov 2026: C4D 2027.0 (c4dpy) -> UE 5.8.4, a 2.5M-polygon rack scene with 17 instanced devices, 39 Redshift
materials, MoGraph tracer/sweep light lines and a 5-screen LED camera rig. Result: framing identical, mean colour within
3 % of the Redshift frame, ~4 s/frame at 128 spp 2884x1800 on an RTX 4090 (Redshift: 14 min/frame).

## 1. Export the geometry from c4dpy (FBX, not USD)
- **C4D 2027's USD exporter was not usable**: identical-looking (empty) Redshift node materials were merged into
  `DisplayColor_*` materials (slot names lost), and render instances came out as cyclic references ("Cycle detected",
  the instanced objects missing). glTF kept material names but every material plain white; FBX "Bake Materials" failed on
  every node material ("Illegal state: Invalid Space"). No format carries Redshift graphs.
- Work on `td.TakeToDocument(take)` of the take you render (take visibility baked in), keep only the subtree you need.
- **Bake generators AND instances** with `MCOMMAND_CURRENTSTATETOOBJECT` (outermost visible generators first, repeat
  2-3 passes; Python Generators, Cloners, Sweeps, Extrudes, Connect, Instance objects). Insert the result where the
  generator was (`doc.InsertObject(new, parent=g.GetUp(), pred=g)`, `new.SetMg(g.GetMg())`), copy its texture tags.
  Then delete what is not render-visible (first explicit on/off up the hierarchy wins; a disabled generator hides).
  Unreal's Interchange re-shares identical meshes; Nanite doesn't mind the extra polygons.
- Compare C4D objects with `==`, never `is` (each access returns a new Python wrapper: `o is not geo` removed `geo`).
- **Material slots survive only as placeholders**: give every used material a unique FBX-safe name
  (`re.sub(r"[^A-Za-z0-9_]", "_", name)`, `__2` for duplicates), dump its Redshift graph to JSON (section 3), then put a
  classic `Mmaterial` with that name and a unique colour on the same texture tags and **remove every other material** from
  the document (otherwise the exporter renames yours `Name.1`). The exporter still appends `.1` to some names and
  Interchange turns `.` into `_` - match slots by stripping `[._]\d+$`.
- FBX exporter ids (2027): 1023 Cameras, 1022 Lights, 1024 Splines, 1033 Instances, 1016 Triangulate, 1014 Normals,
  1035 Up Axis (1036 = Y), 1034 Flip Z, 1004 Tracks, 1046 Takes (1047 None), 1005 Material, 1010 Embed Textures,
  1029 Substances, 1039 Bake Materials. Set geometry + normals + material on, everything else off.

## 2. Import into Unreal
- `mgr = unreal.InterchangeManager.get_interchange_manager_scripted()`; `src = unreal.InterchangeManager.create_source_data(fbx)`;
  `p = unreal.ImportAssetParameters(); p.is_automated = True`; `mgr.import_scene(dest, src, p)` -> static meshes (Nanite
  already on) + actors with the hierarchy in the open level (1311 meshes in ~2 min).
- **The scene import puts per-actor override materials on every StaticMeshActor** (its own placeholder materials). They
  hide anything you assign on the mesh assets: clear them (`for i in range(c.get_num_materials()): c.set_material(i, None)`,
  `c.set_editor_property("override_materials", [])`), then delete the placeholder materials.
- **Axes**: Unreal (x, y, z) = Cinema 4D (x, -z, y) - for the FBX scene import and for Alembic with conversion
  scale (1, -1, 1), rotation (90, 0, 0), flip V. Check once against a known object's position / a bbox.

## 3. Translate the Redshift graphs (script, not rebuild)
- Dump per material (c4dpy, maxon API): every node's asset id and every input port's value, plus its connection
  (`port.GetConnections(maxon.PORT_DIR.INPUT, conns)` -> source node + port id). The `texturesampler.tex0` path is the
  child port `path`. **Ramp knots**: the `rsramp.ramp` port has child ports `_0, _1, ...` with `position`, `color`,
  `interpolation`, `bias` (a missing position = 0).
- **Redshift enum values, MEASURED** (C4D 2027 + RS; one emissive plane per value, rendered with Commandline):
  `rscolorcomposite.comp_mode` 0 = base, 1 = blend (over), 2 = average, **3 = add**, 4 = subtract (base - blend),
  **5 = multiply**, 9 = screen (6-8 unclear: 7 ~ lighten/max, 8 ~ darken/min). `rsramp.inputmapping` 0 = along V,
  1 = along U (with `inputsource` 2 = UV). Guessing 3 = multiply / 5 = min gave grey streak-only ribbons instead of the
  coloured ones. To measure another enum: build the planes in c4dpy (constants via `SetPortValue(maxon.ColorA(...))`,
  `maxon.Int32(...)`), render with Commandline; a fresh c4dpy document's output carries a colour transform (0.6 came out
  0.44), so also render the inputs as reference planes and compare candidates through a 3x3 fitted from them.
- Ramps of BOTH mappings combined in one shader (U streaks x V fades + V colour cycle) are 2D: bake a U x V texture
  (512x512 was plenty) instead of a 1D gradient; emission above 1 needs a half-float EXR (imports as Texture2D).
- Two masters cover typical scenes:
  `M_RS_Standard` (two-sided like Redshift's single planes): BaseColor vector or BaseTex (StaticSwitch) x weight,
  Roughness, Metallic, Specular, EmissiveColor x EmissiveWeight, opacity mask from BaseTex.A or a MaskTex (StaticSwitches;
  the MI switches its blend mode to Masked through `base_property_overrides`);
  `M_RS_Clear`: translucent, refraction method Index of Refraction, BaseColor / Opacity / Roughness / IOR - for
  `refr_weight` > 0.5.
- Mapping from `standardmaterial`: base_color (+ base_color_weight), refl_roughness, metalness,
  Specular = refl_weight x F0(refl_ior) / 0.08 (UE 0.5 = F0 0.04), emission_color x emission_weight,
  opacity_color from `rscolorsplitter.outa` -> the base texture's alpha, from a texturesampler -> separate mask.
  Not translated: ramps / colour layers on roughness, curvature, round corners, bump (constant fallback, note them).
- Only translate what is visible: materials of hidden objects (e.g. replaced hardware) drop out; meshes reached only
  through instances count as visible.
- Textures: import the files the graphs point to (`relative:///` = relative to the .c4d folder), set
  `power_of_two_mode = STRETCH_TO_POWER_OF_TWO` on non-power-of-two images (mips; the path tracer aliases without them).
- A Substance node can't be exported: rebuild procedurally (world-position projection when the mesh has no UVs;
  in the path tracer derive normals analytically - no ddx/ddy).

## 4. MoGraph animation -> Alembic geometry caches
- Tracer + Sweep + Cloner + Displacer setups bake fine to Alembic from c4dpy: select the Sweep objects, `ABCEXPORT_SELECTION_ONLY`,
  frame range, `ABCEXPORT_GLOBAL_MATRIX`, UVs + normals on.
- **The first Alembic export of a c4dpy session comes out empty (~1 KB)**, whichever object it is: export the first one twice.
- Import: `AbcImportSettings` with `import_type = GEOMETRY_CACHE`, `conversion_settings` (preset CUSTOM, flip_v, scale,
  rotation as above), `sampling_settings` frame range, `geometry_cache_settings.flatten_tracks = True`,
  `apply_constant_topology_optimizations = False` (varying topology).
- Play it in Sequencer: binding + `MovieSceneGeometryCacheTrack`, section over the range,
  `params.geometry_cache_asset = <cache>` (set the struct back with `set_editor_property("params", ...)`).
- Check placement: `comp.set_editor_property("manual_tick", True); comp.tick_at_this_time(t, False, False, False)` then
  actor bounds against the C4D bbox at that frame (stepped from frame 0 - tracers need history).

## 5. Lights
- RS Dome with a texture -> SkyLight `SLS_SPECIFIED_CUBEMAP`. Unreal makes cubemaps only from `.hdr`/`.exr` (lat-long 2:1):
  convert a JPG dome (sRGB -> linear, resize to 2:1 - Redshift stretches any image over the sphere) to `.hdr` with OpenCV.
  **Every `.hdr` imports as a TextureCube** - use a 16-bit linear PNG for 1D gradients.
- **Emitters invisible to camera** (RS Object tag, primary-ray visibility off) that still light the scene: in the path tracer
  Render In Main Pass = off removed their light too. Use a `MaterialExpressionPathTracingRayTypeSwitch` (inputs `Main`,
  `Shadow`, `IndirectDiffuse`, `IndirectSpecular`, `IndirectVolume`) on the opacity mask: Main 0, the rest 1; blend Masked.
- Emissive ramps along a sweep: bake the knots (smooth-knot = smoothstep between knots) to a 1024x4 linear PNG, sample it at
  the sweep's V. The V direction after Alembic import may be reversed - test both against the Redshift frame. For 2D
  bakes give the master static switches SwapUV / FlipU / FlipV and render every combination (20 s each at half size):
  correlation 0.92 vs 0.85-0.87 picked the orientation clearly (FlipV, as for 1D).
- **A `TextureSampleParameter2D` with sampler type Linear Color and no default texture** compiles in the editor (the MIs
  supply a texture) but FAILS in the MRQ render process ("Sampler type is Linear Color, should be Color for
  DefaultTexture") - Unreal renders the grey default material there. Set `texture` on the node to a linear texture.
  The render process logs to `Saved/Logs/<Project>_2.log`: grep it for "Failed to compile" after a surprising render.

## 6. Calibrate against a Redshift frame
- Render the same frame linear from both (Redshift EXR; MRQ path tracer with `MoviePipelineColorSetting.disable_tone_curve`
  and EXR), apply one sRGB curve to both, compare region means and chroma (r, g, b / sum) - hue errors show at once
  (the reversed gradient: chroma 0.153/0.239/0.607 vs 0.195/0.144/0.661; fixed 0.193/0.135/0.672).
- Dome rotation: render 0/90/180/270 deg, keep the best log-luminance correlation.
- Light balance: render each light group alone (dome only, emitters only) and least-squares fit their weights to the
  Redshift frame (weight 1/(value + eps) for relative error) - correlation 0.889 -> 0.930.
- Cross-check noise at 100% +2 stops: 48 spp + denoiser blotches dark detail (keyboard keys); 256 spp is clean.
- Emission vs lighting on a material: render emission-only (BaseColor 0, Specular 0) and lit-only (EmissiveWeight 0) -
  the frame is linear in the two (|E + L - both| was 5 % of the mean) - and least-squares fit both weights to the Redshift
  frame (blur 5x5 first: fine geometry never lines up). Translucent Redshift ribbons came out emission x 0.74, lighting
  ~0 (correlation 0.986 -> 0.989, means within 2 %). Same trick per material variant (opacity 0 on the others) shows
  whether one variant is off.
- Emissive translucent layers converge fast: 32 spp was within 1 % of 128.

## 6b. Scenes lit by emissive geometry (moving mesh lights, light cards) - verified on a tunnel scene, Nov 2026
- Redshift mesh emitters (glowing cylinders / tori / cards on cloners, often invisible to camera via the RS Object tag:
  `2999` override with `2000` primary / `2006` reflection visibility absent) are what made its frames noisy and
  flickering. In Unreal replace them with lights the path tracer samples directly: capsule point light per cylinder
  (source_radius = r, source_length = h - 2r, axis = the light's X), N point lights around each torus ring, a pair of
  back-to-back rect lights per card. Keep visible emitter meshes for the look with an emissive behind a
  `PathTracingRayTypeSwitch` (Main = emission, others 0) and cast_shadow off on the mesh, so the light isn't doubled.
  Parent everything to one animated actor when a null moves the emitter cloner.
- **Path tracer light grid drops lights silently**: `r.PathTracing.LightGridMaxCount` (default 128, engine max 256 -
  `RAY_TRACING_LIGHT_COUNT_MAXIMUM`) caps lights per grid cell. 421 lights with a 200 m attenuation radius each made the
  full render 17x darker than one spot alone. Give lights realistic attenuation radii (50 m here), raise the cvar in
  `[SystemSettings]`, and check that group-only renders add up to the full render.
- 378 movable shadow-casting point lights crashed the GUI editor's raster viewport (classic cube shadow maps, D3D12
  "Too many residency sets"): set `r.Shadow.Virtual.Enable=1` before spawning them (the path tracer doesn't care).
- **Nanite fallback is what the path tracer traces** while `r.RayTracing.Nanite.Mode` is 0: a 1.85M-triangle scan had an
  automatic fallback of 8k triangles. For hero meshes set `fallback_target = PERCENT_TRIANGLES`, `fallback_percent_triangles = 1.0`.
- Redshift render-time displacement doesn't survive the export: bake it into a dense mesh in c4dpy (heights sampled with
  numpy from the displacement map at the texture node's scale, e.g. 1 x 3; amplitude = displacement node scale x RS
  Object tag scale), export FBX like the rest, keep normal / roughness maps in a small floor master.
- Redshift spot / area lights ("image" units, Decay 0, cone + falloff angles) did not convert cleanly: neither a wide
  cone nor no-decay fitted better than a physical narrow spot; fit them as groups. A Redshift file can also use a different
  camera exposure than its sibling scene (here 3.7 stops) - fit an "emissive seen by camera" group to get it.
- Redshift (IPC GI) carried emitter light 30+ m down shiny pipes; the path tracer doesn't. Expect such glows to be
  missing and treat them as an art decision, not a calibration error.
- Fit groups in LOG space on coarse blocks (12x12 px): linear least squares was dominated by one hot spot and zeroed
  whole groups.

## 7. Passes (Redshift takes that hide object groups) -> sublevels
- Move each pass's actors into a streaming sublevel: select them, then
  `unreal.EditorLevelUtils.create_new_streaming_level(unreal.LevelStreamingDynamic, "/Game/Maps/L_X_PassA", True)`
  (True = move the selection). Keep cameras, sky, post-process volume in the persistent level.
- Not exposed to Python in 5.8: `World.persistent_level`, `World.get_streaming_levels`,
  `LevelStreamingDynamic.set_should_be_visible`. Use `actor.get_level().get_path_name()` to tell which level an actor
  is in, `unreal.GameplayStatics.get_streaming_level(world, "L_X_PassA")` for the streaming object
  (`initially_loaded` / `initially_visible` editor properties).
- Bindings in the master sequence point at the old actor paths: rebuild the possessables (geometry-cache tracks) after the move.
- Per pass a shot (subsequence of the master + camera cut) with ONE `MovieSceneLevelVisibilityTrack`: a VISIBLE section
  naming its own sublevel and a HIDDEN section naming the other (`set_visibility`, `set_level_names`). MRQ warns that
  blueprint-streamed sublevels are only guaranteed visible in a render when a visibility track controls them.
  Verified: the Light pass rendered identical to before the split, the ribbon pass showed only ribbons.

## Unreal side, reusable
- Five-screen LED rigs, per-screen shots and MRQ presets: `unreal-led-volume-rig`. Path tracer in MRQ: remove
  `MoviePipelineDeferredPassBase`, add `MoviePipelineDeferredPass_PathTracer`; the spatial sample count is the spp.
- Pass script arguments as one dict popped per run (`A = globals().pop("ARGS", {})`): editor Python globals persist
  between remote runs, and a stale `OUT` sent a whole test render to an old folder.

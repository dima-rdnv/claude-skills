---
name: cinema4d-redshift
description: Redshift in Cinema 4D through Python — node materials via the maxon graph API (node/port IDs), an emission-only lit-gold recipe, RS Object tag particle settings, splines as RS curves, RS Camera ids, image sequences on the Texture node, verifiable test renders, rendering a take with Redshift from a script (GUI threaded render, take render settings, out-of-memory code), and verified dead ends. Use when shading or test-rendering with Redshift in C4D. Load with cinema4d-mcp.
---

# Redshift in Cinema 4D (verified, C4D 2026.3–2026.4)

## Node materials through the maxon API
- Every material is type 5703; the Redshift graph lives in a node space:
  `RS = maxon.Id("com.redshift3d.redshift4c4d.class.nodespace")`,
  `graph = mat.GetNodeMaterialReference().GetGraph(RS)` (`HasSpace(RS)` to test).
  The MCP tool `inspect_redshift_materials` skips these as "not_redshift_like" — use the API.
- New material: `mat = c4d.BaseMaterial(c4d.Mmaterial); doc.InsertMaterial(mat);
  graph = mat.GetNodeMaterialReference().CreateDefaultGraph(RS)` → RS Standard + Output.
- List nodes: `graph.GetViewRoot().GetChildren(lst, maxon.NODE_KIND.NODE)`; node type:
  `n.GetValue("net.maxon.node.attribute.assetid")`. List ports:
  `n.GetInputs().GetChildren(lst, maxon.NODE_KIND.PORT_MASK)`.
- Edit inside `with graph.BeginTransaction() as t: ... t.Commit()`:
  `graph.AddChild(maxon.Id(), maxon.Id(node_type))`, `n.GetInputs().FindChild(port_id)`,
  `port.SetPortValue(maxon.String(...) / maxon.Float(...) / maxon.ColorA(...))`, `out.Connect(inport)`,
  `n.Remove()`. Assign: `tag = obj.MakeTag(c4d.Ttexture); tag[c4d.TEXTURETAG_MATERIAL] = mat`.
- Find node types: `maxon.AssetInterface.GetUserPrefsRepository().FindAssets(
  maxon.AssetTypes.NodeTemplate(), maxon.Id(), maxon.Id(), maxon.ASSET_FIND_MODE.LATEST)` and filter
  ids for "redshift" (161 templates). Build a node in a throwaway doc's material to list its ports.
- Value types that worked (2026.1): colour ports `maxon.Color(r, g, b)` (linear), vector ports
  `maxon.Vector(x, y, z)`, scalars `maxon.Float(v)`.
- Read wiring: `conns = []; port.GetConnections(maxon.PORT_DIR.INPUT, conns)` → `conns[i][0]` is
  the source port (`.GetAncestor(maxon.NODE_KIND.NODE)` for its node). `maxon.PORT_CONNECTION_MODE`
  doesn't exist. Identify nodes by wiring, not by list order, before editing duplicates.

## IDs (prefix `com.redshift3d.redshift4c4d.nodes.core.`)
- `standardmaterial`: `.base_color`, `.base_color_weight`, `.emission_color`, `.emission_weight`,
  `.refl_weight`, `.refl_roughness`, `.overallaffectsemission`. Output: `com.redshift3d.redshift4c4d.node.output`.
- `vertexattributelookup`: `.attribute`, `.defaultcolor` (magenta), `.defaultscalar`, `.outcolor`, `.outscalar`.
- `particleattributelookup`: `.attribute`, `.outcolor`, `.outscalar`.
- `rsuserdatacolor`: `.attribute`, `.default`, `.out` (also `rsuserdatascalar/vector/integer/string`).
- `state`: outputs `.normal`, `.normal_nobump`, `.normal_geom`, `.raydirection`, `.rayposition`,
  `.uvwcoord`, `.tangent`, `.bitangent` (world space).
- `rsmathdotvector`: `.input1`, `.input2`, `.out` · `rsmathrange`: `.input`, `.old_min`, `.old_max`,
  `.new_min`, `.new_max`, `.clamp`, `.out` · `rsmathsaturate`: `.input`, `.out` · `rsmathpow`:
  `.base`, `.exponent`, `.out` · `rsmathmul`: `.input1`, `.input2`, `.out`.
- `rscolormix`: `.input1`, `.input2`, `.mixamount`, `.outcolor` · `rscolorconstant`: `.color`,
  `.outcolor` · `fresnel`: `.facing_color`, `.perp_color`, `.ior`, `.outcolor` · `ambientocclusion`:
  `.bright`, `.dark`, `.spread`, `.maxdistance`, `.out` · `rsramp`: `.input`, `.ramp` (gradient —
  setting it from Python untested), `.outcolor` · `rscolorlayer`: `.base_color`, `.layerN_color/_mask/_blend_mode`.
- Others seen: `texturesampler`, `triplanar`, `bumpmap`, `bumpblender`, `roundcorners`,
  `rsscalarramp`, `incandescent`, `curvature`, `rsvectormaker`, `c4dhairattribute`, `volume*attribute`.

## Recipe: emission-only "lit" gold without lights (verified look)
For stylised elements that must read without a light rig: RS Standard with base colour black,
refl_weight 0, emission weight ≈1.2, emission colour =
`colormix(dark, gold, range(dot(state.normal, L), -1..1 → 0..1))` → second `colormix(that,
highlight, pow(saturate(dot(state.normal, H)), 18))`, with L = normalize(-0.55, 0.65, -0.55) (upper
left, towards a camera looking down +Z) and H = normalize(L + (0, 0, -1)). Gold that read well:
dark (0.30, 0.13, 0.02), gold (1.0, 0.72, 0.28), highlight (1.0, 0.93, 0.70) (linear).
Particle dust: emission-only (1.0, 0.80, 0.46) × 1.1 on a dark green comp reads as pale gold.

## Recipes: atmosphere rim and a screen-space gradient sky (verified look, C4D 2026.4)
- **Rim** on a shell sphere just above the globe: `dot(state.normal, state.raydirection)` →
  `rsmathrange` (−1…0 → 0…1) → `rsmathsaturate` → `rsmathpow` (exp 5–7) → `rscolormix(black, rim)`
  → `emission_color`; the same mask → `rscolormix(black, white)` → `opacity_color`. Base/refl weight 0.
- **Gradient sky**: a Plane (`PRIM_AXIS` 5 = −Z, UVW projection) parented to the camera at local z,
  width = z · aperture / focal (+1 %). `dot(state.uvwcoord, (0,1,0))` = v, and **v = 1 at the top
  of frame**. One segment `range(v) → saturate → rsmathmul(t, t) → colormix(top, horizon)` is smooth;
  two linear segments joined by colormix showed a visible band at the join.
- `rsmathrange` accepts old_min > old_max (inverted mapping) — verified.
- Emission hex values rendered ~2–2.5 stops darker through the scene's view transform: measure the
  render and raise emission weight (3–6 here) rather than trusting the hex.
- Graph edits inside `BeginTransaction` are not in exec_python's undo (`add_undo_change` covers
  objects/tags only) — build on new or cloned materials and swap texture-tag links (undoable).
- (cause unknown) an `rsmathpow` inserted between a saturate and a colormix `mixamount` rendered 0;
  a `rsmathmul(t, t)` in the same spot worked.
- Many RS point lights inside cloned rigs (66 here) made a 960×540 preview crawl (~15 % after 80 s);
  with them off it took 8 s.
- **Splines as Redshift curves** (verified 2026.4, many hundreds of lines in ~6 s at 1920 final):
  RS Object tag on the spline: `[9000]` Mode (0 Off, 1 Hair Strands, 32 Boxes, 33 Cylinders,
  34 Capsules, 35 Cones, 36 Strips), `[9001]` Thickness (cm), `[9002]` Scale = `c4d.SplineData`
  thickness along each curve (a new SplineData already holds 2 knots: delete them before
  `InsertKnot(0, 1)`, `InsertKnot(1, 0)` for a taper). Multi-segment splines work (one curve per
  segment); tags put on splines built inside a Python Generator's cache are honoured. Dots = 2-point
  segments in Capsules mode. Camera-only look: `[2999]` Override on, 2001–2013 off.
- Sub-pixel curves look like grain in `render_preview_image(quality="preview")` (denoised); judge
  them with `quality="final"`.
- **RS Camera object** (type 1057516, not `IsInstanceOf(c4d.Ocamera)`): `[500]` Focal Length (mm),
  `[7002]` Sensor Size (mm, Vector w/h), `[7005]` Fit (0 Fill-Crop, 1 Horizontal, 2 Vertical,
  3 Overscan), `[7022]` Zoom (focal × zoom), `[7012]` Shift. Looks down +Z like a C4D camera; a
  pinhole projection with focal and the horizontal aperture (sensor.x for Fit Horizontal) matched
  the render to 1 px. Replace a standard camera: copy Mg, focal, aperture → `[500]`, `[7002]`,
  then set it on the BaseDraw and the Main take.
- **Hair-thin lines (~1 px)**: 1 px at distance z is z · aperture / (focal · width_px). Sweeps with a
  0.018–0.02 cm square profile at 250–490 cm (100 mm, 36 mm gate, 1920 wide) rendered as crisp
  ~1 px lines; emission-only weight 6–8 keeps them bright after anti-aliasing (preview quality).
- Texture-driven line opacity (`texturesampler` → `rsscalarramp`): lowering the ramp's `old_max`
  (1 → 0.35–0.45) keeps only the dark line cores of a black-on-white grid texture → thinner lines.
- Check texture paths before judging a material: a missing `relative:///tex/...` texture made an
  opacity-masked grid render as a solid sphere. `c4d.GenerateTexturePath(doc_path, file, "")`
  returns None when unresolved.
- (unverified fix) RS Object tag 1999 = 1 + 2002 "Casts Shadows" = 0 did not stop a small emissive
  sphere's shadow in a preview; shrinking the object did.

## RS Object tag (plugin 1036222)
- Particles: override 2999, mode 3000 (0 Disabled, 1 Point, 2 Sphere, 3 Quad instances, 4 Custom
  objects, **5 Optimized Spheres**), 3001 Scale Multiplier (× the particle radius channel).
- Motion blur: 6999 override, 6000 mode (0 Global, 1 Off, 2 Transformation, 3 + Deformation).
- Verified: an Alembic Particle Group renders as Optimized Spheres at its `width` radius.
- Verified: native simulated Particle Groups (Basic Emitter) render the same way (radius × 3001);
  material = texture tag on the group. Mode 0 hides a group that only feeds a Cloner.

## Image sequences on the Texture node (verified C4D 2026.4, by rendering a barcode sequence)
- `texturesampler.tex0` sub-ports (Int64 unless noted): `path` (Url), `animation` = Mode
  (0 Off, 1 Once, 2 Loop, 3 Ping-Pong), `timing` (0 Frame, 1 Time, 2 Range), `framestart`, `frameend`,
  `framerate`, `startoffset`, `loops`, `rangestart`/`rangeend` (TimeValue).
- Measured with Mode Once: **Frame** → scene frame f shows `framestart + f` (fps ignored).
  **Time** → scene time t shows `framestart + startoffset + floor(framerate · t)`; before the first
  frame the texture is blank, after the last it holds. So with `framestart = N0`,
  `startoffset = −N0`, `framerate = 30` a sequence numbered in 30 fps edit frames plays at its edit
  time in a scene of any fps whose time equals edit time (same rule AE uses to nest 30 in 50 fps).
  Checked at 50 fps and at 30 fps: at exact frame times (30 fps scene, 30 fps sequence) there is no
  floating-point off-by-one — frames 509…855 all mapped to themselves, in Time and in Frame timing.
- `rangestart`/`rangeend` can't be set from Python: `SetPortValue` rejects `maxon.TimeValue`
  (also wrapped in `maxon.Data`) — use Time + start offset instead of Range.
- A relative path into a sub-folder works: `maxon.Url("relative:///Sub/seq_00509.png")` resolves
  like `c4d.GenerateTexturePath(doc_path, "Sub/seq_00509.png", "")` (doc folder or its `tex`).
- How to test any texture mapping: generate a sequence whose frames encode their own number as
  black/white stripes plus an always-white reference stripe (an all-black frame is
  indistinguishable from "no texture"), map it emission-only on a camera-filling plane with UVW
  projection (a Python texture tag defaults to Spherical), set the camera on the Main take,
  RenderDocument small frames and decode the stripes.

## Test renders you can verify
```python
rd = doc.GetActiveRenderData().GetClone()
rd[c4d.RDATA_XRES], rd[c4d.RDATA_YRES] = 480, 270
rd[c4d.RDATA_FRAMESEQUENCE] = c4d.RDATA_FRAMESEQUENCE_CURRENTFRAME; rd[c4d.RDATA_SAVEIMAGE] = False
bmp = c4d.bitmaps.MultipassBitmap(480, 270, c4d.COLORMODE_RGB)
res = c4d.documents.RenderDocument(doc, rd.GetDataInstance(), bmp, c4d.RENDERFLAGS_EXTERNAL)  # 0 = ok
```
- Returns well under the 60 s limit at this size. Set `doc.SetTime(...)` first.
- **Never RenderDocument a `TakeToDocument()` copy with Redshift** (verified 2026.4): at 961×600 it
  held C4D's main thread for 8+ minutes until the user had to restart C4D — unsaved work was lost.
  The same scene's live document rendered 400×250 in < 60 s. Render a take by making it current on
  the live doc (restore it after), keep frames small, or use the adapter's `start_render` (own thread).
  After a long synchronous call the adapter times out on everything (`ping` too) — don't queue more.
- A geometry/texture placement check needs no render: export the deformed mesh + UVs, project it,
  and warp the texture frame per quad onto the plate (OpenCV `getPerspectiveTransform` per quad,
  combine with `max`, skip quads within a few cm of the camera — they project huge and paint black).
- Verify numerically: sample `bmp.GetPixel(x, y)` in the region of interest and bucket colours
  (a magenta default on a lookup node = "attribute not found").
- To look at it (any OS, no files): save to `c4d.storage.MemoryFileStruct` as JPEG, print base64,
  decode in the sandbox — full recipe, crops and contact sheets in `cinema4d-render-preview`.
  (Old macOS route: `bmp.Save('/tmp/x.png', c4d.FILTER_PNG)` → `sips` → `base64`.)
- Simulations: render a clone stepped from frame 0 with `RENDERFLAGS_NODOCUMENTCLONE` so the sim
  state is kept (verified with native particles).
- A scene's render output path may be a Windows path (`D:/...`) — on macOS that creates a folder named
  `D:` next to the scene; keep SAVEIMAGE off for tests.

## Rendering a take with Redshift from a script (verified C4D 2026.4, macOS)
- `RenderDocument` with Redshift on a **headless c4dpy** document, and in the GUI on an in-memory
  `TakeToDocument` copy, returned 0 but wrote a uniform blank image (1.6 KB PNG). The recipe above
  (active document in the GUI) is the one that renders.
- Working route for a take: open the file in the GUI, `td.SetCurrentTake(take)`, clone the take's
  render setting (`GetClone(c4d.COPYFLAGS_NO_HIERARCHY)`), set `RDATA_RENDERENGINE = 1036219`, insert
  `BaseVideoPost(1036219)` if missing, `doc.InsertRenderDataLast(rd)` and **`take.SetRenderData(td, rd)`**
  — a take's own render setting wins over `doc.SetActiveRenderData(rd)` (the first try rendered the
  take's Viewport setting). Then the Maxon MCP `start_render` (threaded; C4D stays usable), poll
  `get_render_status`, close the document with `force` so nothing is saved.
- Result code **1 = out of memory** after ~10 s while After Effects held 57 GB on a 64 GB
  unified-memory Mac; after `app.purge(PurgeTarget.ALL_CACHES)` in AE (−50 GB) it rendered. Check
  `top -o mem` before blaming the scene. (With Rendering Mode `[21151] = 1` progressive it also failed
  with 1 — not retried after the purge; bucket mode `0` rendered.)
- Redshift videopost ids seen: 21151 Rendering Mode, 1003 progressive passes, 1101/1102 samples
  min/max, 5801 global displacement, 5002 refraction trace depth, 9006 refraction (another depth).
  Preview settings for a refractive blob scene with 500k sphere clones: displacement off, refraction
  depth 2, 640×360 → ~1.5 min per frame (a 960×540 frame with every clone emitting white took ~10 min).
- MoGraph colour in a material: Color User Data node (`rsuserdatacolor`) with attribute `RSMGColor`
  reads the clone colour set by effectors (seen in a production clone material feeding a ramp).

## Verified dead end: per-particle colour on Alembic Particle Groups
- Positions and radius render, but colour does not reach Redshift: Vertex Attribute Lookup `__cd__`
  → default (magenta); Particle Attribute Lookup `color` / `__cd__` → black; Color User Data
  `__cd__` → black. Cause: the colour channel is empty in real documents (see `cinema4d-alembic`).
  Ruled out: render engine, OCIO, fps/time range, doc path, scene objects, materials.
- Routes instead: Redshift Proxy from Houdini (needs Redshift for Houdini; Cd via RS Point
  Attribute), polygon mesh with point Cd (spheres copied to points or a VDB mesh → Vertex Color tag →
  Vertex Attribute Lookup; heavy files), a procedural colour in the RS shader (age/position driven;
  whether Particle Attribute Lookup reads `age` is untested), or clones on a mesh whose vertex maps
  drive MoGraph colour (`cinema4d-alembic`).

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

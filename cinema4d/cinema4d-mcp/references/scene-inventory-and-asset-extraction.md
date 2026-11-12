# Scene inventory, camera visibility and clean asset extraction (headless c4dpy, verified C4D 2027.0, Windows, Nov 2026)

Use these to answer "what is in this scene / which objects are a given product / what do the cameras
see / give me this model as a clean file with its textures" without touching the open GUI scene.
Scripts in `../scripts/` (run with `c4dpy g_licenseModel=LICENSEMODEL::MAXONAPP <abs script> args < /dev/null`).

## Inventory: `scripts/c4d_scene_dump.py <scene.c4d> <out.json>`
- Writes every object (path, type, polys, material tags, layer, editor/render visibility, global
  position, Instance link target, RS Proxy file), materials, all assets (`GetAllAssetsNew`, with
  `exists`), layers, cameras and the take tree with each take's camera. A 326 MB / 1150-object
  scene dumped in ~1 min. Summarise the JSON in the sandbox (polys per subtree, instance counts).
- Finding "which objects are brand X": object names are often useless (CAD exports name parts
  `Next assembly relationship`, `Body1`, numbers). Look at the **textures** the materials use — photo
  textures of downloaded models show logos when you zoom (autocontrast a crop); CAD part numbers in
  names identify a vendor's own assemblies.
- `GetAllAssetsNew` `assetname` for Asset Browser textures reads like
  `assetdb:///Textures/Surfaces/Redshift/Metal_Aluminium_001_Roughness.tif` → filename `asset:///file_…~.tif`.

## Sizes: measure in the object's own axes
- A product under an animated turntable null ("Rot") is rotated at frame 0, so a world-space bbox
  is inflated (a 22 × 37 cm card measured 36 × 42). Measure points as
  `(~root.GetMg()) * o.GetMg() * p` over all polygon descendants → matches the source CAD to < 0.1 cm.
- Instance objects (`Oinstance`, `INSTANCEOBJECT_LINK`): geometry = the linked object's local bbox
  placed at the instance's own matrix.
- Comparing a scene object with a source OBJ: point/poly counts differ by a few dozen after import
  (welds), so an identical mesh shows ~0.005 % difference; a few % more polys inside the same bbox
  means detail was added in the scene. Rack ears removed showed up as width 44.0 vs 48.3 cm.

## Camera visibility: `scripts/c4d_camera_visibility.py <scene> <out.json> <cams> <objects> [step]`
- Steps the timeline (`SetTime` + `ExecutePasses(None, True, True, False, …)`), projects a 5×5×5
  grid of points of each object's local bbox into each camera and reports frames seen, max screen
  coverage and closest distance. Pinhole: `u = 0.5 + (f·x/z)/A − offX`, `v = 0.5 − (f·y/z)/(A·yres/xres) − offY`
  (C4D film offset X + shifts the view right, Y + shifts it down — see `unreal-led-volume-rig`);
  resolution per camera from the take that uses it (`take.GetRenderData(td)`).
- Results were plausible for a 5-camera LED-volume rig (side walls dominated by the side cabinets,
  hidden objects never seen) but were **not checked pixel-for-pixel against a render**.

## Clean asset file: `scripts/c4d_extract_asset.py <src.c4d> <out_dir> <name.c4d> <obj/path> [...]`
- Loads the source read-only, keeps only the given objects (moved to the root with the pose they
  had relative to their old parent, animation tracks removed), drops every other object and every
  material no kept object uses, removes all video posts, centres the result on the floor at the
  origin and runs `SaveProject(ASSETS | SCENEFILE | USEDOCUMENTNAMEASFILENAME | DONTFAILONMISSINGASSETS)`.
  Then reopen the saved file and list its textures to verify (the script does).
- **`SaveProject` returned False and wrote only some texture copies (no scene file)** when one asset
  was missing — here a LUT (`.cube`) referenced by the Redshift post-effects video post, pointing to
  the project's old drive path. With the video posts removed and `DONTFAILONMISSINGASSETS` it saved.
- Set only the document **name** before `SaveProject`, not its path: a file whose textures are stored
  relative (name only, found via its own `tex/`) reported them missing after `SetDocumentPath(out_dir)`
  (the new folder was still empty). Without it they were copied and relinked (verified by re-extracting
  an already-extracted asset).
- Asset Browser textures (`asset:///…`) are **not copied** into `tex/`; they stay library
  references and resolved (`exists=True`) after reopening. Plain file textures are copied to `tex/`
  and relinked.
- **Never compare C4D objects with `is`**: every `GetFirstObject()`/`GetNext()` returns a new Python
  wrapper, so `op is kept` was False for the same object and the script deleted what it meant to keep
  ("ReferenceError: the object 'c4d.BaseObject' is not alive" later). Use `==`.
- A 1 GB scene returned None from `LoadDocument` in c4dpy 2027 (300–500 MB files loaded); cause not
  investigated — fall back to a smaller scene holding the same model.

## Swapping hardware in a heavy scene, headless (verified 2027.0, Nov 2026, a 330 MB scene)
- **Build a library first.** Bake each replacement device to one polygon mesh: run
  CurrentStateToObject on the device root, Connect each effective-material group, then merge those
  meshes yourself, writing one polygon selection and one texture tag per material and copying the
  UVs. Three traps:
  - In c4dpy 2027, Connect (`MCOMMAND_JOIN`) on a whole hierarchy wrote its texture tags with empty
    restrictions, so every part rendered with the last material.
  - Walk only the CSTO result's own subtree (`[root] + walk(root.GetDown())`). A helper that also
    follows `GetNext()` from the root pulled in other top-level objects.
  - Build helper geometry inside the target document. Tags that point at another document's
    materials came out empty.
- **Place copies as render instances** (mode 1) of the baked meshes, under one null per cabinet that
  carries the scene's uniform scale. Read the object scale of what you replace first: in this scene the
  units sat at 12.5× and the cabinets were modelled at about 10×. Match the scale per role, uniformly.
- **Keep what the cameras see.** Size the replacement to the original's volume and on-camera detail
  size, not to a textbook real-world size:
  - A real 42U, 60 cm rack at the cabinets' ~10× made every device about 20% smaller on camera.
    Derive the scale from the original modules' width (here ~12.2× a 19-inch device), then build the
    frame to fill the same volume (here 35U, 52 × 167 × 53 cm real).
  - Copy the original's open or closed structure too. Side, back and roof panels the original didn't
    have blocked the scene's sky light, and the racks rendered black inside.
- **Keep the composition.** Map the original's modules (their y-ranges in the cabinet's own space) to
  whole rack units and place one device per module. Derive the map from the geometry rather than by
  hand. Leave the gaps open: the openings were part of the shot. Reserve slots for anything else (hero units, cabled switches) only when the object's *centre*
  lies inside that rack. A corner-overlap test also reserved slots in the touching racks next to it.
- **Hide the originals in place** (`MODE_OFF`) instead of deleting them. Take overrides on a parent
  group's visibility still apply to new objects placed under it. Save to a new file next to the
  original so relative textures still resolve. Then compare fps, frame range, take count,
  render-setting count and cameras against the original.
- **Re-target cable rigs (MoGraph).** Use a Cloner in Object mode on a mesh with one small quad per
  port: Distribution Polygon Center, Align on.
  - The clone's Z points into the port for only one of the two windings.
  - Its in-plane rotation follows the vertex order. Shift the start vertex by 2 to turn a clone
    180°, e.g. for the upside-down lower port of a stacked cage.
  - Read the MoData matrices and compare them with the wanted frames. Try both windings × 4 start
    vertices once, then reuse the result.
  - With Fix Clone on, the clone matrix replaces the child's own matrix. Model the plug in the
    child's local axes and keep the null the wire generator starts from.
- **Quick frames of a heavy scene:** use the scene's own takes with `Commandline -oresolution W H`
  (10–30 s per frame at 721×450). Brighten dark frames only for inspection.
- **Launch failures:** Git Bash launches of Commandline and c4dpy started to fail instantly (exit 139,
  0 s) while a trivial c4dpy script still ran. The same calls through PowerShell
  `Start-Process -Wait` worked. In PowerShell, avoid single-letter function names: `R` is an alias of
  Invoke-History.
- **EXR from child takes:** a child take inherits its parent's render setting, output format
  included, and here that was EXR. Read it with `OpenEXR`:
  `OpenEXR.File(p).channels()['RGBA'].pixels`.

## Other headless notes (c4dpy 2027.0)
- Standard renderer `RenderDocument` works headless: a 330k-poly FBX merged into a new document with
  3 distant lights + environment ambient rendered 1600×1200 with alpha in ~2 s (`MultipassBitmap`,
  `AddChannel(True, True)`, `Save(..., SAVEBIT_ALPHA)`). Good for quick contact sheets; final looks
  go through Redshift (Commandline renders, see SKILL.md).
- A Claude session started before the MCP server was enabled has **no** cinema4d tools (ToolSearch
  finds none); `scripts/c4d_mcp_call.py ping` through Maxon's relay still reaches the running C4D.

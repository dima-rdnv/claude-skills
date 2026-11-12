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

## Other headless notes (c4dpy 2027.0)
- Standard renderer `RenderDocument` works headless: a 330k-poly FBX merged into a new document with
  3 distant lights + environment ambient rendered 1600×1200 with alpha in ~2 s (`MultipassBitmap`,
  `AddChannel(True, True)`, `Save(..., SAVEBIT_ALPHA)`). Good for quick contact sheets; final looks
  go through Redshift (Commandline renders, see SKILL.md).
- A Claude session started before the MCP server was enabled has **no** cinema4d tools (ToolSearch
  finds none); `scripts/c4d_mcp_call.py ping` through Maxon's relay still reaches the running C4D.

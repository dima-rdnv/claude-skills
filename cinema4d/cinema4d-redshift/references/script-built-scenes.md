# Script-built Redshift scenes: render settings that render, bevels in the material (verified C4D 2027.0, Windows, Nov 2026)

## Commandline waits forever on a script-built scene: it was the cloned Redshift videopost
- Symptom: `Commandline.exe -render` sits at "Loading Project", no frame, no error. The Redshift log
  (`C:\ProgramData\Redshift\Log\Log.Latest.N\log.html`) ends with `Context: Locked:Render` and
  `Context: Busy:Render Waiting until idle`.
- The scene had one parent render setting with a `c4d.documents.BaseVideoPost(1036219)` inserted and
  configured, and child render settings made with `rd.GetClone()` (so each child carried a clone of
  that videopost). Built in c4dpy or inside the GUI through `exec_python`: both files hung.
- Ruled out by stripped variants (each still hung): lights, materials, bokeh, progressive vs bucket,
  denoise, the take (Main also hung), an empty save path, multi-pass flag, `BaseDocument()` vs a real
  new project (`CallCommand(12094)`).
- What fixed it: remove the videoposts from **every** render setting and give each its own new one.
  A fresh `BaseVideoPost(1036219)` per setting and Redshift's helper both rendered (2–5 s):
```python
import redshift
for r in (rd_parent, rd_child_a, rd_child_b):          # after the clones exist
    vp = redshift.FindAddVideoPost(r, redshift.VPrsrenderer)
    vp[60000] = 1                                      # Advanced mode, then the classic ids
```
  So: create child render settings with `GetClone(c4d.COPYFLAGS_NO_HIERARCHY)` **before** any Redshift
  videopost exists, then add one videopost per setting. Why the cloned one hangs is not known.
- `rd.GetClone()` also copies child render settings: a second clone taken after the first child was
  inserted carried that child along (a nested duplicate). Use `COPYFLAGS_NO_HIERARCHY`.
- Bisecting such a hang: copy a scene that is known to render, then swap one part at a time between
  the two with c4dpy (its render data cloned into the failing scene, or the failing scene's objects
  merged into it). Run every Commandline test with `timeout 90`; a good scene starts within ~20 s.

## Bevels as shading: Round Corners (the user's preference over bevel geometry)
- The user asked for bevels "as a material, not actual geometry". Node
  `com.redshift3d.redshift4c4d.nodes.core.roundcorners`: inputs `.radius` (scene units, default
  0.5), `.numsamples` (6), `.sameobjectonly`; output `.out` → the Standard Material's `.bump_input`.
- **Round Corners only renders in bucket mode.** With Rendering Mode `[21151] = 1` (progressive) and in
  the progressive IPR it is silently ignored: a radius of 30 cm on a 60 cm cube showed nothing, on a
  primitive and on script-built meshes alike. The same file with `[21151] = 0` showed the bevels at
  once. Hardware ray tracing on or off made no difference. So a scene that relies on it needs bucket
  render settings, and the user has to switch the IPR to bucket to see it.
- Polygons built in Python: C4D's face normal is `(a - c) × (b - d)`. A sweep helper that maps its
  own (along, across, up) axes to X/Z/Y in two orientations turns half the objects inside out. They
  shade normally in Redshift, so check the sign on a top face per object and swap `b`/`d` where it
  points down.
- Keep the mesh edges hard (90°) and give round shapes (pill ends, cylinders) a Phong tag with a
  ~50° limit: `op.SetPhong(True, True, math.radians(50))`.
- One radius per material, so group parts of similar size under one material (radius about a
  quarter of the smallest width). At a quarter of the width the effect is subtle in wide shots.
- Standard Material port for metals: `.metalness`.

## Many small parts from Python (tens of thousands)
- Collect points and quads in Python lists and bake one `PolygonObject` per group
  (`SetAllPoints`, `SetPolygon`): ~650 000 quads built and saved inside one `exec_python` call
  (a 40 MB file). Share points along a swept shape so the Phong tag can smooth it.
- A new Texture tag made in Python reads as Spherical projection: harmless for untextured
  materials, set `TEXTURETAG_PROJECTION` to UVW (6) when UVs matter.

## Smooth shading of script-built and CAD parts (verified 2027.0, a facing-ratio "X-ray" material)
- `c4d.BaseObject(c4d.Ocylinder / Osphere / Ocone / Otube / Olathe)` from Python gets **no Phong tag** (the menu adds one): it
  renders flat-shaded, and a Fresnel / facing-ratio material shows every polygon as a band. `MakeTag(c4d.Tphong)` with an angle
  limit (60°) fixes it.
- CAD-tessellated revolved parts (long sliver triangles) still streak under a Fresnel material whatever the normals (imported
  normal tags kept or removed). Rebuild them as a Lathe of their own profile: for a part revolved around its local Y, take the max
  radius per point ring (`round(p.y, 3)` → `max(hypot(p.x, p.z))`), close the profile on the axis, Lathe 128 segments + Phong;
  relink the instances that used the CAD mesh.
- A lathed solid with an internal cavity from ONE closed profile works (outer contour down, inner contour back up). The legacy
  Boole (`c4d.Oboole`) returned no geometry when that profile touches the axis twice (two poles with an axis segment between):
  drill holes as uncapped cylinders (`PRIM_CYLINDER_CAPS = False`) instead.

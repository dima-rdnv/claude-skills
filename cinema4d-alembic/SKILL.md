---
name: cinema4d-alembic
description: Alembic in Cinema 4D through Python — importer options, frame mapping, particle channels, mesh point attributes as animated vertex maps / vertex colours driving MoGraph (Variable Tag fields), popup traps, coloured sim previews in the Viewport Renderer. Use when importing or checking Alembic geometry or particles in C4D. Load with cinema4d-mcp.
---

# Alembic in Cinema 4D (verified, C4D 2026.3–2026.4)

## Merging from Python
```python
d = {}
plug = c4d.plugins.FindPlugin(c4d.FORMAT_ABCIMPORT, c4d.PLUGINTYPE_SCENELOADER)
plug.Message(c4d.MSG_RETRIEVEPRIVATEDATA, d); imp = d["imexporter"]
keep = {k: imp[k] for k in (1009, 1021, 1024)}
imp[1009] = 1031; imp[1024] = 0; imp[1021] = 1          # Particle Group, colour only (see below)
try:    c4d.documents.MergeDocument(doc, path, c4d.SCENEFILTER_OBJECTS, None)
finally:
    for k, v in keep.items(): imp[k] = v                 # restore the user's importer prefs
```
- Importer ids: **1009 Points** (1018 None / 1019 As Particle Geometry = Thinking Particles /
  1020 As Polygon Object / **1031 As Particle Group**), 1024 Other Attributes, 1021 Color Maps,
  1010 Scale (`UnitScaleData.GetUnitScale()`), 1014 Original frame rate, 1007 SubD, 1008 Curves.
- Merged objects land at the document root: diff the top-level list before/after (GUIDs) to find
  them, then move them into a group with undo. `MergeDocument` into a non-active open document works.

## Frame mapping
- Houdini writes Alembic time = frame/fps. An Alembic **Generator** (meshes) shows Houdini frame N at
  C4D frame N when the file starts at time 0, so two such files from one exporter line up.
- **A Particle Group maps the FIRST sample to frame 0.** A file exported from Houdini frame 571
  played from C4D frame 0. Fix: **write the Alembic from frame 0** (empty samples cost almost nothing).
  Setting the Offset (param 50006) instead also maps correctly, but changing Offset after import left
  duplicated attribute tags (`____color____` next to `__color__`, c4dpy 2027) — the same mechanism as
  the GUI popup loop below. Verified Nov 2026: written from 0, sample N = 60 fps document frame N,
  counts matched Houdini at 6 checked frames.
- **An EMPTY sample keeps the previous particles** in a Particle Group (11 stray full-size droplets
  where the file had 0 points; 22 before the first non-empty sample). Fix in Houdini: when a frame has
  no points add one dummy point far away with `width` 0 (invisible in Redshift).
- Outside its range an Alembic holds the first/last sample, and frames exported EMPTY from Houdini
  did not blank a mesh either (a smoke mesh stayed visible for 100 s after its window) — key
  editor/render visibility (`ID_BASEOBJECT_VISIBILITY_EDITOR/RENDER`, 0 = on, 1 = off;
  `key.SetGeData(curve, v)`).

## Checking an import against the scene
- **Measure animated Alembic geometry from the cache**, not the generator: points of
  `GetDeformCache() or GetCache()` × each cache object's `GetMg()`. `GetMp()/GetRad()` on an Alembic
  Generator is static — it produced a false "timing mismatch".
- Scale check: compare a known part's extent with Houdini — a round factor means a scale is off.
- Containment check for particles: radial distance / height of sampled points against the collider's
  measured extents at a few frames.

## Points: Particle Group vs Thinking Particles
- **"As Particle Geometry" (Thinking Particles) gave 0 alive particles** — don't use.
- **"As Particle Group" works** (`ParticleGroupObject`): `GetPointCount()`, `GetAllPoints()` (+ `GetMg()`),
  `GetParticleColorsR / RadiiR / VelocitiesR / AgesR / UniqueIdsR()` (raw bytes: colours/velocities
  4×float32, radii/ages float32, ids uint32 — decode with `struct`). Params: 50003 Alembic path,
  50004 identifier, 50006 offset, 50025 interpolation, 50001 cache mode; draw: 3004 mode,
  3005 size, 3001/3002 override mode/colour.

## Point attributes → particle channels
- `width` → radius, taken directly, not halved as Alembic's diameter convention suggests (export
  `width = pscale`); `Cd` (typeinfo color) → colour, `color` works too, `Cs` does NOT;
  `v` → velocity, `id` → unique id, `age` → age. **Never export `pscale`**: colour/radius didn't map
  and the popup below appeared.
- With 1024 Other Attributes = 1 the attributes become tags (`__cd__`/`__color__`, `__radius__`, …).
  In a real (loaded) document the colour channel (`GetParticleColorsR`) then stays EMPTY and radii are
  filled; a Python blank document shows colours (not initialised — see `cinema4d-mcp`). Consequence
  for rendering: see `cinema4d-redshift`.
- **"Property name already exists" popup loop:** a Particle Group carrying attribute tags
  (Cd, v, id, width, age) whose Offset was changed after import (re-read) raised the modal popup again
  and again; clicking OK didn't break it and C4D had to be force-quit. Save before experimenting,
  set Offset only on fresh imports or avoid it (write from frame 0), and import only what you need:
  `1024 = 0, 1021 = 1` gave a single `__color__` tag and no popups (colour channel filled — checked in
  a blank document).

## Mesh point attributes → animated vertex maps / colours (verified C4D 2026.4)
- A Houdini polygon mesh with point floats (e.g. `front`, `char`, `emit`) and `Cd`, merged with
  `1021 = 1` (Color Maps) and `1024 = 1` (Other Attributes): the Alembic Generator (1028083) gets one
  **Alembic Tag** (type 1036433) per attribute; its cache polygon object carries a per-point
  **Vertex Color** tag (`Cd`) and **Vertex Map** tags (the floats). Values change every frame.
- Clamp floats to 0..1 in Houdini (vertex maps are weights; values above 1 untested).
- Read them from the cache: `vmap.GetAllHighlevelData()`; vertex colour:
  `c4d.VertexColorTag.GetPoint(tag.GetDataAddressR(), None, None, i)` (`IsPerPointColor()` True).

## Driving clones with those maps (verified on a 312k-point animated mesh, 500k clones)
- **Create effectors (and cloners, fields) from Python with `op.Message(c4d.MSG_MENUPREPARE, doc)`
  right after `c4d.BaseObject(...)`, before setting parameters.** Without it they work in the open
  session but are inert after save + reload (verified: 21 % of clones hidden before saving, 0 % after;
  with MSG_MENUPREPARE 10.6 % after reload). The menu does this; `c4d.BaseObject()` does not.
- **Field layer "Variable Tag"** (`mograph.FieldLayer(440000294)`): `[1000]` = the generator's
  **Alembic Tag** (works directly — no need to reach the cache tag). `[1001]` Mode: 0 Index (by point
  index — useless for clones), **1 Nearest** (exact: correlation 1.000 at the mesh points), 2 Max,
  4 Average, 5 Min within `[1002]` Radius (Average ≈ 0.99). On a Vertex Color tag the layer returns the
  colour (value 1).
- Remapping needs `[1005021] = 1` (Enable Remapping) — for Invert `[1005014] = 1` AND for Color Remap
  `[1005017] = 2` (Gradient) with gradient `[1005016]` (`FlushKnots`, `InsertKnot(col, 1.0, pos, 0.5, i)`).
  Without it the gradient was ignored (clones white).
- **Cloner in Object mode** (`[1015]` = the Alembic Generator, `[1100] = 3` Surface) distributes on
  the animated mesh — also when the generator (or its parent null) is hidden in editor and render.
- **Plain effector (1021337) recipes** — field = Variable Tag layer:
  - colour: Color Mode `[1014] = 5` (Field), position/scale off → `MODATA_COLOR` = vertex colour
    (median error 0), or a vertex map through a Color Remap gradient (e.g. 0..1 → grey 0..0.3 to land in
    the range a material ramp expects). A material reads it as MoGraph colour (Redshift Color User
    Data `RSMGColor`). Colour blending Multiply (`[1015] = 3`) with a field colour changed nothing
    (cause unknown).
  - size: Scale on `[1061] = 1`, uniform `[1017] = 1`, `[1018] = -1`, field **inverted** → clone scale =
    the map value exactly (0 hides the clone). Effector Min/Max (`1001/1002`) did NOT invert the field.
- Order matters: put these effectors FIRST in the cloner's list. After an effector that moves clones
  (a Shader effector lifting them along their normals ~10 cm) the lookup hits other points
  (correlation 0.915); later effectors with a colour mode also mix their colour in.
- Replacing the field list of an effector loaded from a file (made in the UI) did not take effect in
  that session — it kept its old colour; a new effector did. Add new effectors rather than re-wiring
  loaded ones (cause unverified).
- Verify numerically: MoData (`GeGetMoData(cloner)`, `MODATA_MATRIX` scale = `v1.GetLength()`,
  `MODATA_COLOR`) against the field sampled at the same positions:
  `fl.SampleListSimple(cloner, mograph.FieldInput(positions, n), c4d.FIELDSAMPLE_FLAG_VALUE |
  c4d.FIELDSAMPLE_FLAG_COLOR)` → `GetValue(i)`, `GetColor(i)`. Re-check after saving and re-opening.

## Coloured sim previews in the Viewport Renderer (VP)
- The VP renderer draws Particle Group dots **black**, whatever the Cd colour, Override colour
  (3001/3002), display colour or material. For previews export a mesh instead: in Houdini copy a
  small octahedron (`platonic`, 6 points) to every particle and write a points-only (`P`) polygon
  Alembic; in C4D give the Alembic Generator `ID_BASEOBJECT_USECOLOR = 2` and `ID_BASEOBJECT_COLOR` —
  it renders coloured in VP. Smoke: an iso-surface mesh of the density works the same way.
- VP renderer settings live in the videopost 300001061 of the render data; param 1009
  "Geometry Only" = 1 hides grid/HUD/axes but also hides particles. A RenderData created in Python
  may have no such videopost — insert `c4d.documents.BaseVideoPost(300001061)` and set 1009.
- Quick single-frame checks: `RenderDocument` with a clone of the take's render data
  (`RDATA_FRAMESEQUENCE_CURRENTFRAME`, small size, `RENDERFLAGS_EXTERNAL | RENDERFLAGS_NODOCUMENTCLONE`)
  then `bmp.Save(path, c4d.FILTER_PNG)` — same result as the Render Queue for VP.

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

## Alembic meshes into a new scene (verified 8 Nov 2026, C4D 2027)
- `c4d.BaseObject(1028083)` + `[c4d.ALEMBIC_PATH] = path` renders **nothing**: the object identifier inside the file is not set.
  Import through the importer instead (`MergeDocument(doc, path, SCENEFILTER_OBJECTS)`), collect the new top-level objects (by
  GUID) and move them under your own null; scale that null (×100 for Houdini metres). The leaf is an Alembic Generator.
- C4D primitive axes are easy to get backwards (the Hemisphere's dome, a Disc's normal): for a cut-away object build the mesh in
  Houdini (clip + polyfill, cap grouped by normal) and import it; then soot/smoke emitted from the same plane in Houdini lines up.

---
name: cinema4d-alembic
description: Alembic in Cinema 4D through Python — merging .abc files with chosen importer options (points as Particle Group vs Thinking Particles, other attributes, color maps, scale), checking frame mapping and scale against other Alembics, measuring animated Alembic geometry, which point attributes map to native particle channels (width, Cd, v, id, age; pscale clashes), and reading particle data buffers. Use when importing or checking Alembic geometry or particles in C4D. Load with cinema4d-mcp.
---

# Alembic in Cinema 4D (verified, C4D 2026.3)

## Merging from Python
```python
d = {}
plug = c4d.plugins.FindPlugin(c4d.FORMAT_ABCIMPORT, c4d.PLUGINTYPE_SCENELOADER)
plug.Message(c4d.MSG_RETRIEVEPRIVATEDATA, d); imp = d["imexporter"]
keep = {k: imp[k] for k in (1009, 1021, 1024)}
imp[1009] = 1031; imp[1024] = 1; imp[1021] = 1          # Particle Group + attributes
try:    c4d.documents.MergeDocument(doc, path, c4d.SCENEFILTER_OBJECTS, None)
finally:
    for k, v in keep.items(): imp[k] = v                 # restore the user's importer prefs
```
- Importer ids: **1009 Points** (1018 None / 1019 As Particle Geometry = Thinking Particles /
  1020 As Polygon Object / **1031 As Particle Group**), 1024 Other Attributes, 1021 Color Maps,
  1010 Scale (`UnitScaleData.GetUnitScale()`), 1014 Original frame rate, 1007 SubD, 1008 Curves.
- Merged objects land at the document root: diff the top-level list before/after to find them,
  then move them into a group with undo.

## Checking an import against the scene
- **Frame mapping:** Houdini writes Alembic time = frame/fps, so C4D frame N shows Houdini frame N
  (verified: engine part heights identical frame-for-frame). Both Alembics from the same exporter
  therefore line up regardless.
- **Measure animated Alembic geometry from the cache**, not the generator: points of
  `GetDeformCache() or GetCache()` × each cache object's `GetMg()`. `GetMp()/GetRad()` on an Alembic
  Generator is static — it produced a false "timing mismatch".
- Scale check: compare a known part's extent in C4D with Houdini (e.g. a radius) — a round factor
  (×10, ×100) means an export or import scale is off.
- Containment check for particles: radial distance / height of sampled points against the collider's
  measured extents at a few frames.

## Points: Particle Group vs Thinking Particles
- **"As Particle Geometry" (Thinking Particles) gave 0 alive particles** (100 empty slots) even after
  stepping frames and forcing redraws — don't use.
- **"As Particle Group" works** (`ParticleGroupObject`): `GetPointCount()`, `GetAllPoints()` (+ `GetMg()`),
  `GetParticleColorsR / RadiiR / VelocitiesR / AgesR / UniqueIdsR()`. Params: 50003 Alembic path,
  50004 identifier, 50025 interpolation (default 1), 50001 cache mode.
- `GetParticle*R()` return raw bytes: colours/velocities 4×float32, radii/ages float32, ids uint32 —
  decode with `struct` (`bytes(buf)`).

## Point attributes → particle channels (tested one attribute at a time)
- `width` → radius, **taken directly** (not halved as Alembic's diameter convention suggests):
  export `width = pscale`.
- `Cd` (typeinfo color) → colour; `color` works too; `Cs` does NOT.
- `v` → velocity, `id` → unique id, `age` → age.
- **Never export `pscale`**: with it, colour/radius didn't map and C4D raised a modal
  "Property name already exists" popup repeatedly.
- In a real (loaded) document the attributes appear as tags on the Particle Group — Vertex Color
  `__cd__`, Vertex Map `__radius__` / `__age__`, Vertex Color `__velocity__` — and the colour channel
  (`GetParticleColorsR`) stays EMPTY; radii are filled. A Python blank document shows colours (not
  initialised — see `cinema4d-mcp`). Consequence for rendering: see `cinema4d-redshift`.

## Keeping this skill current
After any session that used Houdini/Cinema 4D via MCP, or whenever something new is verified:
1. Add gotchas/recipes ONLY if tested and working in a real scene; mark anything else "(unverified)".
2. Correct entries that proved wrong — don't append contradictions.
3. Put each finding in the skill it belongs to (see the indexes in `houdini-mcp` and `cinema4d-mcp`);
   project-specific facts go to that project's notes (see `project-notes`), never into a skill.
4. Keep each SKILL.md under ~300 lines; split into a new sub-skill or `references/` when it grows.
5. Re-package every changed skill (keep names) and, if the skills live in a git repo, commit and push.
   Tell the user in one line what changed.

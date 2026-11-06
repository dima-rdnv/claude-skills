---
name: houdini-pyro-smoke
description: "Pyro Solver SOP smoke/fire in a closed, moving container (e.g. an engine cylinder): CAD colliders, collider velocity, valve exhaust, dissipation units, caching. Load with houdini-mcp."
---

# Pyro smoke in a moving container (verified, Houdini 21 Indie)

## Network (SOP level)
```
SOURCE points → attribwrangle (density/temperature/burn/v) → volumerasterizeattributes ─┐
COLLIDERS (VDB: collision SDF + v) ───────────────────────────────────────────────────────┴→ pyrosolver
pyrosolver → attribwrangle (16-bit) → rop_geometry (.vdb)      file SOP (cache reader = display node)
```
- `pyrosolver` inputs: 0 = Sources, 1 = Collision Geometry/Volumes. Set `startframe`, `divsize`.
- **Feeding VDB colliders: set `col_type` = 1 ("SDF + Volume Velocity")** (and
  `col_usevolumevelocity` = 1), field names `collisionsdf` = `collision`, `collisionvel` = `v`.
  With the default `col_type` 0 the moving SDF still pushed density around but its velocity was
  ignored: the piston swept through the gas and nothing left through the open valve. With 1 the mean
  gas velocity followed the piston and smoke entered the valve gap.
- Output VDBs: `conv_vdb` = 1. Choose fields with the `export_enable#` multiparm; drop `vel` when
  nothing downstream needs it (it was ~85 % of the cache: 3.4 M active voxels vs 0.6 M for density).
- Half floats on disk: prim wrangle
  `setprimintrinsic(0, "vdb_is_saved_as_half_float", @primnum, 1);`
  (`convertvdb`'s precision menu only offers 32/64).

## Units and rates (measured)
- **`dissipation` acts per 1/24 s**: 0.02 gave an exponential decay of 0.48/s at 60 fps. For
  k per second use `dissipation = k / 24` (0.001 ≈ 0.024/s; 0.005 ≈ 0.12/s).
- Source operator "Add" adds the source value per second. Rasterized points overlap and sum, so a
  point density of 6/s produced voxel peaks ~200 — start around 0.5/s.
- Thin smoke fades faster than the nominal rate (clamp-below 0.005 + mixing into a growing volume):
  a 0.15/s source with dissipation 0.005 went from 0.15 to 0.02 mean density in 8 s. For smoke that
  must last, raise the source density and lower dissipation together.
- The sparse solver only allocates tiles where density/flame exist (+ padding): fields such as `vel`
  are zero/undefined in empty regions (e.g. an exhaust port before smoke reaches it).

## Colliders from CAD
- **Non-watertight CAD shells** (engine head/body): `vdbfrompolygons` with `unsigneddist` = 1
  (band 4 voxels) → volume wrangle `@surface = abs(@surface) - 0.012;` → name `collision`. Every
  surface becomes a thin solid wall regardless of normals. A signed SDF of such a shell had no
  interior (all positive).
- **Moving parts** (piston, valves): `trail` (Compute Velocity, central difference) →
  `vdbfrompolygons` distance `collision` (fill interior) + attribute `point.v` → `v` (vector type
  Displacement/Velocity). Union with the body: `vdbcombine` A = moving, `agroup @name=collision`,
  B = body, operation `sdfunion` (a "not a valid level set" warning about the unsigned body is harmless).
- **Close every opening.** Smoke leaked up an injector bore until the injector geometry was added
  to the colliders. Probe density above the head/around fittings before a long run.
- Read vector VDBs in Python with `prim.samplev(pos)` (`sample()` returns 0.0 for vectors).

## Closed chamber that expands, then exhausts
- An incompressible solver cannot satisfy a receding piston in a closed volume (net outflow with no
  outlet). **Gate the collider velocity**: object spare parm keyed 0 while the valves are closed and
  1 once the exhaust valve opens, applied with a volume wrangle `v@v *= ch("../gate");`. The SDF still
  moves; uncovered cells fill with zero-density fluid. Keep the source emitting while the chamber
  grows so it stays filled.
- **Resolution has to open the valve curtain**: a ~0.05-unit gap with 0.012 wall shells passed no
  flow at 0.02 voxels; at 0.01 the gas went through.
- Check numerically after a short test range (start the test sim just before the event, emit
  briefly at its start): mean `vel.y` across the chamber vs the piston speed, and density probes along
  the port (gap → throat → port end).

## Sources that follow a moving volume
- Detail wrangle that adds N random points inside the current chamber every frame (cylinder radius,
  top = head face, bottom = `bbox("../PISTON", D_YMAX)` + gap as a spare parm), then a point wrangle:
  density from `onoise` clumps × an `emit` channel on the object, swirl `v` about the bore axis
  (source operator Pull keeps it at the set speed; Add accelerates every frame), `pscale` ~2× voxel.
- Flames / glow: rasterize `temperature` and `burn` too; pyrosolver source 2 (temperature, Pull) and
  source 3 (`burn` → `flame`, Maximum); `flames_lifespan` sets how long flame persists.

## Running it
- Never display `pyrosolver` in the GUI (a frame jump makes it re-simulate from `startframe`; see
  `houdini-mcp`). Display the cache reader.
- Cache with background hython (`houdini-mcp`). 0.01 voxels in a ~0.6 unit³ chamber: 1543 frames in
  ~23–29 min on a 10-core Apple-silicon Mac; ~13–19 MB/frame with vel, ~4 MB without (16-bit).
- Run a 0.02-voxel pass first for sources and timing, then 0.01 for anything that has to pass
  through narrow gaps.
- Viewport previews for C4D: density → `convertvdb` to polygons (iso ~0.1–0.25, adaptivity 0.6) →
  Alembic every 2nd frame; see `cinema4d-alembic` for the VP side.

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

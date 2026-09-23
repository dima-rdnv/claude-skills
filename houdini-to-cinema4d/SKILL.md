---
name: houdini-to-cinema4d
description: The Houdini side of getting particles and meshes into Cinema 4D — the verified Alembic export chain (attribute clean-up, scale to C4D space, width instead of pscale, rop_alembic), one-frame read-back tests, re-exporting from a finished .abc without re-simulating, file sizes, and monitoring long exports. Use when exporting from Houdini for Cinema 4D / Redshift. Load with houdini-mcp; the C4D side is in cinema4d-alembic and cinema4d-redshift.
---

# Houdini → Cinema 4D (Houdini side)

## Particle export chain (verified end-to-end into C4D Particle Groups)
```
dopimport → attribdelete → xform (scale) → attribadjustfloat (pscale ×scale)
          → attribwrangle (f@width = f@pscale; Cd typeinfo color) → attribdelete (pscale) → rop_alembic
```
- `attribdelete`: `ptdel='* ^P ^v ^id ^pscale ^Cd ^age'`, `primdel/vtxdel/dtldel='*'` — drops ~20
  sim-only attributes (hit*, force, targetv, pprevious…).
- `xform` scales P **and** `v` (vector typeinfo) — verified speeds ×10. `pscale` is NOT scaled by
  xform: `attribadjustfloat` (`attrib='pscale'`, `operation='mult'`, `valuetype='const'`, `singlevalue`).
- **C4D reads `width` directly as particle radius and `pscale` clashes** → rename in a wrangle
  (`f@width = f@pscale; setattribtypeinfo(0, "point", "Cd", "color");`) and delete `pscale`.
  Mapping details: `cinema4d-alembic`.
- SOP `rop_alembic`: `filename`, `trange` (0 current / 1 range), `f1`, `f2`; execute with
  `parm('execute').pressButton()`. `f1/f2` default to `$FSTART/$FEND` expressions —
  `deleteAllKeyframes()` before `set()` (see `houdini-mcp`).
- Houdini writes Alembic time = frame/fps → C4D frame N = Houdini frame N.

## Verify before a full export
- Write ONE frame to a separate file, read it back (`alembic` SOP + `unpack`, transfer `*`): counts,
  attribute names, bbox, width, speed.
- For C4D-side questions (which attribute names map), export one-frame files with one candidate each
  and test them in C4D — faster than guessing on the full file.

## Re-export without re-simulating
- Read the finished .abc (`alembic` SOP, frame = `$FF`) → `unpack` (transfer `*`) → rename/clean →
  `rop_alembic` over the full range: 3600 frames of 20.6k particles ≈ 1 min.

## Sizes and long exports
- Sizes (production example): 20.6k particles ≈ 1.1 MB/frame; a VDB surface mesh ≈ 10.8 MB/frame.
  Alembic de-duplicates unchanging samples (ids, constant attributes): 3600 frames = 2.09 GB, not ~3.2 GB.
- **Long ROP exports block the bridge.** Monitor from a separate shell tool (macOS, read-only): file
  size growth (`stat -f %z` twice, 15 s apart) and whether Houdini's `idialog ... -t Interrupt`
  process is alive. Done = size stable + no idialog. Then check the range with
  `_alembic_hom_extensions.alembicTimeRange(path)`.
- Pre-cook the sim in ≤100-frame chunks (display parked) before exporting a range. If the bridge
  times out while the user scrubs past the cached range, Houdini is cooking — poll `hou.frame()`.
- Before renaming a written .abc: `_alembic_hom_extensions.alembicClearArchiveCache()`.

## Redshift Proxy route
- Needs Redshift for Houdini: check `hou.ropNodeTypeCategory().nodeTypes()` / SOP types for
  'redshift' — a Houdini 21 Indie (Mac) install had none (Sep 2026). This is the route that carries
  per-particle Cd into Redshift (the Alembic Particle Group route does not — `cinema4d-redshift`).

## Keeping this skill current
After any session that used Houdini/Cinema 4D via MCP, or whenever something new is verified:
1. Add gotchas/recipes ONLY if tested and working in a real scene; mark anything else "(unverified)".
2. Correct entries that proved wrong — don't append contradictions.
3. Put each finding in the skill it belongs to (see the indexes in `houdini-mcp` and `cinema4d-mcp`);
   project-specific facts go to that project's notes (see `project-notes`), never into a skill.
4. Keep each SKILL.md under ~300 lines; split into a new sub-skill or `references/` when it grows.
5. Re-package every changed skill (keep names) and, if the skills live in a git repo, commit and push.
   Tell the user in one line what changed.

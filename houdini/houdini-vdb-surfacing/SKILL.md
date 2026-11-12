---
name: houdini-vdb-surfacing
description: Turning Houdini particles into VDB surfaces/blobs (vdbfromparticles → vdbsmoothsdf → convertvdb → attribtransfer), with verified settings, blob-count diagnostics and how to rescale when particle count changes. Use when visualising particles as liquid/blobs/meshes or preparing VDB meshes for export. Load with houdini-mcp.
---

# Particles → VDB surface
## Surfacing particles as VDB blobs (verified)

```
dopimport (objpattern popobject1) → vdbfromparticles → vdbsmoothsdf → convertvdb → attribtransfer → null
```
- `vdbfromparticles`: `voxelsize` ≈ ⅓ of particle radius (0.004 for pscale 0.012), `radiusscale`
  1.4 so neighbours in a clump overlap and fuse, `minvoxelradius` 1.0, `bandwidthvoxels` 3.
- `vdbsmoothsdf`: `operation='meanvalue'`, `radius` 1, `iterations` 3 — rounds the blobs.
- `convertvdb`: `conversion='poly'`, `adaptivity` 0.15, `computenormals` 1.
- `attribtransfer` (input 1 = the particles): `primitiveattribs=0`, `pointattribs=1`,
  `pointattriblist='Cd'`, `kernelradius` ~2.5× pscale, `maxsamplecount` 4 — surface inherits the
  particle colour ramp.
- Verified on 10k particles: ~0.15 s/frame, 50–65k polys; 20k: ~0.2 s/frame, ~115k polys.
- **Judge fusing by blob count and the largest blob's share of polys:** `connectivity` SOP with
  `connecttype='prim'` (default is point → no prim `class`), count prims per class.
- **When particle count changes, rescale `radiusscale` by (density ratio)^(-1/3).** Verified:
  doubling to 20k at 1.4 fused 70% of the fuel into one body; 1.4 × 0.79 ≈ 1.1 gave 237 blobs,
  largest 20% (10k at 1.4: 112 blobs, largest 24%).

## Keeping this skill current
After any session that used Houdini/Cinema 4D via MCP, or whenever something new is verified:
1. Add gotchas/recipes ONLY if tested and working in a real scene; mark anything else "(unverified)".
2. Correct entries that proved wrong — don't append contradictions.
3. Put each finding in the skill it belongs to (see the indexes in `houdini-mcp` and `cinema4d-mcp`);
   project-specific facts go to that project's notes (see `project-notes`), never into a skill.
4. Keep each SKILL.md under ~300 lines; split into a new sub-skill or `references/` when it grows.
5. Re-package every changed skill (keep names) and, if the skills live in a git repo, commit and push.
   Tell the user in one line what changed.

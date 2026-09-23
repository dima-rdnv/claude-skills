---
name: houdini-pop-particles
description: Verified recipes for Houdini POP particle simulations built through MCP — dopnet wiring, sources/bursts, Static Object collisions that actually contain particles (and the failed approaches), physics-based spray deceleration (Hiroyasu–Arai), bounce, gas/piston following, clumping with POP Interact, speed ramps via POP Solver time scale, and measurement methods. Use whenever building or debugging particles, sprays, fuel injection, collisions or containment in Houdini. Load together with houdini-mcp.
---

# Houdini POP particles — verified recipes
Default approach: use Houdini's native systems (POPs, stock SOPs/DOPs) over custom solutions;
faking is fine when abstract/art-directed.

## POP particle sims — verified recipe

In this build there are **no SOP-level POP nodes**; build a `dopnet` with POP DOPs inside.
Collide with **Static Object DOPs**, not `popcollisiondetect`:

```
popobject ─────────────────────────────► popsolver::2.0 [0: Object]
popsource::2.0 → popwind → popcolor ───► popsolver     [1: Pre-Solve]
staticobject(s) ─┐
popsolver ───────┴► merge (affectortype 'ordered', colliders first) → output
```
- **Viewing:** wiring the dopnet straight into a SOP merge shows EVERY DOP object, including
  static-object collider proxies (they hide the particles). Use `dopimport` with
  `objpattern='popobject1'`, `importstyle='fetch'` for the display branch.
- Read particles with `dopnet.simulation().findObject('popobject1')` — once static objects are in
  the sim, `objects()[0]` is a collider, not the particles.

### Collisions — what actually contains and bounces (verified)
- **Working combo:** `popsolver.collisionresponse='none'` (= default bounce, uses `bounce` on
  popobject/staticobject) + staticobject `collisiondetection='surface'`, `mode='rayintersect'`
  on **clean, closed proxy geometry**. 0% leaks, real bounce.
- For a container (cylinder bore): don't collide against the production mesh. Build a proxy —
  `tube` (poly, capped) at the bore radius from head face to below BDC. Verified in ray mode with a
  plain capped tube: 0% leaks to frame 900 at 20k particles with clumping on. Moving parts (piston)
  as a separate staticobject with `animategeo=1`; unpack Alembic + `convert` to polygons first.
- **Failed approaches (don't repeat):**
  - Volume/SDF collision (`collisiondetection='volume'`) on a non-watertight mesh: bad sign, leaks.
  - Inverted SDF container (`invert=1`) on a tube: the volume ends at the tube's bbox = the wall,
    no solid voxels beyond → ~50% leak. A hollow solid (outer tube + reversed inner) also leaked
    in VOLUME mode (it contains fine in surface/ray mode).
  - `collisionresponse='none'` with volume collision: leaks. `'slide'` contains but particles
    glue to walls/crown (no bounce) and accumulate there.
  - `popcollisiondetect` defaults to `response='none'` = detect only; ray against a production
    mesh with a hairline piston/bore slit leaks through the slit.
  - `popinteract` with a POSITIVE position force (repulsion) pushes particles through colliders.
    A NEGATIVE force (attraction) is safe and gives clumping — see below.
  - `popaxisforce` type 'sphere' pulls toward its centre POINT, not toward the axis.
- Collision on thin open surfaces (valves) works with ray mode.

### Emission & motion (verified)
1. **Sims must be stepped in order** (`for f in range(start, N): hou.setFrame(f)`).
2. `emittype='allpoint'` births ONE particle per point per step, ignoring rate. Use `'point'` with
   `constantactivate=1`, `constantrate=<per second>`.
3. Set `popsource.dopobjects='*'`, `usecontextgeo=0`, `soppath=<emitter SOP>`.
4. Velocity isn't inherited unless `v` is in `inheritattrib`. Simplest: `initvel='set'`,
   `velx/y/z` + `varx/y/z` for cone spread.
5. **Spray deceleration — verified recipe (physics-based, not "viscous"):** no popforce;
   `popwind` light (`airresist` ~0.5, `amp` ~0.12, `swirlsize` ~0.25) → `popspeedlimit`
   (`dospeedmax=1`, `uselocal=1`) following Hiroyasu–Arai: speed ~constant until breakup time,
   then penetration ∝ √t → speed ∝ 1/√t, floor at ambient-gas drift (~1/10 of spray speed):
   `speedmax = @age < tb ? 3.0 : max(v0 * sqrt(tb / @age), 0.08);` (tb 0.12, v0 1.3).
   Verified: mean speed 0.84 → 0.59 → 0.34 → 0.17 across age buckets; droplets reach walls/crown.
   - Avoid an abrupt cap (`@age<0.25 ? 3 : 0.04`) — it reads as a viscous stop.
   - popwind `airresist` saturates (3.5 → effective decay ~1.4/s) and `popdrag` doesn't stack with
     popwind (same drag attributes, last wins) — don't rely on drag for spray deceleration.
   - **Gas follows the piston ("stretch" wind) — works, with two conditions:** popwind
     `uselocalwind=1`, `wind += set(0, vpist * s, 0)` with s = height fraction (1 at crown, 0 at
     roof), vpist from spare parms `ptop`/`ptop_prev` (hscript `bbox()` on the piston and on a
     `timeshift` $F-1 copy). (1) Convert to sim time: `vpist = Δy*60/timescale`, with a spare parm
     `tscale` = `ch("../popsolver1/timescale")`. (2) The speed cap floor must exceed the gas speed
     (0.25, not 0.08). An earlier attempt failed (93% on the crown) because it combined the stretch
     with an abrupt 0.04 cap. Verified: cloud trails the crown by ~0.09, wall contact 33% → 7%.
   - **Entrainment by age:** in the same VEXpression, `airresist = fit(@age, 0.3, 1.5, 0.1, 1.5);`
     — fresh spray flies free, mature droplets follow the gas.
   - Wall/piston rebound: `bounce` ~0.5, `friction` ~0.1 on popobject AND each staticobject
     (Bai–Gosman: hot walls → rebound regime with energy loss).
   - Diagnose drift with an **age-bucket table** (mean speed, mean_vy, depth per age range).
   - Count impacts with `hittotal` (cumulative). `hitnum` is per-step only.
5b. **Speed ramping (slow-mo):** keyframe **`popsolver.timescale`** (e.g. 1.0 → 0.35 with
   `ease()` keys). Verified: age advances 0.35/60 per frame after the ramp. The **dopnet's own
   `timescale` does not animate** — keys are ignored and it evaluates constant.
5c. **Clumping ("fuel-rich zones"):** `popinteract` with `positionforce` -0.25, `coreradius`
   0.015, `falloffradius` 0.05 (= clump scale), `velforce` 0. Verified: clump index 12.8 → 29.9,
   0% leaks. Measure clumping as the index of dispersion (var/mean of counts in 0.05 cells within
   the cloud's 5–95% height range; 1 = random) against a bypassed baseline. Costs ~2× per frame.
   The index grows with density, so compare runs at the same particle count only; across counts
   compare median neighbours within a radius and % empty cells.
   Prefer this over `popflock`, which aligns neighbours into swarm-like groups.
6. **Stale DOP cache:** press `dopnet.parm('resimulate').pressButton()` before verifying.
7. **Colour over the shot:** `popcolor` `colortype='ramp'`, `updatecolor=1`; its `localramp` VEX
   can use `@Frame`, `noise(@P)`, `rand(@id)`.
7b. **Hollow-cone spray (piezo injector look):** emitter = ring of ~128 points at the nozzle tip,
   each with `v` along the cone surface (half-angle ±wall thickness), speed factor `rand` 0.4–1.4
   so droplets stop at different distances; `popsource inheritattrib='v Cd ...'`,
   `initvel='add'`, small var. Verified: fresh droplets 30–45° off-axis, median 36°, none <25°.
8. Emitter that follows a part: detail wrangle on the part's geo, centroid of the lowest points,
   `removepoint` + `removeprim` everything, `addpoint` at the tip; clamp below the chamber roof
   with a spare parm if the tip is recessed in the head.
9. **Timed bursts:** keyframe `popsource.constantrate` 0 → rate → 0 (`bezier()`). Set
   `dopnet.startframe` to the shot's first frame.
10. When the scene is rescaled, rescale emitter position, velocities, variance, forces and `pscale`.
11. Measure verification with distribution stats (height/radius bands, % outside the container),
    not just counts — a narrow spray can look "contained" because it never reached the walls.

## Keeping this skill current
After any session that used Houdini/Cinema 4D via MCP, or whenever something new is verified:
1. Add gotchas/recipes ONLY if tested and working in a real scene; mark anything else "(unverified)".
2. Correct entries that proved wrong — don't append contradictions.
3. Put each finding in the skill it belongs to (see the indexes in `houdini-mcp` and `cinema4d-mcp`);
   project-specific facts go to that project's notes (see `project-notes`), never into a skill.
4. Keep each SKILL.md under ~300 lines; split into a new sub-skill or `references/` when it grows.
5. Re-package every changed skill (keep names) and, if the skills live in a git repo, commit and push.
   Tell the user in one line what changed.

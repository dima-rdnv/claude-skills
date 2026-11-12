---
name: cinema4d-particles
description: "Build and debug Cinema 4D native particles (emitters, groups, Data Mapper/Math/Look/Condition/Reproduce, forces, Cloner, Redshift) via Python/MCP, with verified IDs and traps. Load with cinema4d-mcp."
---

# Cinema 4D native particles (verified C4D 2026.1, Windows, GPU sim, Redshift)

Native system only (not Thinking Particles, not X-Particles). Everything below was tested by
stepping frames and reading particle buffers, unless marked (unverified).

## Object IDs
- Emitters: Basic Emitter **1061200**, Spline Emitter 1062564, Mesh Emitter 1062577.
- Particle Group **1060887** (`c4d.ParticleGroupObject`). Default Simulation Scene = `grp[4001]`
  (type 1057221); `c4d.CallButton(grp, 4002)` links it (optional, unlinked groups simulate too).
- Modifiers: Data Mapper **1062535**, Math **1061175**, Look **1062541**, Spin 1062542, Turn 1062543,
  Kill 1061199, Follow Spline 1063765, Color Mapper 1061780, Reproduce 1061778, Collide 1061841,
  Flock 1061637, Multi Group 1062038, Switch Group 1062045, Stick 1062128, Surface Attract 1061985,
  Particle Node Modifier 1063260. Conditions: Condition 1060726, Field Condition 1062533, Time
  Condition 1062613. **Blend 1062565 blends between neighbours — not an over-age ramp.**
- Forces that act on native particles: classic Turbulence 5115, Friction 5114, Attractor 5119,
  Gravity 5111, Wind 5149; Field Force 1041451 (+ field layers).
- List more: `c4d.plugins.FilterPluginList(c4d.PLUGINTYPE_OBJECT, True)`, IDs 1059000–1070000.
- Hidden params show up only after the mode that reveals them is set; dump the description again.

## Traps (verified)
- **`op.InsertUnder(parent)` breaks the simulation**: the object emits nothing AND every other
  emitter in the document stops (0 particles) while it exists. Moving it back does not heal it —
  delete and recreate. Always insert with `doc.InsertObject(op, parent=p, pred=prev)`.
  UI "Group Objects" (CallCommand 100004772) nesting is fine.
- An emitter (and a Reproduce modifier) inserted into a document without a group link
  **auto-creates its own "Particle Group"** next to it. After building, delete those extra groups
  (set `em[10201]` / `rep[12002]` to your group).
- **Set emitter parameters after `doc.InsertObject`**. Setting them (including `10201`) on the object
  before inserting it gave 0 particles.
- Only `doc.SetTime(t)` + `doc.ExecutePasses(None, True, True, True, 0)` simulates synchronously.
  `CallCommand(12414)` (next frame) returns before simulating — counts read 0.
- Sim state is sequential: for measurements always step from frame 0; a single jump back leaves
  stale particles from the previous run. Step at the document's own fps (`doc.GetFps()`); the user
  may change it (e.g. 30 → 90).
- Python-created `BaseDocument()` simulates native particles correctly — use it as a sandbox.
  (The "blank doc not initialised" caveat in cinema4d-mcp is about Alembic colour only.)

## Reading particle data
```python
import struct
n = grp.GetPointCount(); P = grp.GetAllPoints()           # positions (local to grp)
R = struct.unpack("%df" % n, bytes(grp.GetParticleRadiiR())[:4*n])
A = struct.unpack("%df" % n, bytes(grp.GetParticleAgesR())[:4*n])        # seconds
L = struct.unpack("%df" % n, bytes(grp.GetParticleLifetimesR())[:4*n])   # seconds
I = struct.unpack("%dI" % n, bytes(grp.GetParticleUniqueIdsR())[:4*n])
V = struct.unpack("%df" % (4*n), bytes(grp.GetParticleVelocitiesR())[:16*n])   # xyz_ per particle
Q = struct.unpack("%df" % (4*n), bytes(grp.GetParticleAlignmentsR())[:16*n])   # quaternion
```
Also `GetParticleColorsR`, `GetParticleDistancesTraversedR`, `GetParticleAngularVelocitiesR`.
Works with the default GPU device (sim scene 1000=1, "Download Particles" 2004=Auto).

## Basic Emitter parameters
| ID | Meaning |
|---|---|
| 1001 / 1002 | Shape (0 rect, 1 circle, 2 cube, 3 sphere, 4 point) / size vector |
| 10002 | Mode 0 shot, 1 constant, 2 pulse; 10003 shot count |
| 10004 / 10005 | Rate (int) / unit 0 per frame, 1 per second (fractional per-frame amounts accumulate) |
| 10014 | Seed |
| 10201 | Particle Group link |
| 10304 / 10301 / 10302 | Limit lifetime / lifetime BaseTime / variance BaseTime |
| 10401 | Direction: 0 axis, 2 normal, 3 radial, 4 random, 6 target, 7 tangential, 8 rail, 5 custom |
| 10409 / 10415 / 10410 | Speed / enable variance / **variance in absolute cm/s, not %** |
| 10411 | Add emitter velocity (0..1 fraction, UI shows %). **Broken on curved 3D motion**, see below |
| 10501 | Forward vector (2 random → random roll per particle) |
| 10601, 10604, 10608, 10609 | Spin vector (5 target) / target / spin speed **rad/s** / variance |
| 10703 / 10702 | Colour sample mode (2 random) / gradient (`c4d.Gradient`, InsertKnot) |
| 90801 / 90802 | Radius / radius variance |
| 100001, 10006, 10007 | Enabled, range on/off, start frame |

- Speed 4 with variance 50 gives average |v| ≈ 24 cm/s. Use variance = 0.5 × speed. Speeds spread
  evenly over speed ± variance (speed 10 ± 5 → offsets 0.5×–1.5×, quartiles evenly spaced).
- Circle shape emits over the whole disc; there is no inner radius or edge-only option.
- Circle + Radial (`1001=1`, `10401=3`) emits straight out from the emitter's Z axis. On a head aligned
  with `SplineHelp.GetMatrix`, the velocity was perpendicular to the path (dot with the travel direction ≈ 0.005).
- A moving emitter spreads its emission over the frame's motion (sub-frame interpolation). A point
  emitter moving 10 cm/frame gave a uniform distribution along the move, with no clumps.

## Size over life with per-particle size variation (verified)
Data Mapper writes absolute values. It has no multiply mode, so use two modifiers, **Data Mapper above
Math in the Object Manager** (execution follows OM order):
1. Data Mapper: `2022=0` (source Property), `60001=21` (Age Percentage), `2007` Lower In = shrink
   start 0..1, `2008` Upper In = 1, `2013=5` (out Radius), `2015` Lower Out 1, `2016` Upper Out 0,
   `2009=0` clamp. `2003` is the remap SplineData (default linear 0→1).
2. Math: `2011=5` target Radius, `2014=3` source Random, `2003=2` Multiply, `2018/2019` min/max,
   `2022` seed. The random value is stable per particle (seeded by ID), so radius = shrink × random
   every frame, with no accumulation.
- Never multiply Radius by a Property source every frame: it compounds.
- **Fixed shrink time** (full size → 0 over the last N frames, same speed whatever the lifetime;
  verified, max error 0.0 on dust, sparkles, clovers and burst groups): Math Radius Assign Property
  Lifetime (`2011=5`, `2014=0`, `60001=7`, `2003=4`, `2007=1`), Math Radius Subtract Property Age
  (`60001=0`, `2003=1`), then Data Mapper Property Radius In [1 .. N+1] → Out [0 .. 1], clamped.
  **Math reads Age and Lifetime in doc frames** (a 1.316 s lifetime read as 118.5 at 90 fps), and the
  value is one frame ahead of the buffer read after the step, hence In starts at 1. Put it after the
  age-percentage shrink and wrap it in Group Not Equals conditions for groups that keep the
  percentage shrink (a 9-frame head glow would start tiny). Toggle it with
  `ID_BASEOBJECT_GENERATOR_FLAG` on the three modifiers (disabling a Math that way works).
- Modifiers **above** the emitters in the Object Manager skip the birth frame. Modifiers **below**
  them also run on the birth frame.
- Property IDs (60001 / 2013 / 2011): 0 Age, 1 Color, 3 Position, 4 Velocity, 5 Radius, 7 Lifetime,
  8 Alignment, 20 Velocity Speed, 21 Age Percentage, 22 Spin Speed, 31 Custom.
- **Math with Source Property** (`2014=0`, source property `60001`) reads ONE scalar: `70004` Extract
  0 X, 1 Y, 2 Z, 7 Magnitude, 6 Dot Product (default X). On an XYZ target that scalar goes to all three
  axes, so the result points along (1,1,1). For vector math use one Math per axis: `2012=i`, `70004=i`,
  scalar multiplier `2007`. Verified: 3 Maths `position.i += velocity.i * m` moved each particle
  exactly `|v| * m` along its velocity.

## Inheriting emitter velocity (verified, C4D 2026.1)
- **Bug:** the emitter's own `10411` Add Emitter Velocity works for straight lines and flat circles
  (100% gives exactly the emitter speed). For any non-planar curved motion (a helix, a 3D spline path)
  new particles get ~0. The motion source doesn't matter: Python-tag SetMg, Align to Spline and baked
  keys all fail. 30 and 90 fps both fail. Reproduced in a blank doc; 10412/10413 (Linear/Angular) don't help.
- **Workaround (native):** a Condition 1060726 (`60001=0` Age, `2006=4` Less Than, `2008=1.0`) with a
  child Math (`2011=4` Velocity, **`2012=5` XYZ**, `2014=2` Constant, `2003=0` Add, `2008` = vector).
  A driver writes `2008 = (pos(u) - pos(u_prev)) * fps * inherit` every frame. Place the Condition
  **above the emitters** in the OM so each particle gets it exactly once (below them, most got it
  twice). Verified: fresh particles leave at ~0.9× inherit × head speed, direction dot 1.00.
- Children of a Condition apply only to matching particles. The Age value counted doc frames in a
  30 fps and a 90 fps blank doc.
- Math with a vector value needs Target Channel `2012=5` (XYZ). The default channel X adds the
  scalar value `2007` (0), which does nothing.
- Reproduced particles are newborn too (age < 1) and would pick up the added velocity. Exclude such
  groups by nesting the age Condition inside Group Conditions (`2024=6` Not Equals), one per group.

## Condition 1060726 (verified)
- `60001` property: 0 Age, 2 Group. `2006` comparison: 2 ≥, 4 <. `2008` value (Age in doc frames).
- Group: `2007` group link, `2024` 0 Equals / 6 Not Equals.
- `2019` Chance / `2020` seed: **re-rolled every frame** for every matching particle, so it acts as
  a random delay, not a one-time filter. For an overall probability P within `N` frames use a
  per-frame chance `p = 1 - (1 - P) ** (1 / N)` and kill the particle after N frames (lifetime).
- Nested Conditions = AND. Sibling Conditions don't combine; each applies only to its own children.
- Below the emitters, `Age < 1` matches twice (birth frame and the next one). Nested `Age ≥ 1` >
  `Age < 2` fires exactly once, one frame after birth.

## Reproduce 1061778 (verified)
| ID | Meaning |
|---|---|
| 4003 / 4011 | Count / count variance (absolute) |
| 4004 | Scatter: **0 Per Particle**. Default 1 Distribute splits the count across all matching particles |
| 4005 / 4006 / 4010 | Kill source / mode 0 Once, 1 Constant / seed |
| 12002 | Target Particle Group |
| 7003 / 7001 / 7011 / 7002 | Direction (4 Random = 360°, 3 Radial) / speed / speed variance (cm/s) / speed inheritance |
| 10005 / 10001 / 10002 | Limited lifetime / lifetime / variance (BaseTime) |
- Two Reproduce on one source (e.g. dust + sparkles): kill source off on the first, on for the last.

## Per-group drag (verified)
Condition (Group Equals) > Math (`2011=4` Velocity, `2012=5`, `2014=2` Constant, `2003=2`
Multiply, `2008=c4d.Vector(k)`). This runs every frame, so use `k = (1 - slow) ** (30 / fps)` to
keep the look fps-independent ("slow" = fraction lost per 1/30 s). With slow 0.2 at 90 fps a 60 cm/s
pop decayed to 0.4 cm/s in 60 frames.

## Look: face the camera (verified)
`13001=5` (Target), `13004=camera`, `13007=0` (Up = Alignment Up, keeps random roll), `13011=0` (Set).
Particle +Z then points exactly at the target (clone v3·dir = 1.000). Emitter spin with target
vector = camera still rolls the particle around that axis.

## Forces, measured (300 particles, speed 4±2, sphere emitter, 2 s)
| Setup | Mean displacement / speed at 2 s |
|---|---|
| none | 8 cm / 4 cm/s |
| Turbulence 1 | 17 cm / 14 cm/s |
| Turbulence 1 + Friction 100 | **11 cm / 7 cm/s** (a calm dissipating trail) |
| Turbulence 6 + Friction 20 | 60 cm / 38 cm/s (explodes a fine trail) |
- Turbulence: 1000 strength, 1003 frequency. The 1002 scale changed nothing on native particles.
- Friction 5114: 1000 strength is weak. 100 roughly halves speed over 2 s.
- **Friction grows steeply with speed.** At 90 fps, strength 100: ~3% speed lost per frame at 60 cm/s,
  but ~90% per frame at a few hundred cm/s. "Shoot out fast, then settle" can't reach a set distance
  in a few frames. Place particles with a position offset instead (see the bursts recipe).
- Turbulence and Friction have no group filter; they act on every group, hidden helper groups too.
- Field Force: `fl = ff[1000]; lay = c4d.modules.mograph.FieldLayer(c4d.FLfield);
  lay.SetLinkedObject(randomField); fl.InsertLayer(lay); ff[1000] = fl; ff[1001] = strength`.

## Cloner on particles (verified)
- Cloner 1018544, `ID_MG_MOTIONGENERATOR_MODE_OBJECT`, `MG_OBJECT_LINK = group`.
- **`cloner[1041]` "Particle Scale" is a blend, not a multiplier:** clone scale = `1 + ps × (radius − 1)`
  (verified in a blank doc: ps 1 → scale = radius; ps 2.2 → radius 0.1 gives 0.98, 0.5 gives 0.1,
  2.0 gives 3.2). Default 0 = no scaling. Any ps > 1 makes shrinking clones pass through 0 and grow
  back (mirrored) before they die. **Keep ps = 1** and put a size factor on the radius instead:
  Condition (Group Equals the clone group) > Math Radius × constant (`2011=5`, `2014=2`, `2003=2`,
  value `2007`), after the size chain. Clones take the particle alignment.
- Clones lag one frame behind the particles unless the sim scene's "Simulate Before Generators"
  (`scene[1017]`) is on (verified in a blank doc). This is a project-wide setting, so ask before
  changing it in a user's scene.
- Read clones: `md = c4d.modules.mograph.GeGetMoData(cloner); md.GetArray(c4d.MODATA_MATRIX)`.

## Redshift (verified)
- RS Object tag 1036222 on a native Particle Group: `2999=True`, `3000=5` (optimized spheres),
  `3001` scale multiplier × particle radius. Material = texture tag on the group.
- A group used only as a Cloner source: tag `3000=0` so it doesn't also render spheres.
- Emissive materials read well without lights. For shading recipes see cinema4d-redshift.

## Recipe: travelling-emitter trail (dust + sparkles + camera-facing sprites)
- A "Head" null moved along a spline (driver: see cinema4d-rigging), with one Basic Emitter per look
  as children (sphere shape, random direction). Use separate groups (dust, sparkles, clovers/sprites,
  short-lived head glow) so each gets its own size and material.
- Rate per second = density (per cm) × cm travelled last frame × fps. This keeps density even under
  eased keys and stops emission when the head stops.
- Shrink chain + Look + Turbulence ≈1 + Friction ≈100. Head glow: lifetime 1–2 frames.
- Inherit head velocity with the Condition + Math workaround above (≈10–30% reads as a comet pull).
- Scale reference: camera 36 mm at ~128 cm from the subject gives ≈15 px/cm at 1920 wide. Dust
  radius ≈0.03–0.1 cm and sparkles ≈0.1–0.3 cm read like fine gold dust.

## Recipe: delayed 360° bursts along the trail ("fireworks" pops, verified)
1. Seeds: one more Basic Emitter on the head into a "Burst Seeds" group. Rate/s = cm travelled last
   frame / spacing × fps. Lifetime = delay + range frames, so seeds that don't pop die (the shrink
   chain fades them out first). Two verified ways to move them:
   - **Visible rockets, set by speed + delay:** emitter circle 0.1 cm + Radial (straight out from the
     path), speed = seed speed, variance = speed × variation. RS tag `3000=5` + the burst material,
     `3001` from a "Seed Size" control (0 = hidden, `3000=0`). Friction, turbulence and the
     inherit-velocity chain act on them like on the trail. Measured at 90 fps, 103 cm/s, Friction 100,
     delay 2 + range 23 frames: pops 2.4–11.8 cm from the launch point. Seed size ≈ 2.5 × the sparkle
     size read as a distinct spark; 1× was lost among the trail sparkles.
   - **Exact distance from the path:** same emitter with speed `s` = 10, variance
     `s × distance_variation`; under the modifiers Condition (Group Equals seeds) > Condition
     (Age < 1) > three Maths `position.i += velocity.i × (distance / s)` (per-axis, see Math) >
     Math velocity × 0; exclude the seeds from the inherit-velocity chain, or its add gets turned
     into a 2nd offset. Verified: distance 40, variation 0 → 39.7–40.0 cm; variation 0.5 → 21.7–57.3 cm.
   (Drifting seeds at a speed computed from a target distance under-shot badly: friction, sub-frame
   births and pop timing all changed the distance.)
2. Under the modifiers: Condition (Group Equals seeds) > Condition (Age ≥ delay, chance p from the
   formula above, fixed seed) > Reproduce → Burst Dust (kill off) + Reproduce → Burst Sparkles (kill on).
   Direction Random, speed inheritance 0, Scatter Per Particle, limited lifetime.
3. Per-group drag (above) on each burst group gives the fast-pop-then-hang look. Turbulence and the
   shared Friction still apply.
4. Keep the burst groups out of the inherit-velocity Condition (Group Not Equals wrappers).
- Verified: pops scattered in time (not all at age = delay), 80±40 dust + 12±6 sparkles per pop,
  ~6–8 cm radius at 60 cm/s with slow 0.2; no head velocity on burst particles.
- Delay, range and lifetime are in **doc frames**; they get shorter in seconds if the user raises fps.

## Keeping this skill current
After any session that used Houdini/Cinema 4D via MCP, or whenever something new is verified:
1. Add gotchas/recipes ONLY if tested and working in a real scene; mark anything else "(unverified)".
2. Correct entries that proved wrong — don't append contradictions.
3. Put each finding in the skill it belongs to (see the indexes in `houdini-mcp` and `cinema4d-mcp`);
   project-specific facts go to that project's notes (see `project-notes`), never into a skill.
4. Keep each SKILL.md under ~300 lines; split into a new sub-skill or `references/` when it grows.
5. Re-package every changed skill (keep names) and, if the skills live in a git repo, commit and push.
   Tell the user in one line what changed.
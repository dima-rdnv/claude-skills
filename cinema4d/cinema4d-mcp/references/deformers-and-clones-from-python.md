# Deformers on MoGraph clones, and the Collision deformer, from Python (verified C4D 2027.0, Windows)

## Measure before you trust a deformer
- Compare the deformed object's `GetDeformCache()` points with the deformer's generator flag on and off. Step the time
  (`f-1` then `f`) before each read: toggling a deformer at the same frame did not re-evaluate a Cloner that only reads it
  through a link (a Python effector), so the "after" values were stale.
- Use a control deformer you know moves points (Wind, `5149`, moved a plane at once). A default Bulge moved nothing, so it is a
  bad control.

## Collision deformer (`1024544`)
- **Colliders list `[1000]`: insert with flags 3.** `InExcludeData.InsertObject(obj, 1)` (the usual "enabled") left the
  deformer doing nothing: no movement in script evaluation, in a live GUI document after `DrawViews`, or in c4dpy, with any
  solver. Flags 3 (or 255) made it work.
- Solver `[1008]`: 0 Intersect, 1 Inside, 2 Outside, 3 Outside (Volume), 4 Inside (Stretch). Restore Shape `[1007]` 1.0 = no
  memory between frames. Fall-off `[1009]` (3 None, 1 Distance) with distance `[1001]`: Distance made no measurable difference.
- On tube meshes passing through closed ellipsoid colliders: Intersect cleared every penetration with the smallest moves; Outside
  cleared them with moves twice as large; Outside (Volume) left many points inside (and moved nothing on an open plane).
- **Stateless solving pops in animation:** points deep inside a collider snap to whichever side is nearer and flip between frames
  as the object moves (frame-to-frame acceleration p99 ~25x the undeformed motion). Keep penetrations shallow (smaller collider,
  move the colliders a little first), or use the deformer's cache with Restore Shape < 100 % so frames carry over.
- A Cloner works as a collider; with instance mode "Instance" its cache holds real polygon objects. Cost: ~2.5 s per frame for
  ~21k points against 320 low-poly ellipsoids (92k polygons).
- Collider proxy that follows other clones exactly: a copy of the Cloner (same Object link, same effector list) cloning the proxy
  shape; identical matrices (offset 0.0). Bake any offset into the proxy's points, because with Fix Clone the child's own transform
  is ignored.

## Instances inside a Cloner
- An Instance object under a Cloner (Fix Clone on) rendered at the clone's scale; the Instance's own 0.1 scale was ignored, and so
  was the source object's position. Measure clone sizes from a render or the source geometry × clone matrix, not the Instance's
  matrix.

## Make clones ride a deformer without bending them (no Deformer effector in 2027)
- The MoGraph Deformer effector is not among 2027's object plugins; every effector's "Deformer" tab (Off / Object / Point /
  Polygon) is for using an effector AS a deformer.
- Python effector (Full Control): per evaluation, put the current clone centres (plus two probe points per clone for rotation)
  into a point object in a scratch `BaseDocument` (same fps and time), add a clone of the linked deformer
  (`COPYFLAGS_NO_HIERARCHY | COPYFLAGS_NO_ANIMATION`, `SetMg` = the original's global matrix), `MCOMMAND_CURRENTSTATETOOBJECT`, and
  move each clone by its centre's displacement. Its displacement matched the scene's deformer within ~10 % on the deformed mesh.
- Deformers stack top to bottom among siblings: the follow only matches when the followed deformer is the LAST one on the mesh;
  with another point deformer after it (e.g. a Shader effector in Point mode), the mesh motion near a clone differs from the
  deformer's own field.
- A deformer one hierarchy level up also deforms hidden "Clone to" objects, so the clones' base positions move too: the same
  deformer then acts twice on the clones.

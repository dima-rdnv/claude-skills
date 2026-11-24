# Two scene files into one file of takes (verified C4D 2027.0, c4dpy, Nov 2026)

Use when the user wants the stills or variants of two scenes in ONE file ("less files, easier to tweak the materials").
Done for a 30 fps close-up scene (base) and three still takes of a 60 fps engine scene; every take of the result matched its
old file object by object.

## 1. Pick the base by what is frame-numbered
- A document has one frame rate. Frame-numbered content must stay in its own document: VDB sequences (`name.####.vdb` follows
  the document frame) and Particle Groups from Alembic (samples map to document frames). Keyframes, Alembic generators and a
  one-sample Alembic are time-based and survive a move.
- So the base is the file with frame-numbered content in its takes; bring in the other file's takes only if what they
  render at their frame is time-based. Frame f at A fps becomes f·B/A at B fps (1880 at 60 = 940 at 30); assert that
  `BaseTime(f2, B).Get() == BaseTime(f, A).Get()`.

## 2. Take the source as the state of one take
- `doc_t = td.TakeToDocument(take)` gives a document whose Main IS that take, with every inherited override applied (the take
  tree is not needed any more). Use the fullest take (the one whose rendered set includes the others).
- The other takes: their own `TakeToDocument` documents have the same hierarchy. Match objects by path (names + index among
  same-named siblings) and record what differs: visibility 901/902, Enabled 906, tag container values (read by index:
  `GetIndexId` / `GetType`; keep `DA_LONG` / `DA_REAL` / `DA_VECTOR`). Three still takes of an engine scene differed in 2 and
  18 values (particles / instances / background visibility, two lights' Enabled, ten RS Object tag values).

## 3. Trim before merging
- Keep: objects that render (effective render visibility, and not a null, camera or spline), every light, a rig subtree as a
  whole (XPresso / Python tags), the take camera, plus a link closure over everything kept: object links in each kept
  object's and tag's container (by index — `for k, v in bc` stops at the first odd data type), InExclude lists, XPresso node
  operator containers (`GetNodeMaster().GetRoot()` → `GetOperatorContainer()`), and all children of generators
  (`GetInfo() & c4d.OBJECT_INPUT`: lathe profiles, cloner sources). Hidden render-instance masters come along through the
  instances' links. 1043 objects → 958; shot cameras, hidden sims and old particle groups dropped.
- Map keys across the trim with `GetGUID()` (stable inside one document). Delete the takes, save to a temp file,
  `MergeDocument(base, temp, OBJECTS | MATERIALS)` (adds no takes), move the new top-level objects under one null with an
  identity matrix.
- Materials with the same name in both files: compare the node graphs (per node: asset id, every input port value, connection
  count); when equal, relink the merged texture tags to the base file's material and remove the copy. Remove merged
  materials no texture tag uses.

## 4. Hide each side in the other's takes
- Main: the merged null's visibility Off; every merged object with explicit On (0) → Off too (explicit On beats a hidden
  parent); merged lights Enabled off.
- New branch take under Main: merged null → Default (2), those explicit-On objects → On, lights → their recorded Enabled;
  the base file's top-level objects and its explicit-On objects → Off, its enabled lights → Enabled off. Switch lights with
  Enabled, objects with visibility.
- Child takes carry only their recorded differences, and each switchable parameter is set on the children only (see the trap
  in SKILL.md: overriding it on the parent too broke the siblings).
- Render settings: `GetClone(c4d.COPYFLAGS_NO_HIERARCHY)` of the source render settings into the base document, manual frame
  range at the converted frame, `RDATA_FRAMERATE` = the base fps, output path unchanged.

## 5. Verify every take without rendering
- For each take, `TakeToDocument` in the old and the new file at its render frame (`SetTime` + `ExecutePasses`), then per
  object: effective render and editor visibility (not the raw flags, which change for explicit-On objects), Enabled, global
  matrix, container values, tag containers (material links by name), point counts; the take's render setting values and
  every videopost container; the scene camera. New objects must be hidden and their lights disabled in the other side's takes.
- What was left after a correct merge: an icon-colour field and two dynamic values on a disabled emitter.
- `GetAllAssetsNew`: every linked file still found. A render comparison is still the final proof; it needs a free GPU and
  the user's OK.

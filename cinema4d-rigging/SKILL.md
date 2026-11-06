---
name: cinema4d-rigging
description: "Build and fix Cinema 4D control rigs via Python/MCP: user data, keyed controls, monotone retiming of cycle controls, Python tag drivers, XPresso/tag evaluation-order lag, slider-crank, spline travel, HUD. Load with cinema4d-mcp."
---

# Cinema 4D rigs: user data + Python tag driver (verified C4D 2026.1)

Pattern: one control null holds all user data, and one Python tag on it pushes the values into
native objects every frame. Native objects do the work. Python only moves and connects things.

## User data
```python
def ud_group(op, name, parent=None):
    bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_GROUP)
    bc[c4d.DESC_NAME] = bc[c4d.DESC_SHORT_NAME] = name; bc[c4d.DESC_COLUMNS] = 1; bc[c4d.DESC_DEFAULT] = 1
    if parent: bc[c4d.DESC_PARENTGROUP] = parent
    return op.AddUserData(bc)
def ud_real(op, grp, name, val, mn, mx, unit=c4d.DESC_UNIT_FLOAT, smax=None, step=0.01):
    bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
    bc[c4d.DESC_NAME] = bc[c4d.DESC_SHORT_NAME] = name
    bc[c4d.DESC_UNIT] = unit            # DESC_UNIT_PERCENT (0..1 shows %), DESC_UNIT_METER (shows cm)
    bc[c4d.DESC_MIN], bc[c4d.DESC_MAX], bc[c4d.DESC_STEP] = mn, mx, step
    bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
    bc[c4d.DESC_MINSLIDER], bc[c4d.DESC_MAXSLIDER] = mn, (smax if smax is not None else mx)
    bc[c4d.DESC_PARENTGROUP] = grp
    did = op.AddUserData(bc); op[did] = val; return did
def ud_cycle(op, grp, name, items, val=0):
    bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
    bc[c4d.DESC_NAME] = bc[c4d.DESC_SHORT_NAME] = name
    bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_CYCLE
    cyc = c4d.BaseContainer()
    for i, s in enumerate(items): cyc.SetString(i, s)
    bc.SetContainer(c4d.DESC_CYCLE, cyc); bc[c4d.DESC_MIN], bc[c4d.DESC_MAX] = 0, len(items) - 1
    bc[c4d.DESC_PARENTGROUP] = grp
    did = op.AddUserData(bc); op[did] = val; return did
# link: c4d.DTYPE_BASELISTLINK, same pattern; int: c4d.DTYPE_LONG without the cycle GUI
```
- IDs are sequential and groups consume IDs too. Print `{name: did[1].id}` after building and
  hard-code those IDs in the driver.
- Read and write: `op[c4d.ID_USERDATA, id]`. To edit a definition later, loop
  `op.GetUserDataContainer()` → change bc → `op.SetUserDataContainer(did, bc)`.
- Put the whole user data build in one bridge call. Keep `SetUserDataContainer` edits to the main thread.
- Attribute Manager order = the order of `GetUserDataContainer()`, not ID order.
  `SetUserDataContainer(did, bc)` with an unused ID creates the entry at the end.

## Insert a control in the middle of existing user data (verified)
Adding to an existing rig puts the new entry last. To place it right after entry `X`:
```python
entries = [(d, c4d.BaseContainer(bc)) for d, bc in op.GetUserDataContainer()]
k = [d[1].id for d, bc in entries].index(X)
def val(d):
    try: return op[d]
    except Exception: return None              # groups have no value (reading raises)
tail = [(d, bc, val(d)) for d, bc in entries[k + 1:]]
for d, bc, v in reversed(tail): op.RemoveUserData(d)
op.SetUserDataContainer(new_did, new_bc); op[new_did] = value     # new_bc: copy a sibling's bc
for d, bc, v in tail:                          # same IDs, so the driver keeps working
    op.SetUserDataContainer(d, bc)
    if v is not None: op[d] = v                # links (folders) restore too
```
- Removing an entry also drops its animation track and take overrides. Check
  `op.GetCTracks()` and the takes first, and only move entries that have none.
- IDs may already be taken by fields the user added (e.g. a stray "Data" entry). Check the ID list
  before choosing a new ID, and leave their entries alone.

## Keyframing user data
```python
did = c4d.DescID(c4d.DescLevel(c4d.ID_USERDATA, c4d.DTYPE_SUBCONTAINER, 0),
                 c4d.DescLevel(uid, c4d.DTYPE_REAL, 0))
tr = op.FindCTrack(did) or c4d.CTrack(op, did); op.InsertTrackSorted(tr)
cv = tr.GetCurve()
k = cv.AddKey(c4d.BaseTime(frame, fps))["key"]; k.SetValue(cv, value)
k.SetInterpolation(cv, c4d.CINTERPOLATION_SPLINE)
```
- Two SPLINE keys with default tangents evaluated linearly. Set tangents if you need an ease.
- Value at any time: `tr.GetValue(doc, basetime)`. The driver uses this for "previous frame" values.
- Hard cuts in a camera move: a key with `CINTERPOLATION_STEP` holds its value until the next key —
  put one on the last frame of a shot and the next shot's first value on the cut frame (verified).

## The Python tag driver
```python
tag = rig.MakeTag(c4d.Tpython); tag.SetName("... Driver")
tag[c4d.TPYTHON_CODE] = CODE
pd = tag[c4d.EXPRESSION_PRIORITY]
pd.SetPriorityValue(c4d.PRIORITYVALUE_MODE, c4d.CYCLE_EXPRESSION)
pd.SetPriorityValue(c4d.PRIORITYVALUE_PRIORITY, -100)
tag[c4d.EXPRESSION_PRIORITY] = pd
```
- **Priority must be Expression, not Initial.** Initial runs before the animation pass, so keyed
  user data is read one frame late. In the verified case, that made the emission rate always 0.
  Expression still runs before generators and the particle simulation.
- Inside the tag `op` is the tag: `rig = op.GetObject()`, `doc = op.GetDocument()`.
- Find rig parts by name among the rig's children. Use a Link user data field for things outside
  the rig (such as a folder of paths).
- Only write a parameter when the value changes, to avoid dirtying the scene every frame:
```python
def setp(o, pid, v):
    if o is None: return
    try: cur = o[pid]
    except Exception: cur = None
    if isinstance(v, float) and isinstance(cur, float):
        if abs(cur - v) < 1e-6: return
    elif cur == v: return
    o[pid] = v
```
- Passing the code through the bridge: build the string in the sandbox with `repr(open(f).read())`
  after `py_compile`, paste it as `CODE = '...'` **inside** `main()`. The bridge echoes top-level
  variables, and a 6 kB code string doubles the reply. The code must not contain `exec(`/`eval(`/
  `import os` (blocked by the bridge filter).
- Patch an existing tag: `code = tag[c4d.TPYTHON_CODE]; tag[c4d.TPYTHON_CODE] = code.replace(a, b)`.
  Read the live code first (the user or an earlier patch may have changed it), check that `a` is
  in it, and refuse to patch otherwise. Test the whole patch on `doc.GetClone(COPYFLAGS_DOCUMENT)`
  before touching the real scene.

## Dropdown that follows a folder's children (verified)
Implement `message(id, data)` in the tag. It is called often on the main thread:
```python
def message(mid, data):
    if c4d.threading.GeIsMainThreadAndNoDrawThread():
        rig = op.GetObject()
        if rig: sync_cycle(rig)     # rebuild DESC_CYCLE from children names, set DESC_MAX,
    return True                     # SetUserDataContainer only when the list changed
```
Adding a spline under the linked folder added a 4th menu entry right away, and removing it
restored 3. In `main()`, clamp the index to the child count.

## Length-uniform travel along a spline (verified)
```python
from c4d.utils import SplineHelp
sh = SplineHelp()
sh.InitSplineWith(sp, c4d.SPLINEHELPFLAGS_GLOBALSPACE | c4d.SPLINEHELPFLAGS_CONTINUECURVE)
length = sh.GetSplineLength()
head.SetMg(sh.GetMatrix(u, realoffset=True, smooth=True))   # u 0..1 = fraction of real length
```
- Cache the helper per spline, keyed by `(name, sp.GetDirty(DIRTYFLAGS_DATA | DIRTYFLAGS_CACHE),
  sp.GetMg())`, and rebuild it when the key changes.
- Distance moved this frame = `(u_now - u_prev) * length`. Use it to drive emission per cm, so
  eased keys don't bunch particles (see cinema4d-particles).

## HUD
- No Python API was found. Use the UI: select the object → Attribute Manager → User Data tab →
  right-click the parameter label → **Add to HUD**. Cycle params show as a dropdown and reals as a
  slider, placed in the active viewport next to the object.
- With computer use, the first click on a context-menu item may only highlight it. Screenshot and
  click again.

## Procedural splines and meshes (verified)
- Spline: `sp = c4d.SplineObject(n, c4d.SPLINETYPE_AKIMA)`, `SetAllPoints`,
  `sp[c4d.SPLINEOBJECT_INTERPOLATION] = c4d.SPLINEOBJECT_INTERPOLATION_UNIFORM`,
  `sp.Message(c4d.MSG_UPDATE)`. Mirror a Bezier spline: negate x on each point and on both tangents,
  `sp.SetTangent(i, vl, vr)`.
- Mesh: `c4d.PolygonObject(np, npoly)`, `SetAllPoints`, `SetPolygon(i, c4d.CPolygon(a, b, c[, d]))`
  (a triangle has c == d), `MSG_UPDATE`, Phong tag (`PHONGTAG_PHONG_ANGLELIMIT`, `_ANGLE` in rad).
- `c4d.utils.CalcFaceNormal` does not exist in 2026. Compute `(b - a).Cross(d - a)` and flip the
  winding if the sum points the wrong way (the facing side convention is unverified; check a render).
- Inflated "pillow" leaf from any outline: rings scaled toward the centroid by cos(a) at height
  h·sin(a), then an apex, with a shallow back. Heart outline: x = 16 sin³t,
  y = 13 cos t − 5 cos 2t − 2 cos 3t − cos 4t. Four hearts rotated 90° apart, tips at the centre,
  make a clover.

## Python Generator that builds geometry from other objects (verified C4D 2026.4)
- A Python Generator (`c4d.Opython`, code in `OPYTHON_CODE`) can return a hierarchy of generators:
  a Null holding one `Osweep` per wire (circle profile + `SplineObject`) builds fine.
- Set `OPYTHON_OPTIMIZE = False` so it sees changes in linked objects. Then cache it yourself:
  build a signature (clone positions, `path.GetDirty(DIRTYFLAGS_DATA)`, `str(path.GetMg())`,
  `str(op.GetMg())`, `op.GetDirty(DIRTYFLAGS_DATA)`) and `return op.GetCache()` when it is unchanged.
  Verified: toggling a Plain effector, editing the path and changing user data all rebuilt it.
- Clones after effectors: `GeGetMoData(cloner)`, `MODATA_MATRIX` (cloner space) and
  `MODATA_FLAGS & MOGENFLAG_CLONE_ON` (cleared by a Plain effector's Visibility). With
  `MGCLONER_FIX_CLONES` (Reset Coordinates) on, a clone's world matrix is `cloner.GetMg() * m`;
  a point inside the clone source is that `* (~src.GetMg() * tip.GetMg())`. Put the generator
  below the Cloner in the hierarchy.
- Read settings by user-data name each call (`{bc[DESC_NAME]: op[did]}`) so IDs aren't hard-coded.
- `c4d.DESC_DESCRIPTION` does not exist (no tooltip constant). A dict with int keys can't go
  through `**kw`: pass it as a plain argument.
- Long code: write it to a file, `py_compile` it, and `open(path).read()` it inside `exec_python`
  (the Maxon adapter reads local files), instead of pasting it into the call.
## Evaluation order: one-frame lag between tags (verified)
Symptom: a part driven by XPresso from another object's **global** position trails by one frame,
and after a timeline jump it is far off (an Alembic export then has a bad first frame).
- Test: `SetTime(t)`, one `ExecutePasses`, read; a second `ExecutePasses`, read again. Different
  values = lag. Test after jumps (0 → 300 → 100), not only sequential frames.
- Cause seen: XPresso (Expression 0) read the end of a con-rod whose parent is aimed by a Target
  tag at Expression 10 — the XPresso ran before the aim was updated.
- Fix: move only the dependent link (read global pos → write) into a **second XPresso tag** with a
  priority above the tag it depends on (here 20). Ports by DescID:
```python
gy = c4d.DescID(c4d.DescLevel(c4d.ID_BASEOBJECT_GLOBAL_POSITION, c4d.DTYPE_VECTOR, 0),
                c4d.DescLevel(c4d.VECTOR_Y, c4d.DTYPE_REAL, 0))
nm = tag.GetNodeMaster(); root = nm.GetRoot()
n = nm.CreateNode(root, c4d.ID_OPERATOR_OBJECT, None, 100, 100); n[c4d.GV_OBJECT_OBJECT_ID] = src
out = n.AddPort(c4d.GV_PORT_OUTPUT, gy)          # then the same for the target node (GV_PORT_INPUT)
out.Connect(inp); nm.Message(c4d.MSG_UPDATE)    # remove the old nodes only after Connect() is True
```
- Priority on any tag: `pd = tag[c4d.EXPRESSION_PRIORITY]; pd.SetPriorityValue(c4d.PRIORITYVALUE_MODE, 2)`
  (2 = Expression), `PRIORITYVALUE_PRIORITY`, write it back.

## Before retiming an existing rig, look for baked leftovers (verified)
Rigs prepared for an earlier bake can still contain baked helper copies: nulls/objects with one
key per frame (`… (baked target)`, `… (Copy)`, `… (Baked)` instances), sometimes still visible or
still **linked** (e.g. a Target tag aiming at a baked null). After a retime they play the old
timing: doubled parts, or a wobble at the old cycle period. Check:
- every Target tag: `tg[c4d.TARGETEXPRESSIONTAG_LINK]`, `tg[c4d.TARGETEXPRESSIONTAG_UP_LINK]`;
- objects with ~1 key per frame (`cv.GetKeyCount()` ≈ frame count) and their visibility.
Hide/mute rather than delete: `tr[c4d.ID_CTRACK_ANIMOFF] = True`, visibility 1 = off.

## Slider-crank (piston) target, live (verified)
For a con-rod aimed by a Target tag, place the target on the cylinder axis at rod length from the
crank pin; the rod end then lands exactly on the axis at every crank angle:
```python
# Python tag on the target null, Expression 5 (after the shaft driver at 0, before the Target tag at 10)
P = pin.GetMg().off; L = (rod_end.GetMg().off - P).GetLength()     # rigid pin -> rod end
axis_x = obj.GetUp().GetMg().off.x
mg = obj.GetMg(); mg.off = c4d.Vector(axis_x, P.y + math.sqrt(max(L*L - (P.x-axis_x)**2, 0)), mg.off.z)
obj.SetMg(mg)
```
Pass `pin` / `rod_end` as Link user data on the tag. Reproduced the original TDC/BDC heights exactly.

## Retiming a cycle control with monotone keys (verified)
To re-time an angle/progress control (crank angle, path %) to story beats without overshoot or
reversal, key the beats and set Fritsch–Carlson tangents yourself:
```python
K = [(sec, value), ...]                                   # strictly increasing values
h = [K[i+1][0]-K[i][0] for i in range(len(K)-1)]; dl = [(K[i+1][1]-K[i][1])/h[i] for i in range(len(h))]
m = [dl[0]] + [0]*(len(K)-2) + [dl[-1]]
for i in range(1, len(K)-1):
    w1, w2 = 2*h[i]+h[i-1], h[i]+2*h[i-1]
    m[i] = 0 if dl[i-1]*dl[i] <= 0 else (w1+w2)/(w1/dl[i-1] + w2/dl[i])
cv.FlushKeys()
for i, (t, v) in enumerate(K):
    k = cv.AddKey(c4d.BaseTime(t))["key"]; k.SetValue(cv, v); k.SetInterpolation(cv, c4d.CINTERPOLATION_SPLINE)
    k.ChangeNBit(c4d.NBIT_CKEY_AUTO, c4d.NBITCONTROL_CLEAR); k.ChangeNBit(c4d.NBIT_CKEY_BREAK, c4d.NBITCONTROL_SET)
    if i > 0:        k.SetTimeLeft(cv, c4d.BaseTime(-h[i-1]/3)); k.SetValueLeft(cv, -m[i]*h[i-1]/3)
    if i < len(K)-1: k.SetTimeRight(cv, c4d.BaseTime(h[i]/3));   k.SetValueRight(cv, m[i]*h[i]/3)
```
- Angle user data with unit degrees stores **radians**: key `math.radians(deg)`.
- Verify by sampling `cv.GetValue(BaseTime)` densely: monotonic, and every key hit exactly.
- Before keying, map the mechanism once (sample the part positions over one cycle at 10° steps,
  two passes per sample) so beats can be expressed as angles (e.g. TDC/BDC, valve open ranges).

## Deliver the rig
- Wrap edits in `doc.StartUndo()` / `AddUndo(UNDOTYPE_NEWOBJ | CHANGE, …)` / `EndUndo()`, then `c4d.EventAdd()`.
- The user may edit the scene while you work (lights and views appeared mid-session). Re-read the
  hierarchy before each structural change. Don't overwrite the user's file: when work should be
  saved, Save-As under the user's versioning convention (e.g. a date suffix) — see `cinema4d-mcp`.

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

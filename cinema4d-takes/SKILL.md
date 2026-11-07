---
name: cinema4d-takes
description: "Cinema 4D Takes through Python/MCP: read a scene's takes and overrides, add takes with parameter/user-data overrides, edit override values, cameras, render settings and override groups, verify each take via TakeToDocument, and render variants. Load with cinema4d-mcp."
---

# Cinema 4D Takes (verified C4D 2026.1)

Takes are a common way to render several variants of one scene (e.g. one take per path of a rig, rendered
with the `$take` token in the output path). **Before changing a scene, list its takes.** A
parameter the user overrides in a take will not follow an edit made in the Main take.

**Default for any variant (v2 look, alternative setting, extra output):** a take that overrides only
the parameters that differ, plus a child render setting under the shot's render setting that changes
only the differing render values. No scene copies, no full duplicate render settings, unless the user
asks for files. New generator/rig features must reproduce the old look at their default values, so
Main keeps the old look and the take switches the new controls on.

## Child render settings from Python (verified C4D 2027.0, throwaway documents)
- A `RenderData` inserted under a parent with `doc.InsertRenderData(child, parent, None)` reads the
  parent's values and keeps following later parent edits — as long as nothing writes to it.
- **One plain write detaches the whole child**: after `child[RDATA_XRES] = 1000`, parent changes to
  any other parameter no longer reached it (same with `SetParameter(..., DESCFLAGS_SET_USERINTERACTION)`
  or `DESCFLAGS_SET_NONE`). A write of the value it already has did not detach it.
- `DESCFLAGS_SET_DONTAFFECTINHERITANCE` keeps it attached, but the written value is replaced by the
  next parent change and is not kept through save/load — not an override.
- "Inherit Parent Behavior" is not in the public API (Maxon forum: internal
  `RENDERSETTINGS_BIT_OVERRIDEBEHAVIOUR`, 1 << 6; staff: it is not continuous copying and works poorly
  from Python). A clone takes the flag of the parent it was cloned from. What the UI then does with
  the user's own parent edits is unverified.
- So: build each child as a clone of its parent without its children (see the `GetClone` note below),
  write only the differing parameters, and when a script changes a parent value later, write the same
  value into every child that doesn't intentionally differ (compare with the parent's old value).
  List each child's intended differences in its name or a note so they stay visible.
- Take overrides can't target render settings: `FindOrAddOverrideParam(td, renderdata, …)` returned
  None. Assign per-take render settings with `t.SetRenderData(td, child)` instead.

## Read what exists
```python
import maxon          # printing some override values fails with "maxon module needs to be imported first"
td = doc.GetTakeData(); main = td.GetMainTake(); cur = td.GetCurrentTake()
def walk(t, d=0):
    while t:
        cam = t.GetCamera(td); rd = t.GetRenderData(td)          # None = inherited from parent
        print("  "*d + t.GetName(), t.IsChecked(), cam and cam.GetName(), rd and rd.GetName())
        for ov in t.GetOverrides():                               # BaseOverride per overridden node
            node = ov.GetSceneNode()
            for did in ov.GetAllOverrideDescID():
                print("  "*d, "  ", node.GetName(), did, ov.GetParameter(did, c4d.DESCFLAGS_GET_NONE))
        walk(t.GetDown(), d + 1); t = t.GetNext()
walk(main)
```
- `IsChecked()` = marked for "Render Marked Takes". The Main take can hold overrides too.
- User-data overrides show as DescID `((700, 5, 0), (id, dtype, 0))`.
- Render output tokens, e.g. `...\$prj_$take\$prj_$take_` in `RDATA_PATH`, give each take its own folder.

## Create and edit (verified)
```python
t = td.AddTake("Variant A", main, None)                  # name, parent, clone-from
t.FindOrAddOverrideParam(td, obj, c4d.DescID(c4d.DescLevel(c4d.PRIM_CUBE_LEN, c4d.DTYPE_VECTOR, 0)), c4d.Vector(50))
t.FindOrAddOverrideParam(td, rig, ud_descid, 2)           # user data works the same way
t.SetCamera(td, cam); t.SetRenderData(td, rd)             # rd must be inserted: doc.InsertRenderData(rd, parent, pred)
og = t.AddOverrideGroup(); og.SetName("hide")
og.AddToGroup(td, obj); og.SetEditorMode(c4d.MODE_OFF); og.SetRenderMode(c4d.MODE_OFF)
t.SetChecked(True)
```
- **`FindOrAddOverrideParam` returns None for everything** (even a fresh cube) when the file has the
  Take Manager's **Lock Overrides** on: `td.GetOverrideEnabling()` lacks `c4d.OVERRIDEENABLING_GLOBAL`
  (64; 4031 instead of 4095). `c4d.CallCommand(431000108)` ("Lock Overrides") toggles it — works in
  c4dpy on the active document (`InsertBaseDocument` + `SetActiveDocument`); toggle back before saving
  to keep the owner's setting. Override groups and their tags work even while locked.
- Object visibility (902/901) can't be a parameter override (None) — use override groups. A tag that
  only some takes need: put it on the object with neutral values and override its parameters per take
  (verified with an RS Object tag matte), or `og.AddTag(td, type, None)` on an override group.
- Never call `ov.UpdateSceneNode(...)` while building: it pushes the override value into the scene
  node of the current (Main) take.
- `t.GetEffectiveCamera(td)` / `t.GetEffectiveRenderData(td)` return a tuple `(object, take)` that
  resolves inheritance. Use `[0]`.
- `td.SetCurrentTake(t)` + `ExecutePasses` applies the overrides to the open document. Switching
  back to Main restores the values. The user sees this happen, so restore their current take afterwards.
- Wrap edits in undo. Takes are document data, so don't create or delete takes in a user's scene
  unless asked.
- `AddTake` inserts the new take as the FIRST child, so a loop creates them in reverse order.
  Reorder with `t.Remove(); t.InsertUnderLast(parent)` — camera and render data stay assigned (verified).
- **Render settings: `rd.GetClone()` copies the child render settings too.** Cloning a parent setting
  once per shot to make its children nested each new clone under the previous ones — 12 shots gave
  ~4,000 settings. Clone without children (`GetClone(c4d.COPYFLAGS_NO_HIERARCHY)`, unverified) or
  remove the clone's children before inserting it. Count the tree afterwards.
- Render settings that should render at 30 fps from a 60 fps scene: `rd[5023] = False` (Use Project
  Frame Rate) and `rd[c4d.RDATA_FRAMERATE] = 30`; frame range as `c4d.BaseTime(frame30, 30)`.
- **`$take` in the output path:** works in Commandline. In the Render Queue one scene's take jobs all
  rendered their first frame and failed "Error – Saving Image", nothing written (C4D 2027) — yet in
  another scene `…\$prj\$prj_$take_` and `…\$prj_$take\$prj_$take_` rendered through the queue with
  Team Render and wrote `<prj>_<take>_####.exr` (2027.0, the folders already existed). The queue
  doesn't create folders, so a `$take` *folder* that doesn't exist yet is the likely difference
  (unverified). Safe layout regardless: one parent render setting per shot and
  quality (resolution, samples, range) with one **child per take** (a clone, named after the take,
  explicit path `.../<shot>/<take>/<take>`) — tidy in the list (the user found 23 top-level settings
  far too many), and a child clone keeps its own path (verified). Changing a file's render settings
  after queuing: re-add the jobs (the job keeps the render setting it had when added).
- Output names with a dot in the take/file name (`thr0.05`) are cut at the dot: three variants
  overwrote each other. Keep dots out of names.
- Redshift passes whose materials are unlit (Fresnel/X-ray, self-lit emission): switch GI off
  (`rs_vp[7005] = 0`) — verified pixel-identical; the Unified sampling threshold (`[1103]`) can go
  up to 0.1 for such alpha-only passes without visible change.
- **EXR half float** (C4D 2027): `rd[c4d.RDATA_FORMATDEPTH] = 1` raises "parameter set failed" and a
  container write doesn't stick (files came out 32-bit float). Use the image settings dictionary:
  `d = maxon.DataDictionary(); d.Set(maxon.MEDIASESSION.OPENEXR.EXPORT.HALFFLOAT, True);
  c4d.bitmaps.SetImageSettingsDictionary(d, rd.GetDataInstance().GetContainerInstance(c4d.RDATA_SAVEOPTIONS), c4d.FILTER_EXR)`.
  `RDATA_NAMEFORMAT = c4d.RDATA_NAMEFORMAT_6` writes `name.0000.exr`.

## Replicating a take setup from a reference file (verified C4D 2026.4)
- `td.AddTake(name, parent, None)` inserts the new take as the **first** child. Add them in reverse
  order, or reorder with `td.InsertTake(take, other, c4d.INSERT_BEFORE)`.
- Copy the DescIDs from the reference's overrides (`ov.GetAllOverrideDescID()`) instead of building
  them, so the dtypes match exactly. Mirror the Main take's base-value overrides too.
- Typical "passes" setup: Main overrides the parts' Enabled (906) = on; each child take switches the
  other parts off; Redshift camera **Background (13000)**: 0 Render Settings, 1 Off, 2 Override —
  set to Off in the pass takes so they render on alpha.
- Render settings worth diffing between files (flatten `GetDataInstance()` incl. nested containers):
  5016 frame sequence (1 current, 2 all), 5033 format (`c4d.FILTER_EXR` 1016606, `FILTER_TIF` 1100,
  `FILTER_PNG` 1023671), RDATA_FORMATDEPTH, RDATA_SAVEOPTIONS container (copy it with the format),
  RDATA_PATH, RDATA_MULTIPASS_SAVEIMAGE, and the Redshift video post (2006 = Denoising › Enabled).
  Keep each file's own fps/resolution/film aspect — don't clone render data across files with a
  different frame rate.
- For working undo in several open files, make each one active in its **own** call first
  (`SetActiveDocument`), edit in the next call with `undo=true`, restore the user's active file at the end.
- Verify per take with `TakeToDocument` (enabled flags, camera background), then `KillDocument`.
- `SetTime`/`ExecutePasses` on a document marks it as changed even when nothing was edited — tell
  the user, so an "unsaved changes" flag on a file you only inspected isn't a surprise.

## Edit an existing override (verified)
```python
ov = take.FindOverride(td, obj)                  # None if the take doesn't override obj
for did in ov.GetAllOverrideDescID():
    old = ov.GetParameter(did, c4d.DESCFLAGS_GET_NONE)
    ov.SetParameter(did, new_value, c4d.DESCFLAGS_SET_NONE)
    if take == td.GetCurrentTake(): ov.UpdateSceneNode(td, did)   # push it to the object now
```
- Walk every take, the Main take included: Main also returns overrides (the base values of
  parameters that other takes override).
- Renaming a user data entry (`SetUserDataContainer` with the same DescID) keeps its overrides.
  Removing an entry drops them.
- When a control changes meaning (e.g. a distance becomes a speed), convert the value in every take
  that overrides it, not only the object's current value.
- The user may add takes mid-session. List the takes again right before changing user data.

## Split one long edit camera into shot cameras + takes (verified)
For a scene where one camera plays the whole film (step keys at the cuts) and each shot should get
its own camera, take and render range:
```python
trans = c4d.AliasTrans(); trans.Init(doc)
rig = master_rig.GetClone(c4d.COPYFLAGS_NONE, trans)      # rig = null + camera + focus null
doc.InsertObject(rig, shot_cams_null, prev); trans.Translate(True)   # camera focus link -> the clone's focus null
# keep only the keys that shape this shot: from the last key <= shot start to the first key >= shot end
k0 = max(k for k in keys if k <= a); k1 = min(k for k in keys if k >= b)
for i in range(cv.GetKeyCount() - 1, -1, -1):
    f = cv.GetKey(i).GetTime().GetFrame(fps)
    if f < k0 or f > k1: cv.DelKey(i)
```
- Verify by sampling the track, not the curve: `tr.GetValue(doc, c4d.BaseTime(f, fps), fps)` against
  the master track on every frame of the shot — got 0.0000 difference, spline ease keys included.
- **Handles: don't use the track's Before/After "Continue"** (track params 910 / 911: 0 Off,
  1 Constant, 2 Continue, 3 Repeat, 4 Offset Repeat, 5 Oscillate, 6 Loop). With ease keys (long zero-value
  tangents) or step keys it extrapolated nonsense (z −1,200,000). Set both to Constant (1) and add an
  explicit linear key at each handle end, value = boundary value ± boundary slope × handle length
  (slope from two samples of the master). Set the boundary key to linear first if it was a step key —
  the segment inside the shot is unchanged when the key before it is linear. Hold instead of
  continuing after a crash zoom IN (continuing flies through the subject).
- One take per shot under the take that carries the shared look/visibility overrides, each with its
  camera and a child render setting (shot range + handles, output path per shot). A continuous move
  split into two shots can share one camera.
- Keep the old camera as a renamed reference rig if other takes (stills, a full-length preview) use it.

## Verify or render a take without touching the open scene
```python
x = td.TakeToDocument(t)        # new document with the take's overrides baked in
# step it from frame 0 (simulations), read values, or render it (see cinema4d-render-preview)
c4d.documents.KillDocument(x)
```
- Verified on a particle rig with a Python-tag driver: each take's document (Path 1/2/3 user-data
  override) moved the emitter along the right spline and simulated independently.
- Verified: override groups with render mode OFF show up as object render visibility 1 (off) in
  the take document.
- TakeToDocument is also the clean way to export one take's geometry (e.g. Alembic of a MoGraph
  object with the take's visibility): select the object in the take document, save with
  `FORMAT_ABCEXPORT`, kill the document. A 113-frame, 312k-point export ran ~3 min (longer than the
  60 s bridge wait; poll the file size until it stops growing).
- (unverified) In a test, every take document's *active* render data came back as the last
  inserted RenderData. When rendering a take, pass `t.GetEffectiveRenderData(td)[0]` to RenderDocument explicitly.
- **Commandline renders a take** (verified 2027.0): `Commandline.exe … -render scene.c4d -take v2
  -frame 120 120 -oimage …` — the frame was bit-identical to the take's earlier full render, and
  without `-take` it rendered Main.

## Fold a scene copy into a take, and promote a take to Main (verified 2027.0)
- Fold: open the original, check it differs from the copy only where expected (compare objects'
  `GetMl()` without tracks, points, materials, render setting names, fps/range), copy the copy's new
  user-data entries with **their own IDs** (`SetUserDataContainer(did, bc)` in the copy's order) and
  give them values that keep the old look on Main, then `AddTake` + `FindOrAddOverrideParam` for
  every value that differs, plus a child render setting (clone of the parent, children removed,
  only the path changed) set on the take. Proof: render one frame of Main and of `-take` with
  Commandline and diff against renders made before the fold — both came out max diff 0.0.
- Promote (the old look is no longer needed): for each `ov in t.GetOverrides()`,
  `ov.GetSceneNode().SetParameter(did, ov.GetParameter(did, DESCFLAGS_GET_NONE), DESCFLAGS_SET_NONE)`
  with Main current, copy what the take's render setting changed (here the path) into the parent,
  `td.DeleteTake(t)`, `child.Remove()`. Main then rendered the take's frames exactly.
- Works on a file the user closed without opening a tab: `LoadDocument` → edit → `SaveDocument` to
  its path → `KillDocument` (check first that it isn't open in the GUI).

## Render several takes through the Render Queue — no per-take file copies (verified C4D 2026)
```python
br = c4d.documents.GetBatchRender()
n = br.GetElementCount(); br.AddFile(path, n)
names = []
for i in range(br.GetTakeCount(n)):                       # take index = depth-first order of the take tree, Main = 0
    br.SetActiveTakeIndex(n, i, False); names.append(br.GetActiveTakeName(n))
br.SetActiveTakeIndex(n, names.index("F02_VP"), False)    # this job renders that take
print(br.GetActiveRenderSettingsName(n))                   # -> the take's render settings
# one AddFile per take, same path; then br.SetRendering(c4d.BR_START)
```
- Verified: each job rendered its take's camera, frame range and output path; a shot render matched
  the old full-length render at the same frames (PSNR 45–46 dB, codec noise only).
- Binding quirks, which differed between runs: `GetAllTakeNames(n)` failed once (asked for a 'takeOnly'
  argument, then rejected extra arguments) and worked later (see `cinema4d-mcp`); the `GetActive…`
  getters raise "Required argument 'filename'" when given the job alone, so pass `(n, path)` if the
  recipe above raises. `GetActiveCameraIndex` works but did not line up with `GetAllCameraNames` —
  trust the take, not that index.
- Save the file before adding the jobs; each job loads the file from disk when it starts.

## Working with a rig that has takes
- Rig controls that differ per take (path index, colours, sizes) belong in take overrides on the
  control null's user data, not in duplicated rigs.
- A Python tag driver reads the overridden user data like any value, so no special handling is needed.
- A self-updating dropdown (see cinema4d-rigging) keeps its entries. Overrides store the **index**:
  reordering the children of the path folder changes what each take renders.

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

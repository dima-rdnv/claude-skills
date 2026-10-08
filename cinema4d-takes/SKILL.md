---
name: cinema4d-takes
description: "Cinema 4D Takes through Python/MCP: read a scene's takes and overrides, add takes with parameter/user-data overrides, edit override values, cameras, render settings and override groups, verify each take via TakeToDocument, and render variants. Load with cinema4d-mcp."
---

# Cinema 4D Takes (verified C4D 2026.1)

Takes are a common way to render several variants of one scene (e.g. one take per path of a rig, rendered
with the `$take` token in the output path). **Before changing a scene, list its takes.** A
parameter the user overrides in a take will not follow an edit made in the Main take.

## Read what exists
```python
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

## Create and edit (verified in a blank doc)
```python
t = td.AddTake("Variant A", main, None)                  # name, parent, clone-from
t.FindOrAddOverrideParam(td, obj, c4d.DescID(c4d.DescLevel(c4d.PRIM_CUBE_LEN, c4d.DTYPE_VECTOR, 0)), c4d.Vector(50))
t.FindOrAddOverrideParam(td, rig, ud_descid, 2)           # user data works the same way
t.SetCamera(td, cam); t.SetRenderData(td, rd)             # rd must be inserted: doc.InsertRenderData(rd)
og = t.AddOverrideGroup(); og.SetName("hide")
og.AddToGroup(td, obj); og.SetEditorMode(c4d.MODE_OFF); og.SetRenderMode(c4d.MODE_OFF)
t.SetChecked(True)
```
- `t.GetEffectiveCamera(td)` / `t.GetEffectiveRenderData(td)` return a tuple `(object, take)` that
  resolves inheritance. Use `[0]`.
- `td.SetCurrentTake(t)` + `ExecutePasses` applies the overrides to the open document. Switching
  back to Main restores the values. The user sees this happen, so restore their current take afterwards.
- Wrap edits in undo. Takes are document data, so don't create or delete takes in a user's scene
  unless asked.

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
- (unverified) In a test, every take document's *active* render data came back as the last
  inserted RenderData. When rendering a take, pass `t.GetEffectiveRenderData(td)[0]` to RenderDocument explicitly.

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
5. Re-package every changed skill (keep names) and, if the skills live in a git repo, commit and push.
   Tell the user in one line what changed.
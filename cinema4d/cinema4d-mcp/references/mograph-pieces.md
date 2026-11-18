# Loose pieces of a mesh as MoGraph clones, visibility by fields (verified 2027.0, macOS)

Task: a scene of merged meshes (each holding thousands of loose pieces) should have every piece
driven by fields. Splitting into separate objects under a Cloner means tens of thousands of objects;
the **Fracture object in Explode Segments mode** does the split itself and stays one object per mesh.

- Count the pieces first: union-find over `GetAllPolygons()` point indices (31,715 pieces in 53 meshes,
  ~1M polygons, took 1.5 s inside `exec_python`).
- Wrap each mesh: `fr = c4d.BaseObject(c4d.Omgfracture)` (not `Ofracture`),
  `fr[c4d.MGFRACTUREOBJECT_MODE] = c4d.MGFRACTUREOBJECT_MODE_EXPLODE`, insert it where the mesh was
  (`parent=op.GetUp(), pred=op.GetPred()`), then the mesh under it. Each clone's matrix sits at its
  piece's centre; the pieces keep the mesh's Material and Phong tags (seen in `fr.GetCache()`).
- One Plain effector shared by every Fracture: `ID_MG_BASEEFFECTOR_POSITION_ACTIVE = False`,
  `ID_MG_BASEEFFECTOR_VISIBILITY = True`, a `FieldList` with a `FieldLayer(c4d.FLfield)` linking the
  field object, the effector in each `ID_MG_MOTIONGENERATOR_EFFECTORLIST` (InExcludeData, flag 1).
- **Send `eff.Message(c4d.MSG_MENUPREPARE, doc)` right after `c4d.BaseObject(c4d.Omgplain)`, before
  setting parameters.** Without it the 2027 adapter warns that the effector's field state was never
  initialised and it goes inert after save + load (Render Queue renders a saved copy). With it, a
  saved and reloaded test kept its hidden clones.
- Linear field (`c4d.Flinear`): Direction is param `1005` (0 +X, 1 −X, 2 +Y, 3 −Y …), default **+X**,
  so moving it in Y does nothing until the direction is set. With direction −Y and the effector's
  Visibility on, pieces whose centre is below the field show and pieces above it hide: raising the
  field reveals a stack bottom to top. Each piece flips at the field's plane.
- Check by numbers: after `ExecutePasses`, `mograph.GeGetMoData(fr).GetArray(c4d.MODATA_FLAGS)` and
  count `& c4d.MOGENFLAG_CLONE_ON`, at several field positions; restore the field position after.

## Rebuilt as instances (verified 2027.0, macOS)
Fracture copies geometry per piece. To instance: group pieces by exact shape (key = sorted polygons as
point offsets from the piece's bbox centre on a 0.001 cm grid), one prototype per shape (centred,
Material + Phong tags copied), most-used first. 31,715 pieces → 1,556 prototypes, 800,913 → 45,020
stored polygons. Lines with rounded ends can't be one stretched box: the caps would stretch.
- One Cloner per mesh: Object mode (`MG_POLY_MODE_` = `MG_POLY_MODE_VERTEX`, `MG_OBJECT_ALIGN` off,
  Iterate), Instance Mode param `1025` = 2 (Multi-Instance), `MG_OBJECT_LINK` = a points-only
  `PolygonObject(n, 0)` of piece centres (hidden with `c4d.MODE_OFF`; it still distributes).
- No native per-clone child pick from data, so the cloud carries a vertex map "shape" = (k+0.5)/n and
  one shared Python effector (`c4d.Omgpython`, `OEPYTHON_MODE_FULLCONTROL`, code in `OEPYTHON_STRING`)
  copies it: `md.SetArray(c4d.MODATA_CLONE, gen[c4d.MG_OBJECT_LINK].GetTag(c4d.Tvertexmap).GetAllHighlevelData(), False)`.
  The cloner maps clone value v to child int(v·n). First in the effector list, Visibility after it.
  Verified per clone (positions exact, every prototype right), after save + load, and in the viewport.
- Insert children with `doc.InsertObject(child, parent=cloner, pred=prev)` after the cloner is in the doc.
- 2027 adapter: `exec_python` stops a script past 10M loop iterations (`LoopBudgetExceeded`), leaving
  earlier edits in place — pass `max_iterations` for big geometry jobs and write scripts that can resume.
- Comparing shapes on a rounding grid can flag identical pieces (507 vs 508); measure the point gap.

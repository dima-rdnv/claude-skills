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

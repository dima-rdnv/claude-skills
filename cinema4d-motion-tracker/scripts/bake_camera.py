# Run in Cinema 4D (exec_python, undo=true). Builds a keyed camera + feature nulls from extended.json, scaled by K.
# Clones the tracker's Solved Camera so lens/sensor settings match exactly.
def main():
    import c4d, json
    IN = r"C:\path\to\extended.json"; K = 1.0   # scene scale factor (see SKILL.md "Real-world scale")
    E = json.load(open(IN)); fps = doc.GetFps()
    root = c4d.BaseObject(c4d.Onull); root.SetName("Extended Track (x%.2f)" % K); doc.InsertObject(root); add_undo_create(root)
    cam = doc.SearchObject("Solved Camera").GetClone(c4d.COPYFLAGS_NONE); cam.SetName("Extended Camera")
    for t in cam.GetTags():
        if t.GetType() == 5629: t.Remove()          # Protection tag
    for tr in cam.GetCTracks(): tr.Remove()
    doc.InsertObject(cam, parent=root)
    curves = []
    for pid in (c4d.ID_BASEOBJECT_REL_POSITION, c4d.ID_BASEOBJECT_REL_ROTATION):
        for a in (c4d.VECTOR_X, c4d.VECTOR_Y, c4d.VECTOR_Z):
            tr = c4d.CTrack(cam, c4d.DescID(c4d.DescLevel(pid, c4d.DTYPE_VECTOR, 0), c4d.DescLevel(a, c4d.DTYPE_REAL, 0)))
            cam.InsertTrackSorted(tr); curves.append(tr.GetCurve())
    prev = None
    for f in sorted(int(x) for x in E["cam"]):
        v = E["cam"][str(f)]
        m = c4d.Matrix(c4d.Vector(*v[0:3]) * K, c4d.Vector(*v[3:6]), c4d.Vector(*v[6:9]), c4d.Vector(*v[9:12]))
        hpb = c4d.utils.MatrixToHPB(m, c4d.ROTATIONORDER_DEFAULT)
        if prev is not None: hpb = c4d.utils.GetOptimalAngle(prev, hpb, c4d.ROTATIONORDER_DEFAULT)   # no 360-degree flips
        prev = hpb
        for cv, val in zip(curves, [m.off.x, m.off.y, m.off.z, hpb.x, hpb.y, hpb.z]):
            k = cv.AddKey(c4d.BaseTime(f, fps))["key"]; k.SetValue(cv, val); k.SetInterpolation(cv, c4d.CINTERPOLATION_LINEAR)
    feats = c4d.BaseObject(c4d.Onull); feats.SetName("Features"); doc.InsertObject(feats, parent=root, pred=cam); prevn = None
    for name in sorted(E["feat"]):
        p = c4d.Vector(*E["feat"][name])
        if p.GetLength() > 5000: continue           # far outliers
        n = c4d.BaseObject(c4d.Onull); n.SetName(name); n[c4d.NULLOBJECT_DISPLAY] = c4d.NULLOBJECT_DISPLAY_POINT
        n.SetAbsPos(p * K); doc.InsertObject(n, parent=feats, pred=prevn); prevn = n
    c4d.EventAdd()
main()

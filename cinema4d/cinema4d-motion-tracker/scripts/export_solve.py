# Run in Cinema 4D (exec_python). Exports the Motion Tracker solve + all 2D tracks for extend_solve.py.
# Edit OUT. Camera rows: [pos xyz, v1 xyz, v2 xyz, v3 xyz, focal mm, aperture mm] in world space.
def main():
    import c4d, json
    OUT = r"C:\path\to\solves.json"
    fps = doc.GetFps(); cam = doc.SearchObject("Solved Camera"); mt = doc.SearchObject("Motion Tracker")
    keys = cam.GetCTracks()[0].GetCurve(); f0 = keys.GetKey(0).GetTime().GetFrame(fps); f1 = keys.GetKey(keys.GetKeyCount() - 1).GetTime().GetFrame(fps)
    A = {"cam": {}, "feat": {}}; t0 = doc.GetTime()
    for f in range(f0, f1 + 1):
        doc.SetTime(c4d.BaseTime(f, fps)); doc.ExecutePasses(None, True, True, True, c4d.BUILDFLAGS_NONE)
        m = cam.GetMg()
        A["cam"][f] = [m.off.x, m.off.y, m.off.z, m.v1.x, m.v1.y, m.v1.z, m.v2.x, m.v2.y, m.v2.z, m.v3.x, m.v3.y, m.v3.z,
                       cam[c4d.CAMERAOBJECT_FOCUS], cam[c4d.CAMERAOBJECT_APERTURE]]
    doc.SetTime(t0); doc.ExecutePasses(None, True, True, True, c4d.BUILDFLAGS_NONE)
    c = doc.SearchObject("Auto Features").GetDown()
    while c: p = c.GetMg().off; A["feat"][c.GetName()] = [p.x, p.y, p.z]; c = c.GetNext()
    td = mt.Get2dTrackData(); fd = mt.GetFootageData(); last = int(mt[10510]); tr2d = {}
    for i in range(td.GetTrackCount()):
        tr = td.GetTrackByIndex(i); bs = tr.GetFramesWithTrackData(); pts = {}
        for f in range(0, last + 1):
            if bs.IsSelected(f):
                p = tr.GetDataForFrame(f).GetPixelPosition(fd, True); pts[f] = [round(p.x, 2), round(p.y, 2)]
        if pts: tr2d[tr.GetName()] = pts
    json.dump({"A": A, "tracks": tr2d, "res": [fd.GetResolutionWidthPix(True), fd.GetResolutionHeightPix(True)]}, open(OUT, "w"))
    print("cams %d-%d, features %d, 2D tracks %d" % (f0, f1, len(A["feat"]), len(tr2d)))
main()

"""Which objects does each camera see over the timeline? (headless c4dpy)

Usage: c4dpy g_licenseModel=LICENSEMODEL::MAXONAPP <abs path>/c4d_camera_visibility.py scene.c4d out.json \
           "Rig/CAM_A,Rig/CAM_B" "Group/ObjA,Group/ObjB" [frame_step=10] < /dev/null
For every object: size in its own axes, centre, visibility flags, and per camera the number of sampled
frames in which part of it is on screen, the max screen coverage (fraction of the frame its visible
points span) and the closest distance. Pinhole projection with C4D film offsets (X + shifts the view
right, Y + down); resolution per camera from the take using it, else the active render data.
Instance objects use the linked object's geometry at the instance's matrix.
Not checked pixel-for-pixel against renders — treat coverage as an estimate.
Verified to run on C4D 2027.0 (Windows). See ../references/scene-inventory-and-asset-extraction.md.
"""
import sys, json, c4d

src, outp = sys.argv[1], sys.argv[2]
cam_paths, obj_paths = sys.argv[3].split(","), sys.argv[4].split(",")
step = int(sys.argv[5]) if len(sys.argv) > 5 else 10
doc = c4d.documents.LoadDocument(src, c4d.SCENEFILTER_OBJECTS | c4d.SCENEFILTER_MATERIALS, None)
fps = doc.GetFps()


def walk(op):
    while op:
        yield op
        yield from walk(op.GetDown())
        op = op.GetNext()


def find(path):
    op, f = doc.GetFirstObject(), None
    for n in path.split("/"):
        while op and op.GetName() != n:
            op = op.GetNext()
        if not op:
            return None
        f, op = op, op.GetDown()
    return f


def local_bbox(root):
    inv, mn, mx = ~root.GetMg(), c4d.Vector(1e30), c4d.Vector(-1e30)
    for o in [root] + list(walk(root.GetDown())):
        if o.CheckType(c4d.Opolygon) and o.GetPointCount():
            m, pts = inv * o.GetMg(), o.GetAllPoints()
            for p in pts[::max(1, len(pts) // 4000)]:
                w = m * p
                mn = c4d.Vector(min(mn.x, w.x), min(mn.y, w.y), min(mn.z, w.z))
                mx = c4d.Vector(max(mx.x, w.x), max(mx.y, w.y), max(mx.z, w.z))
    return mn, mx


items = {}
for p in obj_paths:
    o = find(p)
    if o is None:
        print("not found:", p); continue
    geo = o[c4d.INSTANCEOBJECT_LINK] if o.GetType() == c4d.Oinstance else o
    items[p] = (o, *local_bbox(geo))

td, camres = doc.GetTakeData(), {}


def tw(t):
    while t:
        cam, rd = t.GetCamera(td), t.GetRenderData(td)
        if cam and rd:
            camres[cam.GetName()] = (rd[c4d.RDATA_XRES], rd[c4d.RDATA_YRES])
        tw(t.GetDown()); t = t.GetNext()


tw(td.GetMainTake())
ard = doc.GetActiveRenderData()
cams = [find(c) for c in cam_paths]
res = {}
for k, (o, mn, mx) in items.items():
    s, c = mx - mn, o.GetMg() * ((mn + mx) * 0.5)
    res[k] = {"size_cm": [round(s.x, 1), round(s.y, 1), round(s.z, 1)], "centre": [round(c.x), round(c.y), round(c.z)],
              "vis": [o[c4d.ID_BASEOBJECT_VISIBILITY_EDITOR], o[c4d.ID_BASEOBJECT_VISIBILITY_RENDER]], "cams": {}}
grid = [(i / 4, j / 4, k / 4) for i in range(5) for j in range(5) for k in range(5)]
for f in range(doc.GetMinTime().GetFrame(fps), doc.GetMaxTime().GetFrame(fps) + 1, step):
    doc.SetTime(c4d.BaseTime(f, fps)); doc.ExecutePasses(None, True, True, False, c4d.BUILDFLAGS_NONE)
    for cam in cams:
        A, F = cam[c4d.CAMERAOBJECT_APERTURE], cam[c4d.CAMERA_FOCUS]
        ox, oy = cam[c4d.CAMERAOBJECT_FILM_OFFSET_X], cam[c4d.CAMERAOBJECT_FILM_OFFSET_Y]
        xr, yr = camres.get(cam.GetName(), (ard[c4d.RDATA_XRES], ard[c4d.RDATA_YRES]))
        Av, inv = A * yr / xr, ~cam.GetMg()
        for k, (o, mn, mx) in items.items():
            if res[k]["vis"][1] == 1:  # render visibility off
                continue
            mg, us, vs, zmin = o.GetMg(), [], [], 1e30
            for (a, b, cc) in grid:
                q = inv * (mg * c4d.Vector(mn.x + (mx.x - mn.x) * a, mn.y + (mx.y - mn.y) * b, mn.z + (mx.z - mn.z) * cc))
                if q.z <= 1:
                    continue
                u, v = 0.5 + (F * q.x / q.z) / A - ox, 0.5 - (F * q.y / q.z) / Av - oy
                if 0 <= u <= 1 and 0 <= v <= 1:
                    us.append(u); vs.append(v); zmin = min(zmin, q.z)
            if us:
                d = res[k]["cams"].setdefault(cam.GetName(), {"frames": 0, "max_cov": 0, "min_dist_cm": 1e9, "first": f, "last": f})
                d["frames"] += 1; d["last"] = f
                d["max_cov"] = max(d["max_cov"], round((max(us) - min(us)) * (max(vs) - min(vs)), 3))
                d["min_dist_cm"] = min(d["min_dist_cm"], round(zmin))
json.dump({"camres": camres, "items": res}, open(outp, "w"), indent=1)
print("done", len(items), "objects,", len(cams), "cameras")

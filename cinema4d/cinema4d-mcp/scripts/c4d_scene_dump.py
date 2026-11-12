"""Dump a Cinema 4D scene's objects, materials, assets, cameras and takes to JSON (headless c4dpy).

Usage: c4dpy g_licenseModel=LICENSEMODEL::MAXONAPP <abs path>/c4d_scene_dump.py scene.c4d out.json < /dev/null
Read-only: the scene is loaded into memory and never saved. Verified C4D 2027.0 (Windows).
"""
import sys, json, c4d

src, outp = sys.argv[1], sys.argv[2]
doc = c4d.documents.LoadDocument(src, c4d.SCENEFILTER_OBJECTS | c4d.SCENEFILTER_MATERIALS, None)
if doc is None:
    raise SystemExit("LoadDocument returned None: " + src)


def path_of(o):
    p = []
    while o:
        p.append(o.GetName()); o = o.GetUp()
    return "/".join(reversed(p))


def walk(op, depth=0):
    while op:
        yield op, depth
        yield from walk(op.GetDown(), depth + 1)
        op = op.GetNext()


rows = []
for o, dep in walk(doc.GetFirstObject()):
    r = {"path": path_of(o), "depth": dep, "type": o.GetTypeName(), "tid": o.GetType(),
         "vis_ed": o[c4d.ID_BASEOBJECT_VISIBILITY_EDITOR], "vis_rd": o[c4d.ID_BASEOBJECT_VISIBILITY_RENDER]}
    if o.CheckType(c4d.Opolygon):
        r["polys"] = o.GetPolygonCount()
    mats = [t.GetMaterial().GetName() for t in o.GetTags() if t.CheckType(c4d.Ttexture) and t.GetMaterial()]
    if mats:
        r["mats"] = mats
    lay = o.GetLayerObject(doc)
    if lay:
        r["layer"] = lay.GetName()
    if o.GetType() == c4d.Oinstance:
        link = o[c4d.INSTANCEOBJECT_LINK]
        r["inst_of"] = path_of(link) if link else None
    if o.GetType() == 1038649:  # Redshift Proxy
        try:
            r["proxy_file"] = o[c4d.REDSHIFT_PROXY_FILE, c4d.REDSHIFT_FILE_PATH]
        except Exception as e:  # noqa: BLE001
            r["proxy_file"] = repr(e)
    m = o.GetMg()
    r["pos"] = [round(m.off.x, 1), round(m.off.y, 1), round(m.off.z, 1)]
    rows.append(r)

assets = []
c4d.documents.GetAllAssetsNew(doc, False, "", c4d.ASSETDATA_FLAG_NONE, assets)
layers, lo = [], (doc.GetLayerObjectRoot().GetDown() if doc.GetLayerObjectRoot() else None)
while lo:
    layers.append(lo.GetName()); lo = lo.GetNext()
td, takes = doc.GetTakeData(), []


def take_walk(t, d=0):
    while t:
        cam = t.GetCamera(td)
        takes.append(("  " * d) + t.GetName() + (f"  cam={path_of(cam)}" if cam else ""))
        take_walk(t.GetDown(), d + 1)
        t = t.GetNext()


take_walk(td.GetMainTake() if td else None)
fps = doc.GetFps()
json.dump({"objects": rows,
           "materials": [{"name": m.GetName(), "type": m.GetTypeName()} for m in doc.GetMaterials()],
           "assets": [{"file": a.get("filename"), "owner": a.get("assetname"), "exists": a.get("exists")} for a in assets],
           "layers": layers,
           "cameras": [path_of(o) for o, _ in walk(doc.GetFirstObject()) if o.GetType() in (c4d.Ocamera, 1057516)],
           "takes": takes, "fps": fps,
           "min": doc.GetMinTime().GetFrame(fps), "max": doc.GetMaxTime().GetFrame(fps)},
          open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print("objects", len(rows), "materials", len(doc.GetMaterials()), "assets", len(assets))

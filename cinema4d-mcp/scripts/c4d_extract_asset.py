"""Cut one model out of a Cinema 4D scene into a clean file with its textures (headless c4dpy).

Usage: c4dpy g_licenseModel=LICENSEMODEL::MAXONAPP <abs path>/c4d_extract_asset.py \
           src.c4d out_dir name.c4d "Top/Child/Object" ["Other/Object" ...] < /dev/null
- keeps only the named objects (paths from the root, '/'-separated), moved to the root with the pose
  they had relative to their old parent (a turntable null's rotation is dropped), animation removed;
- removes every other object, unused materials and all video posts (a missing LUT in a Redshift
  post-effect made SaveProject fail), centres the result on the floor at the origin;
- SaveProject with assets (file textures copied to out_dir/tex; Asset Browser asset:/// textures stay
  library references), then reopens the saved file and prints every texture reference.
Verified C4D 2027.0 (Windows). See ../references/scene-inventory-and-asset-extraction.md.
"""
import sys, os, c4d

src, out_dir, out_name, keep_paths = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]


def walk(op):
    while op:
        yield op
        yield from walk(op.GetDown())
        op = op.GetNext()


def find_path(doc, path):
    op, found = doc.GetFirstObject(), None
    for name in path.split("/"):
        while op and op.GetName() != name:
            op = op.GetNext()
        if not op:
            return None
        found, op = op, op.GetDown()
    return found


doc = c4d.documents.LoadDocument(src, c4d.SCENEFILTER_OBJECTS | c4d.SCENEFILTER_MATERIALS, None)
if doc is None:
    raise SystemExit("LoadDocument returned None: " + src)
keep = []
for kp in keep_paths:
    o = find_path(doc, kp)
    if o is None:
        raise SystemExit("object not found: " + kp)
    keep.append((o, o.GetMg() if not o.GetUp() else o.GetMl()))
for o, _ in keep:
    o.Remove(); doc.InsertObject(o)
for o, m in keep:
    o.SetMg(m)
    for x in [o] + list(walk(o.GetDown())):
        for tr in list(x.GetCTracks()):
            tr.Remove()
op = doc.GetFirstObject()
while op:  # compare with ==, never `is` (wrappers differ for the same object)
    nxt = op.GetNext()
    if not any(op == o for o, _ in keep):
        op.Remove()
    op = nxt

doc.ExecutePasses(None, False, False, True, c4d.BUILDFLAGS_NONE)
mn, mx, npoly = c4d.Vector(1e30), c4d.Vector(-1e30), 0
for x in walk(doc.GetFirstObject()):
    if x.CheckType(c4d.Opolygon) and x.GetPointCount():
        mg, pts = x.GetMg(), x.GetAllPoints(); npoly += x.GetPolygonCount()
        for p in pts[::max(1, len(pts) // 50000)]:
            w = mg * p
            mn = c4d.Vector(min(mn.x, w.x), min(mn.y, w.y), min(mn.z, w.z))
            mx = c4d.Vector(max(mx.x, w.x), max(mx.y, w.y), max(mx.z, w.z))
shift = c4d.Vector(-(mn.x + mx.x) / 2, -mn.y, -(mn.z + mx.z) / 2)
for o, _ in keep:
    m = o.GetMg(); m.off = m.off + shift; o.SetMg(m)

used = {t.GetMaterial().GetName() for x in walk(doc.GetFirstObject()) for t in x.GetTags()
        if t.CheckType(c4d.Ttexture) and t.GetMaterial()}
for m in list(doc.GetMaterials()):
    if m.GetName() not in used:
        m.Remove()
rd = doc.GetFirstRenderData()
while rd:
    vp = rd.GetFirstVideoPost()
    while vp:
        nx = vp.GetNext(); vp.Remove(); vp = nx
    rd = rd.GetNext()

os.makedirs(out_dir, exist_ok=True)
doc.SetDocumentName(out_name)  # keep the source path: relative textures (name only, found via the
# source's tex/ folder) are resolved against it — setting the new path first made them "missing"
assets, missing = [], []
ok = c4d.documents.SaveProject(doc, c4d.SAVEPROJECT_ASSETS | c4d.SAVEPROJECT_SCENEFILE
                               | c4d.SAVEPROJECT_USEDOCUMENTNAMEASFILENAME | c4d.SAVEPROJECT_DONTFAILONMISSINGASSETS,
                               out_dir, assets, missing)
size = mx - mn
print(f"{out_name}: SaveProject={ok} polys={npoly:,} size(cm)={size.x:.1f} x {size.y:.1f} x {size.z:.1f} "
      f"materials={sorted(used)} missing={len(missing)}")
for a in missing:
    print("   MISSING:", a)
c4d.documents.KillDocument(doc)

saved = os.path.join(out_dir, out_name)
d = c4d.documents.LoadDocument(saved, c4d.SCENEFILTER_OBJECTS | c4d.SCENEFILTER_MATERIALS, None)
a = []
c4d.documents.GetAllAssetsNew(d, False, "", c4d.ASSETDATA_FLAG_TEXTURESONLY, a)
print(f"VERIFY {out_name}: {len(d.GetMaterials())} materials, {len(a)} textures")
for x in a:
    print(f"    exists={x.get('exists')} -> {x.get('filename')}")

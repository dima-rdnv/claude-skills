"""KLT feature tracks over a whole clip at full resolution, forward-backward checked.
usage: track_klt.py clip.mp4 out.npz
Out: arrays tid, frame, x, y (one row per observation) + vignette mask stats."""
import sys, numpy as np, cv2
OUT = sys.argv[2]
lut = (255 * (np.arange(256) / 255.0) ** 0.5).astype(np.uint8)          # lift the dark grade
def read_all():
    cap = cv2.VideoCapture(sys.argv[1])
    while True:
        ok, im = cap.read()
        if not ok: return
        yield cv2.LUT(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), lut)
acc = None; n = 0; N = 0
for i, g in enumerate(read_all()):
    N += 1
    if i >= 30 and i % 10 == 0: acc = g.astype(np.float32) if acc is None else acc + g; n += 1
H, W = g.shape
print("frames", N, W, H)
# vignette: screen-fixed dark border -> mask where the clip is dark on average (after the fade-in)
mean = acc / n
vmask = (cv2.GaussianBlur(mean, (0, 0), 25) > 40).astype(np.uint8) * 255
vmask = cv2.erode(vmask, np.ones((61, 61), np.uint8))
print("usable area %.0f%%" % (100 * (vmask > 0).mean()))
lk = dict(winSize=(25, 25), maxLevel=4, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 40, 0.01))
rows = []; nid = 0
pts = np.zeros((0, 2), np.float32); ids = np.zeros(0, int)
prev = None
for f, g in enumerate(read_all()):
    if f > 0 and len(pts):
        p1, st, _ = cv2.calcOpticalFlowPyrLK(prev, g, pts, None, **lk)
        p0, st2, _ = cv2.calcOpticalFlowPyrLK(g, prev, p1, None, **lk)
        fb = np.linalg.norm(p0 - pts, axis=1)
        xi, yi = np.clip(p1[:, 0].astype(int), 0, W - 1), np.clip(p1[:, 1].astype(int), 0, H - 1)
        keep = (st[:, 0] == 1) & (st2[:, 0] == 1) & (fb < 0.6) & (vmask[yi, xi] > 0)
        pts, ids = p1[keep], ids[keep]
    # re-seed in empty areas
    m = vmask.copy()
    for x, y in pts: cv2.circle(m, (int(x), int(y)), 14, 0, -1)
    if f < N - 1 and g.mean() > 3:
        new = cv2.goodFeaturesToTrack(g, maxCorners=max(0, 2500 - len(pts)), qualityLevel=0.004, minDistance=14, blockSize=7, mask=m)
        if new is not None:
            new = cv2.cornerSubPix(g, new.astype(np.float32), (5, 5), (-1, -1), (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.03))
            pts = np.vstack([pts, new[:, 0]]); ids = np.concatenate([ids, np.arange(nid, nid + len(new))]); nid += len(new)
    for i, (x, y) in zip(ids, pts): rows.append((i, f, x, y))
    prev = g
    if f % 50 == 0: print("f%d alive %d" % (f, len(pts)), flush=True)
R = np.array(rows)
tid, fr = R[:, 0].astype(int), R[:, 1].astype(int)
cnt = np.bincount(tid); keep = cnt[tid] >= 5
np.savez_compressed(OUT, tid=tid[keep], frame=fr[keep], x=R[keep, 2], y=R[keep, 3], vmask=vmask, W=W, H=H)
print("observations %d, tracks %d (len>=5)" % (keep.sum(), len(np.unique(tid[keep]))))

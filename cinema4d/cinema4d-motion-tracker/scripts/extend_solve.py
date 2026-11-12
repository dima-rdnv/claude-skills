"""Extend a C4D Motion Tracker camera solve past the point where the solver gave up.

Usage: uv run --with numpy --with scipy --with opencv-python-headless python -I extend_solve.py solves.json extended.json [END_A]
  solves.json  written by export_solve.py (run in C4D)   END_A = last frame of the original solve to trust

Input  : solves.json exported from C4D  (A = original solve: cams + 3D features, tracks = 2D pixel tracks)
Output : extended.json  (camera per frame in C4D world space + 3D points)

C4D conventions: camera matrix columns v1 (right), v2 (up), v3 (forward), left-handed world.
Projection that matches the tracker: q = (P - c) @ [v1 v2 v3];  u = W/2 + f*qx/qz,  v = H/2 - f*qy/qz.
OpenCV wants a right-handed world, so world points are mirrored with S = diag(1,1,-1).
"""
import json, sys
import numpy as np, cv2
from scipy.optimize import least_squares

D = json.load(open(sys.argv[1]))
W, H = D["res"]
S = np.diag([1.0, 1.0, -1.0]); Fy = np.diag([1.0, -1.0, 1.0])
A = D["A"]
k0 = sorted(A["cam"], key=int)[len(A["cam"]) // 2]
fl, ap = A["cam"][k0][12], A["cam"][k0][13]
fpx = fl / ap * W
K = np.array([[fpx, 0, W / 2], [0, fpx, H / 2], [0, 0, 1.0]])
END_A = int(sys.argv[3]) if len(sys.argv) > 3 else max(int(f) for f in A["cam"])
LAST = max(int(f) for t in D["tracks"].values() for f in t)

def c4d_to_cv(v):
    c = np.array(v[0:3]); R = np.stack([v[3:6], v[6:9], v[9:12]], 1); R = R / np.linalg.norm(R, axis=0)
    Rcv = Fy @ R.T @ S
    return Rcv, -Fy @ R.T @ c

def cv_to_c4d(Rcv, t):
    C = -Rcv.T @ t
    R = S @ Rcv.T @ Fy
    return S @ C, R

tracks = {n: {int(f): np.array(p) for f, p in d.items()} for n, d in D["tracks"].items()}
poses = {}
for f, v in A["cam"].items():
    f = int(f)
    if f <= END_A: poses[f] = c4d_to_cv(v)
pts = {n: S @ np.array(p) for n, p in A["feat"].items()}

def project(Rcv, t, X):
    x = (Rcv @ np.atleast_2d(X).T).T + t
    return (K @ x.T).T[:, :2] / x[:, 2:3], x[:, 2]

def reproj_err(n, X, frames=None):
    e = []
    for f, uv in tracks.get(n, {}).items():
        if f in poses and (frames is None or f in frames):
            p, z = project(*poses[f], X)
            if z[0] <= 0: return 1e9
            e.append(np.hypot(*(p[0] - uv)))
    return np.median(e) if e else 1e9

# drop A points that don't reproject well (outliers, points on moving things)
bad = [n for n, X in pts.items() if reproj_err(n, X) > 15]
for n in bad: pts.pop(n)
print("A points kept %d, dropped %d" % (len(pts), len(bad)))

def triangulate(n, frames):
    obs = [(f, tracks[n][f]) for f in sorted(tracks[n]) if f in poses and f in frames]
    if len(obs) < 6: return None
    # parallax check between first and last ray
    rows = []
    for f, (u, v) in obs:
        P = K @ np.hstack([poses[f][0], poses[f][1][:, None]])
        rows += [u * P[2] - P[0], v * P[2] - P[1]]
    _, _, Vt = np.linalg.svd(np.array(rows)); X = Vt[-1]; X = X[:3] / X[3]
    c0 = -poses[obs[0][0]][0].T @ poses[obs[0][0]][1]; c1 = -poses[obs[-1][0]][0].T @ poses[obs[-1][0]][1]
    a = X - c0; b = X - c1
    ang = np.degrees(np.arccos(np.clip(a @ b / np.linalg.norm(a) / np.linalg.norm(b), -1, 1)))
    if ang < 0.7: return None
    if reproj_err(n, X, set(f for f, _ in obs)) > 2.5: return None
    return X

log = []
for f in range(END_A + 1, LAST + 1):
    # 1. add new points triangulated from the last ~25 posed frames
    recent = set(g for g in poses if g >= f - 25)
    for n in tracks:
        if n in pts: continue
        X = triangulate(n, recent)
        if X is not None: pts[n] = X
    # 2. resection
    names = [n for n in pts if f in tracks.get(n, {})]
    if len(names) < 6:
        print("frame %d: only %d known points - stopping" % (f, len(names))); break
    obj = np.array([pts[n] for n in names]); img = np.array([tracks[n][f] for n in names])
    Rp, tp = poses[f - 1]; rv0, _ = cv2.Rodrigues(Rp)
    ok, rv, tv, inl = cv2.solvePnPRansac(obj, img, K, None, rvec=rv0.copy(), tvec=tp.copy().reshape(3, 1),
                                        useExtrinsicGuess=True, reprojectionError=4.0, iterationsCount=500,
                                        flags=cv2.SOLVEPNP_ITERATIVE)
    if not ok or inl is None or len(inl) < 6:
        print("frame %d: PnP failed (%s inliers of %d)" % (f, None if inl is None else len(inl), len(names))); break
    inl = inl[:, 0]
    rv, tv = cv2.solvePnPRefineLM(obj[inl], img[inl], K, None, rv, tv)
    poses[f] = (cv2.Rodrigues(rv)[0], tv[:, 0])
    p, _ = project(*poses[f], obj[inl])
    log.append((f, len(names), len(inl), float(np.median(np.hypot(*(p - img[inl]).T)))))

print("resection:", " ".join("%d:%d/%d %.1fpx" % l for l in log[::4]))

# 3. bundle adjustment over the tail: frames > BA0 free, earlier frames fixed (keeps A's gauge and scale)
BA0 = END_A - 15
free = sorted(f for f in poses if f > BA0)
pnames = [n for n in pts if sum(1 for g in tracks[n] if g in poses and g > BA0 - 10) >= 4]
obs = [(free.index(g) if g in free else -1, g, i, tracks[n][g]) for i, n in enumerate(pnames) for g in tracks[n] if g in poses and g > BA0 - 10]
x0 = np.concatenate([np.concatenate([cv2.Rodrigues(poses[g][0])[0][:, 0], poses[g][1]]) for g in free] + [pts[n] for n in pnames])
nc = len(free)
ci = np.array([o[0] for o in obs]); fi = np.array([o[1] for o in obs]); pi = np.array([o[2] for o in obs]); uv = np.array([o[3] for o in obs])
fixedR = {g: poses[g] for g in poses if g <= BA0}
Rfix = np.array([fixedR[g][0] if c < 0 else np.eye(3) for c, g in zip(ci, fi)])
tfix = np.array([fixedR[g][1] if c < 0 else np.zeros(3) for c, g in zip(ci, fi)])
isfree = ci >= 0; cic = np.where(isfree, ci, 0)

def rod(rv):
    th = np.linalg.norm(rv, axis=1, keepdims=True) + 1e-12; k = rv / th
    Kx = np.zeros((len(rv), 3, 3))
    Kx[:, 0, 1], Kx[:, 0, 2], Kx[:, 1, 0], Kx[:, 1, 2], Kx[:, 2, 0], Kx[:, 2, 1] = -k[:, 2], k[:, 1], k[:, 2], -k[:, 0], -k[:, 1], k[:, 0]
    s_, c_ = np.sin(th)[:, :, None], np.cos(th)[:, :, None]
    return np.eye(3)[None] + s_ * Kx + (1 - c_) * (Kx @ Kx)

def resid(x):
    cams = x[:nc * 6].reshape(nc, 6); P = x[nc * 6:].reshape(-1, 3)
    Rf = rod(cams[:, :3])
    R = np.where(isfree[:, None, None], Rf[cic], Rfix); t = np.where(isfree[:, None], cams[cic, 3:], tfix)
    xc = np.einsum("nij,nj->ni", R, P[pi]) + t
    out = K[0, 0] * xc[:, :2] / xc[:, 2:3] + K[:2, 2] - uv
    acc = cams[2:] - 2 * cams[1:-1] + cams[:-2]
    return np.concatenate([out.ravel(), 20.0 * acc[:, 3:].ravel(), 200.0 * acc[:, :3].ravel()])

from scipy.sparse import lil_matrix
nobs = len(obs); nacc = max(nc - 2, 0)
Jsp = lil_matrix((2 * nobs + 6 * nacc, nc * 6 + 3 * len(pnames)), dtype=int)
for k in range(nobs):
    for r in (2 * k, 2 * k + 1):
        if ci[k] >= 0: Jsp[r, ci[k] * 6:ci[k] * 6 + 6] = 1
        Jsp[r, nc * 6 + pi[k] * 3:nc * 6 + pi[k] * 3 + 3] = 1
for j in range(nacc):
    for d in range(3):
        rT = 2 * nobs + 3 * j + d; rR = 2 * nobs + 3 * nacc + 3 * j + d
        for c in (j, j + 1, j + 2):
            Jsp[rT, c * 6 + 3 + d] = 1; Jsp[rR, c * 6 + d] = 1

r0 = resid(x0)
sol = least_squares(resid, x0, jac_sparsity=Jsp, loss="huber", f_scale=2.0, max_nfev=80, x_scale="jac", method="trf")
cams = sol.x[:nc * 6].reshape(nc, 6)
for i, g in enumerate(free): poses[g] = (cv2.Rodrigues(cams[i, :3])[0], cams[i, 3:])
P = sol.x[nc * 6:].reshape(-1, 3)
for i, n in enumerate(pnames): pts[n] = P[i]
print("BA: %d cams, %d points, %d obs, median |r| %.2f -> %.2f px" % (nc, len(pnames), len(obs),
      np.median(np.abs(r0[:2 * len(obs)])), np.median(np.abs(sol.fun[:2 * len(obs)]))))

# 4. per-frame reprojection report
rep = {}
for f in sorted(poses):
    e = []
    for n, X in pts.items():
        if f in tracks.get(n, {}):
            p, z = project(*poses[f], X)
            if z[0] > 0: e.append(np.hypot(*(p[0] - tracks[n][f])))
    rep[f] = (len(e), float(np.median(e)) if e else None)
print("reproj (n, median px):", " ".join("%d:%d/%.1f" % (f, rep[f][0], rep[f][1] or -1) for f in sorted(rep) if f % 6 == 0 or f > END_A and f % 3 == 0))

out = {"cam": {}, "feat": {}}
for f in sorted(poses):
    c, R = cv_to_c4d(*poses[f]); out["cam"][f] = [*c, *R[:, 0], *R[:, 1], *R[:, 2], fl, ap]
for n, X in pts.items(): out["feat"][n] = (S @ X).tolist()
json.dump(out, open(sys.argv[2], "w"))
print("written frames %d..%d, %d points" % (min(poses), max(poses), len(pts)))

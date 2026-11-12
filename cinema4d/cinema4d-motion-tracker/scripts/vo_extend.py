"""Extend a trusted camera solve frame by frame (forward or backward) with sliding-window bundle adjustment.
usage: vo_extend.py solves.json klt.npz out.json DIR START STOP [options]
  solves.json from export_solve.py, klt.npz from track_klt.py
  DIR +1/-1; START = first frame to solve; STOP = last frame to solve (inclusive)
  --seed A0 A1        trusted poses = solve A frames in [A0, A1] (default: all of A)
  --init x.json ...   earlier outputs of this script, also trusted (chain segments)
  --person p.npz      3D points on a person (key P, cv world) - tracks near their projection are never used
  --mask m.npz        per-frame keep masks: frames, masks (HxW uint8), scale (full-res px per mask px)
  --tri-px / --min-par / --min-obs / --pnp-px / --min-inl / --win   triangulation, PnP and window settings
  --model-from F      past frame F, new points take depth from nearby known points instead of triangulation
                      (tried for a small far object; did not fix the solve there - see SKILL.md)
Works in OpenCV camera space (x right, y down, z forward); world = C4D world mirrored in z."""
import sys, json, argparse, numpy as np, cv2
from scipy.optimize import least_squares
from scipy.sparse import lil_matrix
ap_ = argparse.ArgumentParser()
ap_.add_argument("solves"); ap_.add_argument("klt"); ap_.add_argument("out"); ap_.add_argument("dir", type=int)
ap_.add_argument("start", type=int); ap_.add_argument("stop", type=int)
ap_.add_argument("--seed", type=int, nargs=2); ap_.add_argument("--mask"); ap_.add_argument("--win", type=int, default=30)
ap_.add_argument("--pnp-px", type=float, default=3.0); ap_.add_argument("--min-par", type=float, default=1.0)
ap_.add_argument("--focal-free", action="store_true"); ap_.add_argument("--min-obs", type=int, default=6); ap_.add_argument("--person"); ap_.add_argument("--init", nargs="*", default=[]); ap_.add_argument("--min-inl", type=int, default=8); ap_.add_argument("--tri-px", type=float, default=2.0); ap_.add_argument("--model-from", type=int); ap_.add_argument("--person-r", type=float, default=45)
a = ap_.parse_args()
D = json.load(open(a.solves)); W, H = D["res"]; A = D["A"]
S = np.diag([1.0, 1.0, -1.0]); Fy = np.diag([1.0, -1.0, 1.0])
k0 = sorted(A["cam"], key=int)[len(A["cam"]) // 2]; FL, AP = A["cam"][k0][12], A["cam"][k0][13]
FPX = FL / AP * W; CX, CY = W / 2, H / 2
def Kf(fp): return np.array([[fp, 0, CX], [0, fp, CY], [0, 0, 1.0]])
def c4d_to_cv(v):
    c = np.array(v[0:3]); R = np.stack([v[3:6], v[6:9], v[9:12]], 1); R = R / np.linalg.norm(R, axis=0)
    Rcv = Fy @ R.T @ S; return Rcv, -Rcv @ (S @ c)
def cv_to_c4d(Rcv, t):
    C = -Rcv.T @ t; R = S @ Rcv.T @ Fy; return S @ C, R
# ---- tracks
Z = np.load(a.klt); tid, fr, X, Y = Z["tid"], Z["frame"], Z["x"], Z["y"]
o = np.lexsort((fr, tid)); tid, fr, X, Y = tid[o], fr[o], X[o], Y[o]
if a.mask:   # per-frame keep masks (car only etc.): masks.npz with 'frames' and 'polys' or bitmaps
    M = np.load(a.mask, allow_pickle=True); sc = float(M["scale"])
    keep = np.ones(len(tid), bool)
    for f, m in zip(M["frames"], M["masks"]):
        sel = np.flatnonzero(fr == f)
        yi = np.clip((Y[sel] / sc).astype(int), 0, m.shape[0] - 1); xi = np.clip((X[sel] / sc).astype(int), 0, m.shape[1] - 1)
        keep[sel] = m[yi, xi] > 0
    tid, fr, X, Y = tid[keep], fr[keep], X[keep], Y[keep]
starts = np.r_[0, np.flatnonzero(np.diff(tid)) + 1]; ends = np.r_[starts[1:], len(tid)]
TR = {int(tid[s]): (fr[s:e], np.c_[X[s:e], Y[s:e]]) for s, e in zip(starts, ends)}
byframe = {}
for t, (fs, xy) in TR.items():
    for f, p in zip(fs, xy): byframe.setdefault(int(f), {})[t] = p
# ---- trusted poses
A0, A1 = a.seed if a.seed else (min(map(int, A["cam"])), max(map(int, A["cam"])))
poses = {int(f): c4d_to_cv(v) for f, v in A["cam"].items() if A0 <= int(f) <= A1}
focal = {f: FPX for f in poses}
for fn in a.init:      # earlier extensions, trusted like A
    for f, v in json.load(open(fn))["cam"].items():
        if int(f) not in poses: poses[int(f)] = c4d_to_cv(v); focal[int(f)] = v[12] / v[13] * W
trusted = set(poses)
pts = {}; born = {}
from scipy.spatial import cKDTree
PERS = np.load(a.person)["P"] if a.person else None      # already cv world (tri_trusted.py)
ptree = {}; banned = set()
def person_tree(f):
    if f not in ptree:
        R, t = poses[f]; q = PERS @ R.T + t; q = q[q[:, 2] > 1]
        ptree[f] = cKDTree(q[:, :2] / q[:, 2:3] * focal[f] + [CX, CY]) if len(q) else None
    return ptree[f]
def is_person(t, f):
    if PERS is None: return False
    if t in banned: return True
    T_ = person_tree(f); p = byframe.get(f, {}).get(t)
    if T_ is None or p is None: return False
    if T_.query(p)[0] < a.person_r: banned.add(t); return True
    return False
def proj(R, t, fp, P):
    x = P @ R.T + t; return x[:, :2] / x[:, 2:3] * fp + [CX, CY], x[:, 2]
def triangulate(t, frames):
    fs, xy = TR[t]; sel = [i for i, f in enumerate(fs) if int(f) in frames]
    if len(sel) < a.min_obs: return None
    rows = []
    for i in sel:
        f = int(fs[i]); R, tt = poses[f]; P = Kf(focal[f]) @ np.hstack([R, tt[:, None]]); u, v = xy[i]
        rows += [u * P[2] - P[0], v * P[2] - P[1]]
    _, _, Vt = np.linalg.svd(np.array(rows)); Xh = Vt[-1]
    if abs(Xh[3]) < 1e-12: return None
    P3 = Xh[:3] / Xh[3]
    e = []; cs = []
    for i in sel:
        f = int(fs[i]); R, tt = poses[f]; p, z = proj(R, tt, focal[f], P3[None])
        if z[0] <= 0: return None
        e.append(np.hypot(*(p[0] - xy[i]))); cs.append(-R.T @ tt)
    if np.median(e) > a.tri_px or np.max(e) > 3 * a.tri_px: return None
    v0, v1 = P3 - cs[0], P3 - cs[-1]
    ang = np.degrees(np.arccos(np.clip(v0 @ v1 / np.linalg.norm(v0) / np.linalg.norm(v1), -1, 1)))
    return P3 if ang >= a.min_par else None
def recent(f):
    return set(g for g in poses if abs(g - f) <= a.win)
def model_points(f):
    """new points get depth from nearby known points (frozen model) instead of triangulation"""
    R, t = poses[f]; fp = focal[f]; known = [k for k in pts]
    if len(known) < 4: return 0
    Q = np.array([pts[k] for k in known]) @ R.T + t; ok = Q[:, 2] > 0; Q = Q[ok]
    uv = Q[:, :2] / Q[:, 2:3] * fp + [CX, CY]; T_ = cKDTree(uv); n = 0
    for k, p in byframe.get(f, {}).items():
        if k in pts or is_person(k, f): continue
        d, i = T_.query(p, k=6, distance_upper_bound=max(40.0, 0.06 * np.ptp(uv[:, 0])))
        i = i[np.isfinite(d)]
        if len(i) < 4: continue
        z = np.median(Q[i, 2]); ray = np.array([(p[0] - CX) / fp, (p[1] - CY) / fp, 1.0]) * z
        pts[k] = R.T @ (ray - t); born[k] = f; n += 1
    return n
def add_points(f):
    if a.model_from is not None and (f - a.model_from) * a.dir > 0: return model_points(f)
    win = recent(f); n = 0
    for t in byframe.get(f, {}):
        if t in pts or is_person(t, f): continue
        P3 = triangulate(t, win)
        if P3 is not None: pts[t] = P3; born[t] = f; n += 1
    return n
def window_ba(f, nfix=10):
    win = sorted(recent(f), key=lambda g: abs(g - f))      # nearest first
    free = [g for g in win[:max(0, len(win) - nfix)] if g not in trusted]
    fixed = [g for g in win if g not in free]
    pn = [t for t in pts if sum(1 for g in TR[t][0] if int(g) in win) >= 3]
    obs = []
    for j, t in enumerate(pn):
        for g, p in zip(*TR[t]):
            g = int(g)
            if g in win: obs.append((free.index(g) if g in free else -1, g, j, p))
    if not free or not obs: return None
    nc = len(free); ci = np.array([q[0] for q in obs]); gi = np.array([q[1] for q in obs]); pj = np.array([q[2] for q in obs]); uv = np.array([q[3] for q in obs])
    Rfix = np.array([poses[g][0] for g in gi]); tfix = np.array([poses[g][1] for g in gi]); ffix = np.array([focal[g] for g in gi])
    isf = ci >= 0; cic = np.where(isf, ci, 0)
    order = sorted(free); oi = [free.index(g) for g in order]       # time order for smoothness
    x0 = np.concatenate([np.concatenate([cv2.Rodrigues(poses[g][0])[0][:, 0], poses[g][1]]) for g in free] + [pts[t] for t in pn])
    nf = 1 if a.focal_free else 0
    if nf: x0 = np.concatenate([x0, [np.mean([focal[g] for g in free]) / FPX]])
    def rod(rv):
        th = np.linalg.norm(rv, axis=1, keepdims=True) + 1e-12; k = rv / th; Kx = np.zeros((len(rv), 3, 3))
        Kx[:, 0, 1], Kx[:, 0, 2], Kx[:, 1, 0], Kx[:, 1, 2], Kx[:, 2, 0], Kx[:, 2, 1] = -k[:, 2], k[:, 1], k[:, 2], -k[:, 0], -k[:, 1], k[:, 0]
        s_, c_ = np.sin(th)[:, :, None], np.cos(th)[:, :, None]; return np.eye(3)[None] + s_ * Kx + (1 - c_) * (Kx @ Kx)
    npn = len(pn)
    def resid(x):
        cams = x[:nc * 6].reshape(nc, 6); P = x[nc * 6:nc * 6 + 3 * npn].reshape(-1, 3)
        fp = x[-1] * FPX if nf else FPX
        R = np.where(isf[:, None, None], rod(cams[:, :3])[cic], Rfix); t = np.where(isf[:, None], cams[cic, 3:], tfix)
        F = np.where(isf, fp, ffix)
        xc = np.einsum("nij,nj->ni", R, P[pj]) + t
        r = (F[:, None] * xc[:, :2] / xc[:, 2:3] + [CX, CY] - uv).ravel()
        cs = cams[oi]
        acc = cs[2:] - 2 * cs[1:-1] + cs[:-2] if len(cs) > 2 else np.zeros((0, 6))
        return np.concatenate([r, 20.0 * acc[:, 3:].ravel(), 200.0 * acc[:, :3].ravel()])
    nacc = max(nc - 2, 0); nobs = len(obs)
    J = lil_matrix((2 * nobs + 6 * nacc, len(x0)), dtype=int)
    for k in range(nobs):
        for r in (2 * k, 2 * k + 1):
            if ci[k] >= 0: J[r, ci[k] * 6:ci[k] * 6 + 6] = 1
            J[r, nc * 6 + pj[k] * 3:nc * 6 + pj[k] * 3 + 3] = 1
            if nf and ci[k] >= 0: J[r, len(x0) - 1] = 1
    for j in range(nacc):
        for d in range(3):
            for c in (oi[j], oi[j + 1], oi[j + 2]):
                J[2 * nobs + 3 * j + d, c * 6 + 3 + d] = 1; J[2 * nobs + 3 * nacc + 3 * j + d, c * 6 + d] = 1
    r0 = resid(x0)
    sol = least_squares(resid, x0, jac_sparsity=J, loss="huber", f_scale=2.0, max_nfev=40, x_scale="jac", method="trf")
    cams = sol.x[:nc * 6].reshape(nc, 6)
    fp = sol.x[-1] * FPX if nf else FPX
    for i, g in enumerate(free): poses[g] = (cv2.Rodrigues(cams[i, :3])[0], cams[i, 3:]); focal[g] = fp
    P = sol.x[nc * 6:nc * 6 + 3 * npn].reshape(-1, 3)
    res = np.hypot(*sol.fun[:2 * nobs].reshape(-1, 2).T)
    pres = np.zeros(npn); np.maximum.at(pres, pj, res)
    for j, t in enumerate(pn):
        if pres[j] > 8: pts.pop(t, None)          # drop points that stopped fitting (morphing / sliding)
        else: pts[t] = P[j]
    return np.median(np.abs(r0[:2 * nobs])), np.median(np.abs(sol.fun[:2 * nobs])), fp
# ---- seed points from the trusted range nearest the start
add_points(a.start - a.dir)
print("seed points", len(pts))
log = []
f = a.start
while (f - a.stop) * a.dir <= 0:
    prev = f - a.dir
    names = [t for t in byframe.get(f, {}) if t in pts]
    names = [t for t in names if t not in banned]
    if len(names) < a.min_inl: print("frame %d: only %d known points - stop" % (f, len(names))); break
    obj = np.array([pts[t] for t in names]); img = np.array([byframe[f][t] for t in names])
    Rp, tp = poses[prev]; fp = focal[prev]
    ok, rv, tv, inl = cv2.solvePnPRansac(obj, img, Kf(fp), None, rvec=cv2.Rodrigues(Rp)[0], tvec=tp.reshape(3, 1).copy(),
                                        useExtrinsicGuess=True, reprojectionError=a.pnp_px, iterationsCount=1000, flags=cv2.SOLVEPNP_ITERATIVE)
    if not ok or inl is None or len(inl) < a.min_inl: print("frame %d: PnP failed (%s of %d)" % (f, None if inl is None else len(inl), len(names))); break
    inl = inl[:, 0]; rv, tv = cv2.solvePnPRefineLM(obj[inl], img[inl], Kf(fp), None, rv, tv)
    poses[f] = (cv2.Rodrigues(rv)[0], tv[:, 0]); focal[f] = fp
    p, _ = proj(*poses[f], fp, obj[inl]); e = float(np.median(np.hypot(*(p - img[inl]).T)))
    for t in set(names) - set(np.array(names)[inl]):     # outliers at this frame: forget their 3D
        if born.get(t) is not None and abs(born[t] - f) > a.win: pts.pop(t, None)
    nn = add_points(f)
    in_model = a.model_from is not None and (f - a.model_from) * a.dir > 0
    ba = window_ba(f) if (f - a.start) % 5 == 4 and not in_model else None
    log.append((f, len(names), len(inl), e, nn, ba))
    f += a.dir
ba = window_ba(f - a.dir) if a.model_from is None else None
for l in log[::3]:
    print("f%d pts %d inl %d %.2fpx new %d%s" % (l[0], l[1], l[2], l[3], l[4], "" if l[5] is None else " | BA %.2f->%.2f f %.0f" % l[5]))
# ---- report: reprojection of current points per frame
rep = {}
for g in sorted(poses):
    d = byframe.get(g, {}); ns = [t for t in d if t in pts]
    if not ns: continue
    p, z = proj(*poses[g], focal[g], np.array([pts[t] for t in ns])); e = np.hypot(*(p - np.array([d[t] for t in ns])).T)
    rep[g] = (len(ns), float(np.median(e[z > 0])))
out = {"cam": {}, "rep": rep, "feat": {}}
for g in sorted(poses):
    c, R = cv_to_c4d(*poses[g]); out["cam"][g] = [*c, *R[:, 0], *R[:, 1], *R[:, 2], focal[g] / W * AP, AP]
for t, P3 in pts.items(): out["feat"][int(t)] = (S @ P3).tolist()
json.dump(out, open(a.out, "w"))
sel = [g for g in sorted(rep) if (g - a.start) * a.dir >= -12]
print("reproj:", " ".join("%d:%d/%.1f" % (g, rep[g][0], rep[g][1]) for g in sel[::3]))

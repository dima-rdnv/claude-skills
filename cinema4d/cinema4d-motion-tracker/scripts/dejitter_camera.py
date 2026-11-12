"""De-jitter a tracked camera: Gaussian-smooth position AND rotation (quaternions) with the SAME sigma,
tapered to no smoothing at the first/last frames. Optionally reports CG jitter vs footage jitter.

usage: dejitter_camera.py cam.json sigma out.json [solves.json features.json K]
  cam.json: {frame: [pos xyz, v1 xyz, v2 xyz, v3 xyz, focal, aperture]} (world space, as keyed in C4D)
  solves.json / features.json / K: from export_solve.py / extend_solve.py, to print the jitter report
"""
import json, sys, numpy as np
from scipy.spatial.transform import Rotation as Rot

C = json.load(open(sys.argv[1])); sigma = float(sys.argv[2]); OUT = sys.argv[3]
fr = sorted(int(f) for f in C); nf = len(fr)
c0 = np.array([C[str(f)][0:3] for f in fr])
R0 = np.array([np.stack([C[str(f)][3:6], C[str(f)][6:9], C[str(f)][9:12]], 1) for f in fr]); R0 /= np.linalg.norm(R0, axis=1, keepdims=True)
q0 = Rot.from_matrix(R0).as_quat()
for i in range(1, nf):
    if q0[i] @ q0[i - 1] < 0: q0[i] = -q0[i]          # keep quaternions on one hemisphere
d = np.minimum(np.arange(nf), nf - 1 - np.arange(nf)).astype(float)
sig = sigma * np.clip(d / (2.5 * sigma), 0, 1)          # taper: a truncated window would drag the ends
c1 = c0.copy(); q1 = q0.copy()
for i in range(nf):
    if sig[i] < 0.05: continue
    k = np.arange(max(0, i - int(4 * sig[i]) - 1), min(nf, i + int(4 * sig[i]) + 2))
    w = np.exp(-0.5 * ((k - i) / sig[i]) ** 2); w /= w.sum()
    c1[i] = w @ c0[k]; q1[i] = w @ q0[k]
q1 /= np.linalg.norm(q1, axis=1, keepdims=True); R1 = Rot.from_quat(q1).as_matrix()
json.dump({f: [*c1[i], *R1[i][:, 0], *R1[i][:, 1], *R1[i][:, 2], *C[str(f)][12:14]] for i, f in enumerate(fr)}, open(OUT, "w"))

if len(sys.argv) > 6:
    D = json.load(open(sys.argv[4])); F = json.load(open(sys.argv[5]))["feat"]; K = float(sys.argv[6])
    W, H = D["res"]; fpx = C[str(fr[0])][12] / C[str(fr[0])][13] * W; fidx = {f: i for i, f in enumerate(fr)}
    def proj(c, R, i, X):
        q = (X - c[i]) @ R[i]; return np.array([W / 2 + fpx * q[0] / q[2], H / 2 - fpx * q[1] / q[2]]), q[2]
    for label, c, R in (("before", c0, R0), ("after", c1, R1)):
        jit, foot, err = [], [], []
        for n, p in F.items():
            X = np.array(p) * K; t = {int(f): np.array(uv) for f, uv in D["tracks"].get(n, {}).items() if int(f) in fidx}
            P = {}
            for f in t:
                uv, z = proj(c, R, fidx[f], X)
                if z > 0: P[f] = uv; err.append(np.hypot(*(uv - t[f])))
            for f in P:
                if f - 1 in P and f + 1 in P:
                    jit.append(np.hypot(*(P[f - 1] - 2 * P[f] + P[f + 1]))); foot.append(np.hypot(*(t[f - 1] - 2 * t[f] + t[f + 1])))
        print("%-6s match median %.2f px | CG jitter median %.2f px/f2 (footage tracks %.2f)" % (label, np.median(err), np.median(jit), np.median(foot)))

# Signature, sampler and pattern search (ExtendScript ES3, numpy side)

Prepend the library to every script you send (the bridge runs one file per call). No backslashes, no
regex literals, `NL = String.fromCharCode(10)` for newlines inside expression text.

## Sampler comp (ExtendScript)
```js
var NL = String.fromCharCode(10);
var TIMES = [1.0, 3.0, 5.0];                 // times of the measured comp to sample
function ensureSampler(srcId) {              // srcId = comp to measure (a duplicate, reference layer off)
  var p = app.project, rd = null, i;
  for (i = 1; i <= p.numItems; i++) if (p.item(i) instanceof CompItem && p.item(i).name === "zz_samp") rd = p.item(i);
  if (rd) { try { rd.remove(); } catch (e) {} }
  rd = p.items.addComp("zz_samp", 1200, 800, 1, 1, 30);
  var lay = rd.layers.add(p.itemByID(srcId)); lay.name = "src";
  var t = rd.layers.addText("x"); t.name = "readout";
  var tp = t.property("ADBE Text Properties").property("ADBE Text Document");
  tp.expression = [
    'var L = thisComp.layer("src"); var TS = [' + TIMES.join(",") + ']; var NX = 24, NY = 16, W = 1200, H = 800, out = [];',
    'for (var k = 0; k < TS.length; k++) { for (var j = 0; j < NY; j++) { for (var i = 0; i < NX; i++) {',
    '  var v = L.sampleImage([(i + 0.5) * W / NX, (j + 0.5) * H / NY], [W / NX / 2, H / NY / 2], true, TS[k]);',
    '  out.push(v[0].toFixed(4) + "," + v[1].toFixed(4) + "," + v[2].toFixed(4)); } } }',
    'out.join(";")'].join(NL);
  return tp;
}
function readSamples(tp) {                   // -> array of [r,g,b], time-major then row-major
  var parts = tp.valueAtTime(0, false).text.split(";"), a = [], i;
  for (i = 0; i < parts.length; i++) { var q = parts[i].split(","); a.push([parseFloat(q[0]), parseFloat(q[1]), parseFloat(q[2])]); }
  return a;
}
```
The measured comps here were 1200 x 800 and the sampler comp the same size; `sampleImage` points are in
the layer's own pixel space, so set W and H to the measured comp's size if it differs.

## Signature and cost (same maths in numpy for the reference frames)
```js
function pctile(sorted, p) { var n = sorted.length, pos = p / 100 * (n - 1), lo = Math.floor(pos), fr = pos - lo; return lo + 1 < n ? sorted[lo] * (1 - fr) + sorted[lo + 1] * fr : sorted[lo]; }
function signature(g) {
  var keepY = [], bands = [[0, 0.30], [0.30, 0.65], [0.65, 1.01]], acc = [[0,0,0],[0,0,0],[0,0,0]], satSum = 0, kept = 0, i, k;
  for (i = 0; i < g.length; i++) {
    var r = g[i][0], gg = g[i][1], b = g[i][2], y = 0.2126 * r + 0.7152 * gg + 0.0722 * b;
    var mx = Math.max(r, gg, b), mn = Math.min(r, gg, b), sat = (mx - mn) / Math.max(mx, 0.0001);
    if (sat >= 0.30) continue;               // drop strongly coloured blocks (product cap, label colour)
    kept++; satSum += sat; keepY.push(y);
    for (k = 0; k < 3; k++) if (y >= bands[k][0] && y < bands[k][1]) { acc[k][0] += r - gg; acc[k][1] += b - gg; acc[k][2]++; }
  }
  keepY.sort(function (a, b) { return a - b; });
  var pct = [], P = [3, 10, 25, 50, 75, 90, 97], tint = [];
  for (i = 0; i < P.length; i++) pct.push(pctile(keepY, P[i]));
  for (k = 0; k < 3; k++) tint.push(acc[k][2] > 0 ? [acc[k][0] / acc[k][2], acc[k][1] / acc[k][2], acc[k][2]] : [0, 0, 0]);
  return { pct: pct, tint: tint, sat: kept ? satSum / kept : 0, kept: kept };
}
var PW = [2, 1, 0.25, 0.25, 1, 1.5, 2];
// REF = { pct:[7], dark:[rg,bg], mid:[rg,bg], bright:[rg,bg], sat } pooled over the reference frames
function cost(s) {
  var c = 0, i, names = ["dark", "mid", "bright"];
  for (i = 0; i < 7; i++) { var e = (s.pct[i] - REF.pct[i]) / 0.03; c += PW[i] * e * e; }
  for (i = 0; i < 3; i++) {
    if (s.tint[i][2] < 5) { c += 5; continue; }
    var e1 = (s.tint[i][0] - REF[names[i]][0]) / 0.015, e2 = (s.tint[i][1] - REF[names[i]][1]) / 0.015; c += e1 * e1 + e2 * e2;
  }
  var es = (s.sat - REF.sat) / 0.04; return c + es * es;
}
```
numpy side: decode the reference with ffmpeg to PNG frames, load as float / 255, resize to the sampler
size, `img.reshape(NY, h // NY, NX, w // NX, 3).mean((1, 3))` for the block means, then the same
percentile / band / saturation logic (`np.percentile`). Print the signature of the *ungraded* comp and
of the reference side by side first: it tells which sliders matter before any search.

## Pattern search (one bridge call, ~200 s)
```js
// P = [{name, id, fx:"L"|"C", v, step, minStep, min, max, pen, n}] ; pen = penalty weight, n = neutral value
function setAll(vals) { for (var i = 0; i < P.length; i++) P[i].prop.setValue(vals[i]); }
function pen(vals) { var c = 0; for (var i = 0; i < P.length; i++) { var d = vals[i] - P[i].n; c += P[i].pen * d * d; } return c; }
var cache = {}, evals = 0;
function evalVals(vals) { var key = vals.join("|"); if (cache[key] !== undefined) return cache[key];
  setAll(vals); var c = cost(signature(readSamples(tp))) + pen(vals); evals++; cache[key] = c; return c; }
// loop: while improved and time left: for each parameter j, for dir in [+1, -1]: trial = cur with
// clamp(cur[j] + dir * step_j); if cost < best - 0.01 keep it and keep walking the same way (max 6 more);
// when a whole round improves nothing, halve every step above its minStep.
```
Fetch `P[i].prop` **after** adding Color Balance (the references die on `addProperty` / `moveTo`):
`(P[i].fx === "L" ? lum : cb).property(P[i].id)`.
Start steps that worked: Temperature / Tint / Saturation / Vibrance 2, Exposure 0.05, Lumetri tone
sliders 2.5, Color Balance 3 (minimum step = about 1/4 of that after the halvings). Penalties
(weight x deviation^2 from neutral): 0.002 on Lumetri sliders, 1.5 on Exposure (its range is +-3),
0.003 on Color Balance values. Bounds: sliders +-100, Saturation 0-200 (neutral 100), Exposure +-3.

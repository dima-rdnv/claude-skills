# Looping 3D spiral flythrough (verified AE 26.5, 1920 x 1920, 30 fps, 15 s, 128 picture layers)

Pictures spawn dark in the depth, follow spiral arms, grow with real perspective and leave past the edge of the
frame; upright (no rotation), looping with no intro or outro. Controls: number of arms, pictures per arm, focal
length, twist, radius, picture size, speed, fade-in, jitter, shuffle, background colour.

## Controller sliders (Slider Control effects on a null named `CONTROLLER`)
| Name | Default | Meaning |
|---|---|---|
| Paths | 11 | spiral arms, clamped 1-16 |
| Pics Per Path | 4 | pictures on every arm, clamped 1-8 |
| Laps | 1 | integer; trips along the whole path per comp duration (negative = backwards) |
| Offset | 0 | % shift of the cycle |
| Twist | -120 | degrees an arm turns from far to near (negative = counter-clockwise outward) |
| Stagger | 100 | % of one spacing that neighbouring arms are shifted |
| Radius | 400 | world radius of the helix |
| Pic Size | 150 | world size of the longest picture side |
| Far Distance | 7500 | depth where the paths start (world px) |
| Focal Length | 35 | mm, 36 mm film width |
| Fade In | 35 | % of the path used to fade from the background colour |
| Jitter | 0 | % random radius variation |
| Shuffle | 7 | which picture sits on which slot |
| Sources | 77 | number of different pictures |
| Background | black | Colour Control; also drives the BG fill and the fog Fill |

## Camera
`comp.layers.addCamera("CAMERA", [w/2, h/2])`, position `[w/2, h/2, 0]`, point of interest `[w/2, h/2, 1000]`.
Zoom expression: `thisComp.layer("CONTROLLER").effect("Focal Length")("Slider") / 36 * thisComp.width`.

## Per-picture effects (names matter, expressions read them)
`Slot`, `Arm`, `U` (Slider Control, expression-driven), `Fog Fill` (Fill, colour = controller Background),
`Fog Composite` (CC Composite, Opacity expression). The layer is 3D with orientation 0.

```
// Slot  (name "PIC 001 | ...")
var C = thisComp.layer("CONTROLLER");
var NU = Math.max(1, Math.round(C.effect("Sources")("Slider")));
var k = parseInt(thisLayer.name.substring(4, 7), 10) - 1;
function gcd(a, b) { return b == 0 ? a : gcd(b, a % b); }
var slot = k;
if (k < NU) { var st = 1 + Math.max(0, Math.round(C.effect("Shuffle")("Slider"))); while (gcd(st, NU) != 1) { st++; } slot = (k * st) % NU; }
slot

// Arm
... P = clamp(round(Paths), 1, 16);  effect("Slot")("Slider") % P

// U  (progress 0 far .. 1 near)
... P, M = clamp(round(Pics Per Path), 1, 8);
var slot = effect("Slot")("Slider"), arm = slot % P, j = Math.floor(slot / P);
var ph = (j + C.effect("Stagger")("Slider") / 100 * arm / P) / M;
var u = ph + C.effect("Offset")("Slider") / 100 + Math.round(C.effect("Laps")("Slider")) * time / thisComp.duration;
u - Math.floor(u)

// Position
... R0 = Radius, Wp = Pic Size, dFar = Far Distance, Z = Focal Length / 36 * thisComp.width, tw = Twist
var u = effect("U")("Slider"), slot = effect("Slot")("Slider"), arm = effect("Arm")("Slider");
seedRandom(slot * 17 + 3, true);
var R = R0 * (1 + C.effect("Jitter")("Slider") / 100 * random(-1, 1));
var hd = Math.sqrt(thisComp.width * thisComp.width + thisComp.height * thisComp.height) / 2;
var rExit = hd / (1 - Math.min(0.9, 0.7071 * Wp / R));
var dNear = Math.min(dFar, R * Z / rExit);
var d = dFar * Math.pow(dNear / dFar, u);
var th = degreesToRadians(arm * 360 / P + tw * u);
[thisComp.width / 2 + R * Math.cos(th), thisComp.height / 2 + R * Math.sin(th), d]

// Scale        s = 100 * PicSize / Math.max(thisLayer.width, thisLayer.height); [s, s, s]
// Opacity      effect("Slot")("Slider") < P * M ? 100 : 0
// CC Composite Opacity (visibility, see SKILL.md)
var f = Math.max(0.001, C.effect("Fade In")("Slider") / 100);
var t = Math.min(1, Math.max(0, effect("U")("Slider") / f));
100 * t * t * (3 - 2 * t)
```

## Why these numbers
- Defaults reproduce a reference sketch of arms leaving the centre with pictures about 0.4 of their radius in
  size: `Pic Size / Radius` is the ratio; above about 0.55 neighbouring arms touch.
- Start radius on screen is `R * Z / dFar` (about 100 px at 35 mm), so pictures begin tiny and fully fogged.
- Perspective strength is set by `dFar` / `dNear`; a longer lens starts larger and grows less.
- Dense default (11 arms x 5, size 220) looked like a carpet; 11 x 4 at size 150 shows the swirl.

## Build order that worked (each a bridge script)
1. Backup copy of the comp in `_old`, set duration, CONTROLLER, camera, guide, BG fill expression.
2. Configure all existing picture layers in place (name prefix first, then `threeDLayer = true`, then effects
   and expressions; 77 layers in under 3 s).
3. `duplicate()` configured layers up to the capacity (51 more), rename `PIC 078 ...`.
4. Error scan, loop check, `toComp` check, preview frames at 0 / 3 / 7.5 / 11 s, save.

## Improvements worth offering
Depth of field with the focus distance following the mid depth, motion blur, per-picture size variety,
a Direction toggle (negative Laps), a custom arm shape (draw a path and read `pointOnPath`) for non-spiral
flows, a second controller for colour grade, Essential Properties to drive it from a parent comp.

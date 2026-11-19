# Thin film, fake diffraction, mesh lights, fog and bloom (verified C4D 2027.0 + RS, macOS, Nov 2026)

Learned on an iridescent silicon-wafer asset (300 mm wafer at 1 mm = 10 cm, dies as Multi-Instance clones, die
surface from greyscale data maps) and a night "light pillars over a grid" lighting setup. Checked by Commandline
renders unless marked otherwise.

## Data textures
- Texture Sampler on data maps (masks, indices): `tex0.colorspace` = `maxon.String("RS_INPUT_COLORSPACE_RAW")`
  (other strings in the plugin: `RS_INPUT_COLORSPACE_SRGB`, `RS_INPUT_COLORSPACE_SRGB_LINEAR`). Without it an 8-bit
  PNG is read as sRGB and a 0.5 index comes out ~0.21.
- `tex0.path` = `maxon.Url("relative:///tex/name.png")` resolved to `<doc folder>/tex/name.png`; `GetAllAssetsNew`
  reported `exists: True`. A document saved one folder higher still found its `tex` files (asset search found them).
- One greyscale map per channel + `rscolorsplitter.outr` → `rsmathrange` (index → physical value) is easy to tune.

## Thin-film interference (iridescent oxide stacks)
- Ports on the Standard Material: `thinfilm_thickness` (nm), `thinfilm_ior`.
- Over a METAL base (`metalness` 1, grey 0.62) the colours came out pale pink/beige. Over a dark DIELECTRIC base
  (`base_color` ~0.012, `metalness` 0, `refl_ior` 3.9, like oxide on silicon) they were vivid. 80–380 nm with film IOR
  1.46 is the first-order range (tan, violet, blue, gold, magenta). Drive the thickness from a map, and put metal (pads)
  on `metalness` with thickness × (1 − metal mask).
- A wafer-level thickness drift from MoGraph colour: Plain effector (custom colour black, spherical field) on a
  Multi-Instance cloner, read in the material with `rsuserdatacolor` attribute `RSMGColor` (default white =
  no drift). Visible as centre-to-rim hue change in a top render.
- An edge-bead rainbow ring at a disc's rim: `state.uvwcoord` − (0.5, 0.5) → `rsmathlengthvector` → `rsmathrange`
  (r from 0.975 R to R → 0 … 450 nm, clamp on) → `thinfilm_thickness` on a planar-UV disc. 900 nm gave too many thin
  fringes; 450 gave a few broad bands.

## Fake diffraction (rainbow that sweeps with the view angle)
Gratings send spectral colours to the camera depending on angle; a reflection tint does it convincingly:
- `state.raydirection` → `rsvectortoscalars` (`outx`, `outz`) → `rsmathmix` by an orientation map (line direction
  per block: grating vector world X or Z) → `rsmathmul` × frequency (from a period map, 1.5–5 cycles per unit) →
  `rsmathadd` small per-block offset (0.35 × another map; a big offset gives confetti instead of a sweep) →
  `rsmathfrac` → `rsvectormaker` (x = hue, y = saturation, z = value) → `rshsv2color` → `rscolormix` (white → rainbow
  by a diffraction-strength map × 0.95) → `refl_color`. The vector→colour connection is accepted.
- Brightness pulse (blocks light up only near their order): second phase → `rsmathmul` π → `rsmathcos`
  (`isradians` True) → range −1..1 → 0..1 → square (`rsmathmul` x·x) → range to 0.15..1 → the HSV value.
- Thin film × (1 − 0.75 · diffraction strength) avoids muddy olive/brown (thin-film colour × rainbow tint).
- Diffraction "glow" without a bright mirror direction: the same rainbow into the base colour
  (`rscolormix` dark → rainbow by strength × 0.4). Without it, a low grazing view reflecting a dark studio stayed grey.
- Grating material for small parts (alignment marks): metal base, rainbow from `raydirection.x` (or z) × 12 into
  `refl_color`.

## Macro depth of field at an inflated scene scale
- At 1 mm = 10 cm a 36 mm sensor behaves like a camera 100× bigger: f/2.8 barely blurs. Scale the RS Camera's sensor
  `[7002]` and focal `[500]` by the same factor k; framing stays, DOF gets real (∝ (distance/focal)²).
- **RS Camera clamps:** focal max 10000 mm, sensor max 2000 mm per side (36×24 × 100 became 2000×2000, which broke
  the framing). k = 55 fits (1980 × 1320, 5500 mm for a 100 mm lens); compensate with f-number ÷ (100/55)² ≈ ÷3.3.
- At very high magnification (~3.6:1) a real DOF blurs everything; keep a normal sensor there.

## Lights
- RS Light `[10000]` type enum: 0 Infinite, 1 Point, 2 Spot, 3 Area, 4 Dome, 5 IES, 6 Portal, 7 Sun.
  Area shape `[11010]`: 0 Rectangle, 1 Disc, 2 Sphere, 3 Cylinder, **4 Mesh** with `[11011]` = the mesh object.
  Units `[11005]` 0 Image, 1 lm, 2 nits, 3 W, 4 radiance, 5 cd, 6 lux. Spread `[11023]`, normalize `[11014]`.
  Ray contributions: camera `[10042]`, reflection `[10034]`, transmission `[10035]`; volume `[10007]` (multiplier),
  volume samples `[10008]`.
- Mesh lights were set up on hidden (render visibility off) ribbon meshes and on a Python Generator's output
  (unverified whether a generator link emits: not isolated in a render).
- Spot: cone `[11019]`, falloff `[11020]` (radians), falloff curve `[11021]`. A spot 95 m above a 30 m scene in
  0.04/m fog: intensity 1.3e7 (Image units) gave a bright, soft column; 4e7 blew the column and the fog out. Cone 2°
  with an 8° falloff reads as a narrow core with a big soft halo.
- Enable/disable lights (also per take): `ID_BASEOBJECT_GENERATOR_FLAG` (906).

## Fog: RS Environment (1036757)
- `[11001]` scattering (1/m), `[11017]` viewing distance (m), `[11003]` anisotropy, `[11000]` tint, `[11004]`
  emission, `[11006]` fog height, `[11007]` horizon blur, `[11008]/[11009]` ground point/normal, ray contributions
  `[11011]` camera, `[11012]` reflection, `[11014]` GI, `[11010]` environment fog. Present in the scene = active.
- 0.04/m with anisotropy 0.5 made spot and pillar beams visible in a 30 m scene; with a strong spot the whole sky
  went grey (the fog scatters everything) — balance spot intensity against scattering.
- Volumetric scenes are slow: 432×540 took 40–90 s on an Apple GPU (fog + mesh lights + RS curves).

## Camera post effects (RS Camera)
- Bloom **mode** `[12110]` is an enum, not a switch: **1 Off, 0 Render Settings, 2 Override**. Writing `True` (= 1)
  turned bloom OFF. Use 2 to enable it on the camera, plus `[12100]` (enable inside the override).
- **The camera wins over the render settings:** with the camera's mode on Override, bloom rendered although it was
  off in the render settings. Leave camera post effects on 0 (Render Settings) unless a shot needs its own.
- Bloom threshold `[12101]` (default 20: too high for most scenes; 2 used), intensity `[12103]`, softness `[12102]`.
  Flare `[12214]` (mode, same enum presumably — check) / `[12200]`, intensity `[12206]`, threshold `[12201]`.
  Streak `[12307]` / `[12300]`, number `[12304]`, angle `[12305]`. The render settings' RS videopost had no bloom
  params in its description.

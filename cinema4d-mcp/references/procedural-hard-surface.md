# Procedural hard-surface devices from Python (verified C4D 2027.0 + Redshift, Windows, Nov 2026)

Building rack-mount hardware (switches, servers) from a reference photo/render with code, through
`exec_python` in the running C4D, rendered with Redshift via Commandline.

## Workflow that worked
1. Measure the reference: scale = known panel width (datasheet) / its width in pixels; convert every
   feature to panel coordinates (u from the left edge, v from the bottom) in cm. Autocorrelation of
   a row/column average of a perforated strip gives the hole pitch (offset rows halve the period).
2. A **kit document** of reusable parts (port cages, jacks, LEDs, screws, ears, handles, fan and PSU
   modules), each a Null with its pivot at the panel plane (front faces −Z), true size in cm,
   materials on the parts. Build parts from primitives (`Ocube` with fillet, `Ocylinder`,
   `Otorus`) — add Phong tags yourself (`c4d.BaseObject()` primitives have none → faceted renders).
3. The **device document**: copy the kit materials + the needed parts with one `c4d.AliasTrans`
   (`trans.Init(kit)`, `GetClone(COPYFLAGS_NONE, trans)` for materials and objects, `Translate(True)`)
   into a hidden masters Null (visibility `c4d.MODE_OFF`, not `True`), then place
   `Oinstance` objects with `INSTANCEOBJECT_RENDERINSTANCE_MODE = 1`. Instances of hidden masters render.
   **Never scale parts or instances to fake a variant** — no non-uniform scale (a squashed LED),
   no shrinking (an 80 mm fan at 72 % as a 60 mm one), no −1 mirror: real hardware has no such
   variants and it shows. Build each variant as its own part at true size (rectangular light pipe,
   60 mm fan, handle for that pocket, a separately built left-hand ear); instances stay at scale 1.
   After a build, audit every object's `GetRelScale()` in both documents.
4. Render from a saved file with Commandline (never inside the GUI on 2027), compare against the
   reference: composite on the reference's background colour, crop both to their object bbox, scale to
   one width, stack + 50 % overlay. Match the camera from the reference's perspective first:
   the ratio of the top's back-edge width to the front width gives the distance
   (`w_back / w_front = d / (d + depth)`), the projected top height gives the camera height.

## Perforated panel with real, full holes (spline + Extrude)
- Real punched panels end every perforated region on **whole** holes (stepped edges on offset rows) —
  a tiled opacity texture cut by rectangles can't do that and has no depth.
- One `SplineObject` (linear) with one closed segment per contour: the panel outline, every port
  opening (rectangles), each hex hole (6 points), round LED holes (12–14 points); under an
  `Oextrude` with `EXTRUDEOBJECT_EXTRUSIONOFFSET` = sheet thickness (default is 100 cm!). Inner
  segments become holes with caps; ~1150 segments (≈1070 hex holes) extruded in well under a second
  to ~19k polygons. Phong angle ~30° keeps the hole walls crisp. Rebuild later by rewriting the
  spline's points/segments (`ResizeObject(npts, nsegs)`, `SetSegment`, `SetAllPoints`) — the Extrude
  updates live.
- Hole placement per region (u0, u1, v0, v1): pointy-top honeycomb with pitch p and row step r,
  circumradius R = flat-to-flat / √3; n_rows = floor((h − 2R) / r) + 1 centred vertically; even-row
  columns n = floor((w − f2f) / p) + 1 centred horizontally; odd rows shifted by p/2 keep only holes
  whose whole hexagon fits → the stepped edges real panels have. Single edge columns: flat-top
  hexes (rotate 30°) at their own pitch.
- Put a black backing plane ~0.8 cm behind the panel so holes read dark.

## Panels with openings, no Booleans
- `Oboole` is the legacy Boole; avoid Booleans for flat panels: decompose the panel rectangle minus
  hole rectangles into a grid of cells (all hole edges as cuts), keep cells outside every hole, merge
  runs along each row, and write the result as quads of one `PolygonObject` (with a UVW tag). Used for
  top plates with pockets and rear plates with module bays.

## Materials and decals
- Printed labels/logo: one RGB texture + one grey mask covering the whole panel (0.1 mm/px), on a quad
  4 µm in front of the panel; mask → `opacity_color` (the texture sampler has no alpha output).
  Generate it with PIL at the measured positions (text anchors centred on the features).
- **No contour may touch or overlap another**: one hex whose outline reached 0.07 cm into a port
  opening made the Extrude cap fill the *whole* opening — a row of 16 ports rendered as flat grey
  panel (looked like "milky" ports; darkening the cage walls did nothing). Guard before building:
  grow each contour's bbox by half the minimum web and test neighbours (honeycomb hexes: test centre
  distance ≥ flat-to-flat + web instead), and refuse to build on any clash.

## Commandline output names
- `-oimage …/name` → `name0000.png`, but a name ending in a digit (`…_r2`) became `…_r2_0000.png`.

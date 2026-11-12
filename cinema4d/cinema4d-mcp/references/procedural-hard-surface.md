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
   reference: composite on the reference's background colour, stack + 50 % overlay. Match the camera
   exactly first (next section) and compare 1:1 at the reference's aspect. Cropping both images to
   their object bbox and rescaling hid a wrong camera distance (back/front width 0.73 against the
   reference's 0.645). Features placed with that camera were up to 6 cm off on the top surface.
5. A kit part missing in a device document: `GetClone()` it, then point each texture tag at the
   device document's material of the same name (clone the material across if it is missing). A bare
   clone keeps its tags linked to the kit document's materials.

## Exact camera match for product renders (level camera + lens shift)
- Product renders are usually shot with a **level camera and lens shift**: the panel's vertical edges
  stay parallel (equal panel width at its top and bottom row). A tilted camera can't reproduce that.
- From the reference (pixels): front width `Wf` → `s = Wf / panel width` (px/cm at the front plane);
  back-edge width `Wb` → distance to the front plane `d = depth · Wb / (Wf − Wb)`; `f_px = s · d`;
  top front edge row `y_f`, back edge row `y_b` → camera height above the top
  `h = (y_f − y_b) / (s · (1 − d / (d + depth)))`; eye-level row `y_c = y_f − s · h` (above the frame
  when the camera looks down on the object).
- C4D camera: focal = `f_px · aperture / image width`, at height (top + h), distance d, no rotation;
  `CAMERAOBJECT_FILM_OFFSET_Y = (image_height / 2 − y_c) / image_height`. **The Y offset is a fraction
  of the frame height** (verified 2027.0 by rendering: the width-based value moved the image 0.56× as
  far). A positive value brought a subject below eye level up into the frame; the wrong sign rendered
  an empty frame. Redshift honours the standard camera's film offset. One test render gave a bbox
  within 2 px of the reference at 1280 wide.
- Positions on the top surface from pixels (e = eye height above the surface):
  `z = f_px · e / (y − y_c) − d`, `x = (x_px − x_c) · (d + z) / f_px`.
- Checking a detail: a second camera at the same position, focal × k, aimed at the detail. Compare
  it with the reference window of width `image_width / k` around the detail's projected point
  `(x_c + f_px·x/(d+z), y_c + f_px·e/(d+z))`, upscaled. Same eye point, so it matches almost 1:1.

## Building several devices from one kit (verified Nov 2026: a 2RU and a 1RU switch in one pass)
- One builder script with a spec per device: openings as contours in panel coordinates, a list of
  (name, kit part, u, v, z) placements, rear modules, ears, the matched-camera numbers. When a kit part
  changes, rebuild the device documents from the kit rather than patching their master copies.
- **Straight-on panel elevations** (open device-type libraries publish front-panel images that are
  exactly the body width) give u, v directly: scale = image width / panel width. Faster and more exact
  than rectifying a perspective render; use the render only for the camera match and the 3D details.
- Identify a hex lattice before rebuilding it: autocorrelate a row inside the band (the same-row pitch)
  and a column (the in-column pitch). Column spacing / in-column pitch = √3/2 means **flat-top** hexes
  stacked in columns; the same ratio between rows and row pitch means pointy-top. Hole size from the
  dark-area fraction: f2f = √(q · cell area / 0.866).
- The overlap guard also catches holes too close to the panel edge (a slot column at exactly the
  minimum web from the edge failed on rounding; keep a little more).
- **Holes in thin parts (rack-ear slots) must be cut**: dark slot boxes 0.4 mm thick with a large fillet,
  laid on the ear, did not render at all (cause not isolated; the fillet was larger than half the
  thickness). An ear built as a spline outline + stadium-shaped holes under an Extrude, inside a hidden
  master used by render instances, rendered see-through slots.
- Hollow round parts (coax jacks, barrels): `Otube` (`PRIM_TUBE_IRAD/ORAD/HEIGHT`, `PRIM_AXIS`). A
  solid cylinder's cap hid the bore and pin.
- Reference photos of one product family differ in exposure (top surfaces from sRGB 157 to 200 for the
  same paint). Match the paint on one reference and keep it shared; don't tune it per photo.

## Details that read wrong until fixed
- **Port cages are ganged**: one stamped 1×N / 2×N part fills each panel opening, with shared walls
  and thin bright front edges. Single cages, each with its own rim, put a thick frame around every
  port with panel showing between. Build the ganged part at true size (width = N · pitch, inner
  walls ~0.6 mm).
- What shows through an opening is the **nearest surface behind it**: comb windows stayed grey after
  blackening the comb's backing, because the band divider's front face sat in front of the backing.
- Product views 5–7° above the top hide anything below the near lip of a recess: handle hardware in
  a top pocket shows only where it reaches the cover level.
- Brightness: compare mean sRGB of matching plain regions (front, top) in the 1:1 render. A chassis
  albedo of 0.15 rendered ~1.5× darker (linear) than a white-studio reference; 0.21 came within ~5 %.
- Small printed symbols (warning stickers): draw them 8× larger with PIL and downsample with LANCZOS
  into the decal. The symbol's own mask clips strokes that overrun its outline.
- Reference images saved as `.jpg` from websites can be AVIF (`file` reports "ISO Media, AVIF
  Image"), and Pillow raises `UnidentifiedImageError`. Use `uv run --with pillow --with
  pillow-avif-plugin` and `import pillow_avif`.

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

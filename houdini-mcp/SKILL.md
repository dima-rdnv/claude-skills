---
name: houdini-mcp
description: Core rules for driving SideFX Houdini through the houdini MCP bridge (execute_houdini_code, get_scene_info). Use EVERY time a task touches Houdini via MCP — inspecting scenes, building networks, sims, caching, exporting, flipbooks.
---

# Houdini via MCP — core

Verified in Houdini 21 Indie (macOS) and Houdini 22.0.429 Indie (Windows, Python 3.13).
Prefer these notes over memory.
Default approach: use Houdini's native systems (POPs, Pyro, stock SOPs/DOPs) over custom solutions;
faking is fine when abstract/art-directed; output is aimed at After Effects compositing or
Cinema 4D rendering; readable networks (see `houdini-network-layout`).

## Sub-skills — load the one that matches the task
- `houdini-pop-particles` — POP sims: emission, collisions/containers, spray physics, clumping,
  speed ramps, diagnostics.
- `houdini-pyro-smoke` — sparse Pyro Solver SOP in a closed, moving container (engine cylinder):
  CAD colliders, collider velocity, dissipation units, caching, smoke leaving through a valve.
- `houdini-vdb-surfacing` — particles → VDB SDF → mesh blobs with transferred colour.
- `houdini-network-layout` — network boxes, sticky notes, comments, safe cleanup of unused nodes.
- `houdini-flipbook` — viewport flipbooks, and OpenGL ROP passes with real alpha (rendered by
  hython) through a camera copied from Cinema 4D, for compositing over C4D renders.
- `houdini-to-cinema4d` — Houdini side of the Alembic hand-off to Cinema 4D / Redshift.
- Cinema 4D: `cinema4d-mcp` (core + index), `cinema4d-alembic`, `cinema4d-redshift`.
- `vo-timing` — word-level timings from a voice-over to key sim events.
- `project-notes` — per-production notes (brief, timings, scene map, state) kept outside the skills;
  read them at the start of any task on a named production.

## Installing the bridge
Server: github.com/capoomgit/houdini-mcp (installed @de4fd93, Jun 2026). Houdini-side package
`houdinimcp` (socket server on 127.0.0.1:9876) + stdio bridge `houdini_mcp_server.py` (FastMCP).
`uv.lock` pins mcp 1.4.1 — install with `uv sync --frozen` (mcp 2.x breaks `mcp.server.fastmcp`).
OPUS tools need a RapidAPI key in `urls.env`; the "urls.env not found" warning is harmless.
Mac install method not recorded (unverified).

**Windows — VERIFIED working (Sep 2026, Houdini 22):**
- Plugin: `Documents\houdini22.0\scripts\python\houdinimcp\` (whether H22 puts `scripts/python`
  on `sys.path` by itself is unverified — the shelf tool adds it anyway).
- Shelf: `Documents\houdini22.0\toolbar\houdinimcp.shelf` → "MCP" tab (shelf `+` → Shelves → MCP),
  one toggle tool; it appends `$HOUDINI_USER_PREF_DIR/scripts/python` to `sys.path` before import.
- Bridge venv: `%LOCALAPPDATA%\houdinimcp\.venv` via `UV_PROJECT_ENVIRONMENT` (keeps it out of
  Documents, which is often cloud-synced). Python 3.12 downloaded by uv.
- Install steps worth scripting (PowerShell): install uv → `uv sync --frozen` → import check
  (`python -c "from mcp.server.fastmcp import FastMCP"`) → config edit; write a log next to the
  plugin so it can be read back through a connected folder.
- Claude Desktop is MSIX here: config is
  `%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json`
  (it may have no `mcpServers` key yet — extensions are stored elsewhere). Edit only after Claude quits
  (script waits on `claude` processes, ignoring `~\.local` = Claude Code), backup `.bak-<date>`,
  relaunch via `Get-StartApps` AUMID.
  Entry: command = venv `python.exe`, args = [bridge path].
- Cowork on Windows: terminals are click-only for computer use and the desktop Filesystem MCP
  tools fail (draft-07 outputSchema error). Working method: write files with `device_bash` into a
  connected folder, give the user one PowerShell command to run.
- After the relaunch the tools appear in the SAME conversation as `mcp__remote-devices__houdini__*`.
- This bridge version also has dedicated tools (create_node, set_parameters, connect_nodes,
  get_geometry_info, cook_node, find_error_nodes, render_single_view, create_wrangle…) and calls
  `execute_houdini_code` a last resort; the recipes below use `execute_houdini_code` (dedicated
  tools unverified).

## Working with the bridge
- Always start with `get_scene_info`, then inspect with `execute_houdini_code` printing compact text.
- If the bridge errors "Could not connect ... localhost:9876", ask the user to start the Houdini-side
  plugin (Windows: the MCP shelf button; console shows "HoudiniMCP server started on 127.0.0.1:9876").
- **Bridge timeout ≈ 10–20 s per call** (10 s seen on macOS while other jobs loaded the CPU). Step
  sims in time-budgeted loops (`while f <= end and time.time() - t0 < 6:`), not fixed frame counts.
  A timed-out call keeps running in Houdini: poll with a tiny call (`hou.frame()`,
  `hou.hipFile.hasUnsavedChanges()`) before repeating anything — e.g. `hipFile.save()` of a 12 MB hip
  took > 10 s and "failed" although the save happened.
- Loops over every prim for many frames (e.g. 30 frames × 150k prims) time out too. Sample a few
  frames, subsample points (`pts[::step]`), or compare bboxes instead.
- Node type names in Python are not always the UI names. Before `createNode`, list the category:
  `hou.sopNodeTypeCategory().nodeTypes().keys()` and grep. Examples: "Transform Pieces" =
  `xformpieces`; POP Source = `popsource::2.0`; POP Solver = `popsolver::2.0`; Collision Source =
  `collisionsource::2.0` (VDBs on output 1, not 0).
- Menu parms need their tokens, not labels: read `parm.parmTemplate().menuItems()` first.
- `SopNode` has no `inputLabel(i)` — use `node.inputLabels()`.
- **`parm.set()` does NOT override an expression-driven parm**: ROP `f1/f2` are `$FSTART/$FEND`,
  the Alembic SOP `frame` is `$FF`, timeshift `frame` is `$FF`. `deleteAllKeyframes()` first.
- `parm.unexpandedString()` raises on keyframed string parms — guard with `if p.keyframes()` /
  `p.expression()`.
- **Blast with an EMPTY group deletes everything.** For "empty outside a frame window" use a
  wrangle: `if (@Frame < s || @Frame > e) removepoint(0, @ptnum);` (prims: `removeprim(0, @primnum, 1)`).
- DOP nodes have no `setRenderFlag` (only display flag).
- Wrap each build step in one script and print a verification (counts, bbox, sampled values).
- **A script that errors stops at the error line — everything after it did NOT run.** Inspect state
  before retrying.
- **FIRST STEP OF EVERY SESSION: park the display flag on a node without a sim** and restore the
  user's display node at the end.
- **Never change the frame while a sim node is displayed** — including Pyro/DOP nodes in *other*
  objects whose object display flag the user turned on. Jumping to a later frame makes the viewport
  cook the sim from its start frame ("catch-up"); `hou.frame()` then reports the intermediate frames
  while it steps, and `hou.hipFile.save()` fails with "Node cook is in progress: <node>". Only the
  user can interrupt it (Esc in Houdini). Keep a file-cache reader (`file` SOP) as the display node of
  every sim object, and read sims with `geometryAtFrame` / cache files.
- **`geometryAtFrame()` on a node downstream of a DOP network cooks the whole sim** in the GUI from
  its start frame (a POP sim reading a Pyro cache blocked the bridge for ~15 min). Read the exported
  cache (.abc / .bgeo / .vdb) with a fresh `alembic` / `file` SOP instead.
- New geo objects are created with their display flag ON — switch it off before stepping frames.
- After `dopnet.parm('resimulate').pressButton()`, a loop that only cooks a `dopimport` sometimes did
  nothing (0 particles, "No DOP object names specified"). Touch the sim every frame:
  `hou.setFrame(f); dopnet.simulation().objects(); imp.cook(force=True)`, starting at `startframe - 1`.
- Destroying a node of an HDA type (seen with `pyrosolver`) can pop a harmless "Python Callback
  Error … hrecipes … No such file or directory: 'Embedded'" dialog that blocks the bridge until the
  user clicks OK. Avoid create/destroy "probe" nodes of HDA types; read parm templates from a node
  you keep.
- **VEXpression variable names** for POP local expressions:
  `vexpressionmenu.buildSnippetMenu('<nodetype>/<parm>', kwargs={'node':n,'parm':n.parm(p)})`
  lists presets that reveal them (popwind: `wind`, `windspeed`, `airresist`, `amp`, `swirlsize`;
  popspeedlimit: `speedmin`, `speedmax`, `spinmin`, `spinmax`; popcolor: `ramp`).
- `chf("parm", time)` inside a per-particle VEXpression is very slow; precompute per-frame values as
  spare parms with hscript `bbox()` expressions (a `timeshift` SOP gives the previous frame).
- VEX: `point(0,"P",i)[1]` is an "ambiguous call" error — assign to `vector p` first.

## Keyframes from Python (verified, Houdini 21)
- **Build every key as a fresh `hou.Keyframe()`** (`setFrame`, `setValue`, `setSlope`,
  `setExpression("cubic()", hou.exprLanguage.Hscript)`), then
  `parm.deleteAllKeyframes(); parm.setKeyframes(keys)`. Do NOT build keys as copies of an existing
  key (`hou.Keyframe(old)`): the copy keeps the old key's in-slope and tie state, and `cubic()` then
  used the old in-slope — errors up to 257° on a crank channel. Fresh keys matched the target
  Hermite curve to 0.0000.
- On a key built with `setSlope()` only (in and out tied), `inSlope()` raises
  `hou.KeyframeValueNotSet` — read `slope()`.
- Pin the slope on every key, including the first and last; slopes are in value units per SECOND.
- **Verify a keyed channel against its source formula** in the same script: sample
  `parm.evalAtFrame(f)` over the range, print the max difference, and stop (no save) above a
  tolerance.
- Evaluate channels only after `hou.hipFile.load()`: a bare hython session runs at 24 fps, so
  frame ↔ second conversions (and `$FPS` expressions) come out wrong.
- Camera moves that must match another app frame-exactly (smoothstep, a u³ crash zoom): compute the
  value per frame from one shared formula / JSON and key every frame (linear) in both apps, instead
  of matching tangents.

## Caching long sims in the background (verified, Houdini 21 Indie, macOS)
- Run ROPs with `hython` from a shell so the GUI and the bridge stay free:
  `nohup <Houdini>/Resources/bin/hython script.py "<hip>" /obj/A/ROP /obj/B/ROP > log 2>&1 &`
  where the script does `hou.hipFile.load(hip, suppress_save_prompt=True, ignore_load_warnings=True)`
  and `hou.node(path).render(verbose=False, output_progress=True)` per ROP, printing START/DONE.
  Save the hip first (the job reads the file on disk). Two hython jobs + the GUI ran at once on Indie.
- A hython script can also build networks, change parms and `hou.hipFile.save()` before rendering —
  useful when the GUI is closed. Keep such build scripts re-runnable (destroy + recreate the nodes they
  own) and store them next to the hip.
- `hou.hipFile.save(path)` into a folder that doesn't exist fails — `os.makedirs` the folder first.
- **Version mix:** hython 21.0.792 (Mac) loaded hips saved by Houdini 22.0.466 (Windows), rebuilt
  networks, ran Pyro / POP caches and OpenGL ROPs, and saved them (verified twice).
- hython may write `/tmp/houdini_temp/crash.*` on exit (signal 11 in `UI_RadialMenu` /
  `FUSE_RadialLauncher` destructors) after the script finished — harmless; trust the saved file and
  the DONE line.
- A Pyro Solver SOP cache can't resume: if the job dies (process closed), restart the ROP from its
  start frame; the files are overwritten.
- **A hython job that saves the hip makes the copy open in the GUI stale**: saving from the GUI later
  silently reverts the job's changes. Re-apply them in the GUI (or reload the hip) before saving there.
- **Memory:** the GUI died with "OpenGL Fatal Error: … not able to run OpenGL 3.3" while macOS swap
  was full (other apps held > 100 GB); no crash file was written, so unsaved GUI work was lost. Before
  long GL / flipbook work check `sysctl vm.swapusage` and `top -l 1 -o mem -n 5`, and save first.
- Monitor from the shell (file count in the output folder, log tail); never block the bridge.
- Observed once: the GUI Houdini quit (crash stack inside the license verify loop) while two hython
  jobs were running. Save the hip before launching jobs; reopen the GUI after they finish.
- Chain dependent jobs with a small shell script that waits for `DONE <rop>` in the first job's log
  before starting the next (e.g. a POP sim that reads a Pyro cache).
- Put big caches outside cloud-synced project folders (ask the user where); delete superseded test
  caches only with their OK.

## Copying networks between objects
- `dest.copyItems([box] + list(box.items()))` copies nodes **with** their network box and sticky
  note; `hou.copyNodesTo([node], parent)` copies whole objects.
- After copying, rewrite absolute paths (`/obj/OLD/...`) in string parms and expressions, and turn
  relative channel references that leave the copied set (`ch("../transform1/sx")`) into absolute ones.

## Moving a project to another folder or machine (verified)
- Absolute file paths baked into a hip (old project root, cache folder) break after a move. Repath
  them in a hython script: walk `hou.node('/').allSubChildren()`, take each string parm's
  `unexpandedString()` (skip keyed ones), replace the old project root with `$HIP/..` and the cache
  root with an env var (e.g. `$PROJECT_CACHE`) that each machine sets in `houdini.env` or before
  launching hython. Print the number of changed parms and save under a new name.
- Hand the other machine the scripts, not instructions to click: setup scripts that take
  `<in.hip> <out.hip>`, print their checks, and refuse to save when a check fails.

## FBX / Alembic
- `kinefx::fbxanimimport` carries animation on a skeleton; the static `file` SOP geo does not move.
  Rebuilding motion with `xformpieces` is fragile (FBX unit conversion scaled positions ~10× but not
  motion). **Preferred: an Alembic export of the animated asset**, retimed with `simple_retime`.
- Alembic pieces are identified by the prim `path` attribute (leaf names end in `Shape`).
- The Alembic SOP's `usevisibility` (on by default) makes `unpack` drop objects that were hidden in
  the source app (CAD colliders, injector) — set it to 0 when you need them.
- Unpack packed Alembic prims before using them as colliders; PolySoups → `convert` (or unpack's
  `convertpolysoup`).
- **Check which parts animate before planning around them** — sample each part's bbox over time, and
  look for hidden static duplicates of the animated parts (e.g. `Valves/Hidden/...` next to the baked
  valves): blast the hidden copies. (An earlier note here said an engine bake had static valves —
  that was the hidden copies; the baked valves animate.)
- **Retime a baked Alembic by a curve** instead of re-baking: measure the bake's rate (fit TDC/BDC
  times of a piston bbox → °/s and phase), key a spare `crank` channel with the same keys as the
  source rig, and drive a `timeshift` (method frame, `integerframe` 0):
  `frame = (ch("../crank") - theta0) / deg_per_s * $FPS`. The Alembic SOP interpolates fractional
  frames linearly. Parts that were baked with a lag get their own timeshift with an offset.
  If the curve runs past the end of the bake, fold it back by whole cycles (e.g. subtract
  720·ceil(max(0, crank − last_baked) / 720) for a four-stroke cycle).
- Matching a C4D key curve exactly: Houdini keys with `cubic()` + `setSlope(m)` (units per second) are
  Hermite — identical to C4D tangents of length h/3 (max error 0.008° over 150 s). Recompute the
  slopes with the same rule the source used (C4D's monotone keys matched PCHIP / Fritsch–Butland, not
  the classic Fritsch–Carlson pass). Build the keys fresh (see "Keyframes from Python").

## Keeping this skill current
After any session that used Houdini/Cinema 4D via MCP, or whenever something new is verified:
1. Add gotchas/recipes ONLY if tested and working in a real scene; mark anything else "(unverified)".
2. Correct entries that proved wrong — don't append contradictions.
3. Put each finding in the skill it belongs to (see the indexes in `houdini-mcp` and `cinema4d-mcp`);
   project-specific facts go to that project's notes (see `project-notes`), never into a skill.
4. Keep each SKILL.md under ~300 lines; split into a new sub-skill or `references/` when it grows.
5. Re-package every changed skill (keep names) and, if the skills live in a git repo, commit and push;
   in a public repo keep personal names and client details out of the text. Tell the user in one line
   what changed.

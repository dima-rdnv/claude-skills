---
name: cinema4d-mcp
description: Core rules for driving Cinema 4D through MCP (Maxon's built-in server or the legacy socket plugin) and headless c4dpy — setup on macOS and Windows, upgrading to a new C4D version, exec_python rules, long jobs and Alembic exports in c4dpy, Save-As, Render Queue traps, safe test documents, UI-only steps via computer use, and the index of Cinema 4D sub-skills. Use EVERY time a task touches Cinema 4D, or when a C4D MCP tool fails.
---

# Cinema 4D via MCP — core

Notes carry the version they were verified on, mostly C4D 2026.x. On a newer C4D treat them as strong
hints, and correct a note when it no longer holds.

## Sub-skills — load the one that matches the task
- `cinema4d-alembic` — Alembic import from Python, importer options, frame/scale checks, Particle
  Groups vs Thinking Particles, attribute mapping, reading particle data.
- `cinema4d-redshift` — Redshift node materials through the maxon API, node/port IDs, RS Object tag,
  test renders with pixel checks, known dead ends.
- `cinema4d-particles` — native 2024+ particle system: emitters, groups, Data Mapper/Math/Look
  modifiers, forces with measured units, Cloner on particles, RS rendering, sim traps.
- `cinema4d-rigging` — control nulls with user data, Python tag drivers, XPresso/tag evaluation order,
  retiming cycle controls with monotone keys, mechanisms (slider-crank), self-updating dropdowns,
  spline travel, HUD, procedural splines/meshes.
- `cinema4d-render-preview` — look at renders from the sandbox: clone → step sim → RenderDocument →
  base64 JPEG, contact sheets, reference-video comparison, viewport screenshots.
- `cinema4d-takes` — reading/creating takes, overrides (incl. user data), override groups,
  per-take camera/render data, splitting one edit camera into shot cameras + takes, rendering takes
  through the Render Queue, verifying a take via TakeToDocument.
- `cinema4d-motion-tracker` — Motion Tracker: reading 2D tracks/solve, why a solve stops, running
  the solver from a script, extending a solve past an occlusion, real-world scale, baking a camera.
- `houdini-to-cinema4d` — the Houdini side of the Alembic hand-off (export recipe, verification).
- `aftereffects-bridge`, `aftereffects-scripting` — reading/building the AE project the renders go into.
- `project-notes` — per-production notes (scene map, state) kept outside the skills.

## Two servers — check which one this session has
- **Maxon's built-in MCP server (C4D 2026.4+) — use this one.** Tools show up as `cinema4d__*`
  with typed tools (`list_documents`, `open_document`, `get_render_status`, `start_queued_render`,
  `create_take`, `set_take_override`, `render_to_file_blocking`, …) plus `exec_python`.
- Legacy: the community socket plugin (`mcp_server_plugin.pyp` + `main.py`, port 5555, tool
  `execute_python_script`). Install and notes: `references/legacy-socket-plugin.md`, step by step in
  `SETUP.md`.
- `ping` reports protocol / C4D / plugin versions and a `session_id`; a new session_id means C4D
  restarted and every handle you hold is stale.

## Maxon MCP server — setup (verified C4D 2026.4.0, macOS, Claude Desktop)
- C4D 2026.3.x has no MCP page in Preferences. Update through the Maxon App; it asks to close every
  process using Maxon libraries first (C4D, `c4dpy`, also `hython` was listed) — ask the user before
  stopping background jobs.
- Preferences → MCP: enable the server; **Allow exec_python** is a separate switch (off = the call is
  refused and the refusal names the preference — relay that to the user).
- "Update Selected Client" writes the server entry into the client's config. **Claude Desktop rewrites
  `claude_desktop_config.json` from memory when it quits**, so the order is: quit Claude Desktop →
  click "Update Selected Client" in C4D → reopen Claude. Done the other way round, the entry vanished.
  It replaces an existing entry of the same name (here the old community server).
- After reopening, the tools reach the same conversation (deferred tools — load them by name).
- Transport: `mxn_plugins/mcp_adapter` is a stdio relay to `http://127.0.0.1:5556/mcp` (2026.4,
  adapter 1.0.0.22).

## What 2027.0 ships (read from a macOS install's files, not yet exercised on macOS)
- The adapter lives in `resource/mxn_plugins/mcp_adapter` in the app folder. Its
  `mcp_adapter/catalog/tools.yaml` describes every tool and its traps: read it when a tool is unclear.
  Every tool named in these skills is listed there. Not yet tried in these notes: `run_batch`, `undo`,
  `call_command`, `search_assets` / `insert_asset`, `apply_node_material_graph`, `set_mesh`.
- Preferences → MCP now has an **Auth Token** (Show / Copy / Regenerate), Port, Request Timeout, **Allow
  exec_python Command** and **Allow Python-Bearing Operations** (the enable dialog says both are on by
  default), Remote Access (Allow Remote Connections, Whitelisted IPs, Browser Client Origins; without it
  only this computer connects, with it the token and scene data travel unencrypted) and Toolset groups
  (applied after the client restarts).
- Clients: "Anthropic Claude Code (Desktop App)", "OpenAI ChatGPT & Codex", "Other" (Copy Config), each
  with a status. "Update Selected Client" backs up the client's config and names the file in its
  dialog. **Regenerating the token locks out every client** until that button is pressed again.
- Its dialogs say a client connects only at startup: leave C4D running, quit the client completely,
  restart it. That fits the quit-first order above. The relay retries `initialize` for 20 s while nothing
  listens, so starting both together works; a client started long before C4D has to be restarted.
- The relay gives up on a call after 300 s, and a call in flight over 10 s prints a stall line to the
  client's MCP server log, so that log can tell a lost call from a slow one.

## After upgrading C4D
The new version's adapter may be off (check the port before trying tools), and old plugin folders and
paths don't come along. Renders can continue through the bundled command-line renderer and scene edits
through `c4dpy`, both without MCP: see `references/upgrading-c4d.md`.

## exec_python (Maxon server)
- Runs on C4D's main thread; C4D is frozen for the whole call. Default wait 30 s
  (`timeout_seconds` to extend; the client's own timeout still applies — keep calls short).
- Namespace: `c4d`, `doc`, `resolve(handle)`, `handle_for(node)` (handles are what the typed tools
  use; `doc.SearchObject(name)` silently returns the first of several same-named objects).
- Undo: `undo=true` records nothing by itself; also call `add_undo_create(op)` / `add_undo_change(op)`
  before each edit. `SetTime` alone triggers a harmless "not undoable" warning.
- `add_undo_change(doc)` does not capture document settings: `doc.DoUndo()` reverted the render data
  but left SetFps/SetMinTime/SetMaxTime changes in place. Get settings right first time; record old values.
- `add_undo_create` only works for the active document (`doc`); objects inserted into another open
  document are kept but the call errors and Ctrl-Z there won't remove them — say so.
- File writes with `open()` work there — export JSON and do heavy maths locally.
- Long jobs (exports, renders) don't belong in a main-thread call: use the Render Queue
  (`start_queued_render`, `get_render_status` sees per-job state) or headless `c4dpy` (below).

## Other Maxon tools (verified 2026.4, Windows)
- `list_entities(kind="object")` on a tracked scene (300+ feature nulls) overflows the reply —
  summarise the hierarchy with `exec_python` instead.
- `capture_viewport` shows the active scene camera's view incl. helper objects — good for checking
  tracked points and scale proxies against footage. It only captures the **active** document, and it
  can keep returning a stale image (`identical_to_previous: true`, same digest) after real changes, even
  after `DrawViews(FORCEFULLREDRAW)` — then verify numerically or render instead.
- `render_preview_image` renders through the **Main take's camera**, not the viewport's: changing
  only `td.GetMainTake().SetCamera(td, cam)` changed the render while the viewport camera stayed put.
  It runs on its own thread (~40 s for a Redshift preview at 960×540): call again to collect.
  After `stop_render` the next call can return "cancelled" once — just call it again.
- `start_render(output_path=…exr)` wrote a 3-channel EXR (alpha dropped); without `output_path` it uses
  the RenderData save settings and wrote RGBA. A save path with `$prj` turns spaces in the scene name
  into underscores and creates that folder.

## Redshift renders from inside the GUI can hang C4D (verified 2027.0, adapter 1.0.0.26, Windows)
Cause unknown (6 Nov 2026). Every in-GUI route waited forever, and only a C4D restart freed Redshift:
- `exec_python` + `RenderDocument` (fresh 160×90 doc) → main thread blocked, window "Not Responding",
  the adapter answered nothing; the user had to kill C4D.
- `start_render` (own thread) → "rendering", 0 % for minutes; `stop_render` → "cancelled" but still
  `running: true`, and every later render waited behind it.
- Render Queue (`BR_START`, scene saved to disk) → the same wait, nothing written.
- The Redshift log shows it (`C:\ProgramData\Redshift\Log\Log.Latest.0\log.html`, strip the HTML):
  `Context: Locked:Render` then `Context: Busy:Render Waiting until idle`, and no further render lines.
- A Redshift `RenderDocument` in **c4dpy 2027** hung too (idle, no output). A leftover c4dpy may not
  be killable from here — ask the user to end it in Task Manager.
Rules: (1) never `RenderDocument` with Redshift inside `exec_python`; (2) before relying on GUI
renders in a session, render ONE tiny frame and read the RS log after ~20 s — on "Waiting until idle"
stop, tell the user (restart needed) and don't retry; (3) while anything renders, watch only from
outside (output folder, RS log), never fire tool calls into the busy app; (4) never `BR_STOP` from
Python, stop the queue in its window; (5) test frames go through `Commandline.exe` (see
`references/upgrading-c4d.md`), which runs outside the GUI and rendered Redshift fine in 2027.0.
- From a shell (e.g. when this session's cinema4d tools disconnected): Maxon's stdio relay with
  the token file — recipe and reply format in `references/shell-relay.md`.

## Headless c4dpy for long jobs (verified C4D 2026, macOS)
```bash
C4D="$(ls -d "/Applications/Maxon Cinema 4D 20"* | tail -1)"     # newest installed version
nohup "$C4D/c4dpy.app/Contents/MacOS/c4dpy" g_licenseModel=LICENSEMODEL::MAXONAPP \
    /abs/path/script.py arg1 arg2 > /tmp/job.log 2>&1 &
sleep 2      # a background spawn from a remote shell may not start without it
```
- `g_licenseModel=LICENSEMODEL::MAXONAPP` (first argument) skips the licence prompt (verified macOS
  and Windows; on Windows `printf "1\n" | c4dpy …` crashed at the prompt). Without it, piping `1`
  answers the prompt on macOS. Pass the script by **absolute path** — a relative one is looked up
  inside the C4D bundle ("can't open file").
- "License needs activation" = the Maxon licence is in use on another machine: one machine at a time.
- Runs without the GUI, next to an open C4D. `LoadDocument` the user's file read-only, work on a
  take document (`td.TakeToDocument(take)`), write results to new files — the open scene is never
  touched. Redshift loads there too — check `c4d.plugins.FindPlugin(1036219)` before saving a file
  that holds RS cameras / lights / video post.
- **The Viewport renderer doesn't work headless.** `RenderDocument` with the Viewport renderer gave a
  black frame in c4dpy (and flat grey shading in another scene). Render VP takes in the GUI (Render
  Queue); c4dpy is fine for edits, exports and Redshift.
- Use it for anything that would block the GUI: Alembic exports of heavy takes, per-frame sampling,
  file edits saved under a new name (Save-As rules below still apply).
- **Alembic exports started from the live GUI (through the MCP bridge) stalled** three times after
  C4D restarts — main thread inside `io_alembic`, nothing written, force quit; the same exports ran
  fine in c4dpy. Prefer c4dpy for exports.
- **A Cloner in the selection stalled the exporter in c4dpy too** (500k clones; nothing written after
  15 min). With the Cloner moved under a **Connect** object (`c4d.BaseObject(1011010)`) in the take
  document and the Connect exported instead, writing started at once (~1.2 GB/min; that run was
  stopped, so completion is unverified).
- **Export only what the render shows.** The Viewport renderer uses EDITOR visibility: a cloner with
  editor visibility off is absent from a VP render even when render visibility is on. Read
  `ID_BASEOBJECT_VISIBILITY_EDITOR` (0 on, 1 off, 2 default — inherit) on the take document before
  exporting matching geometry. Probe a heavy generator first (`mograph.GeGetMoData(cloner).GetCount()`,
  cloned object, segments): 500k clones of an 8-segment sphere wrote ~330 MB per frame.
- Export recipe:
```python
for i, o in enumerate(objs): xdoc.SetActiveObject(o, c4d.SELECTION_NEW if i == 0 else c4d.SELECTION_ADD)
plug = c4d.plugins.FindPlugin(c4d.FORMAT_ABCEXPORT, c4d.PLUGINTYPE_SCENESAVER)
d = {}; plug.Message(c4d.MSG_RETRIEVEPRIVATEDATA, d); ex = d["imexporter"]
ex[c4d.ABCEXPORT_SELECTION_ONLY] = True
ex[c4d.ABCEXPORT_FRAME_START] = f0; ex[c4d.ABCEXPORT_FRAME_END] = f1; ex[c4d.ABCEXPORT_FRAME_STEP] = 1
ex[c4d.ABCEXPORT_GLOBAL_MATRIX] = True        # world-space points; NORMALS / UVS / CAMERAS off keeps it small
c4d.documents.SaveDocument(xdoc, out, c4d.SAVEDOCUMENTFLAGS_DONTADDTORECENTLIST, c4d.FORMAT_ABCEXPORT)
```
- Watch long exports from a shell (`stat` the file twice, check free disk).
- Fast camera sampling: `doc.ExecutePasses(None, True, True, False, c4d.BUILDFLAGS_NONE)` (caches
  off) evaluates animation without rebuilding generators.

## Working with the bridge (verified on the community plugin; mostly general)
- (community plugin) `execute_python_script` echoes EVERY top-level variable back — big lists blow the 1 MB result
  limit. Always wrap scripts in `def main(): ...` + `main()`. Big strings (e.g. Python tag code) go
  inside `main()` too.
- Put `import maxon` at the top of scripts that print take overrides, BaseTimes or other wrapped
  values — otherwise the call can fail with "maxon module needs to be imported first".
- (community plugin) Blocked keywords: `import os`, `subprocess`, `exec(`, `eval(` — stay within the c4d / maxon API.
  Plain `open(path, "w")` works: write bulk data (e.g. 1500 sampled frames) to a file in a folder the
  sandbox can stage, instead of printing it.
- Replies over ~50k characters are not shown inline; they are saved to a `tool-results/*.txt` JSON
  file — parse it in the sandbox (used for base64 render previews).
- **Main-thread timeout (60 s community plugin, 30 s default Maxon).** Anything that reloads heavy data (e.g. changing a parameter on an
  object reading a 2 GB Alembic) takes long — one such change per call, never a loop of them.
  `TakeToDocument` + `RenderDocument` of a 60 MB scene also timed out → use the Render Queue.
- **Never write an unbounded loop** (`while …:`) in a bridge script. Python runs on C4D's main thread
  and cannot be interrupted from outside: a loop that never ends freezes C4D until a force quit
  (happened with `while br.GetElementCount(): br.DelFile(0)`). Use `for i in range(n)` with a fixed n.
- A timed-out call may still be running. Check from a shell (`ps -axo pid,%cpu,state,comm`, output
  file mtimes) before sending another call; ~0% CPU + no answer = deadlock, ~100% = busy/looping.
  `sample <pid> 2` shows whether the main thread is inside the plugin's Python.
- Animated data: `doc.SetTime(c4d.BaseTime(f, fps)); doc.ExecutePasses(None, True, True, True, c4d.BUILDFLAGS_NONE)`.
  `CallCommand(12414)` (next frame) doesn't evaluate synchronously — step with SetTime+ExecutePasses.
- Wrap scene edits in `doc.StartUndo() / AddUndo(...) / EndUndo()` so the user can ⌘Z; `c4d.EventAdd()` after.
  Don't save their file unless asked.
- A script that errors midway leaves its earlier edits in place — inspect the scene before retrying.
- `doc.GetChanged()` is not proof of user edits: your own probe (set a value and restore it, or
  `SetTime` + `ExecutePasses`) sets it too (verified 2027.0). Before editing a document that reports
  changes, `LoadDocument` its file and compare user data, point lists, code and the `GetMl()` of
  objects without tracks (global matrices of animated objects differ only because of the time).
- Find objects by walking `GetDown()/GetNext()` and matching `GetName()`; toggle an object with
  `op[c4d.ID_BASEOBJECT_GENERATOR_FLAG] = False`. Names repeat (e.g. a hidden and a visible
  "Valve Left 1"): find under the right parent.
- **Insert objects with `doc.InsertObject(op, parent=p, pred=prev)`, never `op.InsertUnder(p)`** —
  InsertUnder'd objects silently broke the whole native particle sim (see `cinema4d-particles`).
- **`GetClone()` copies children** (objects AND render settings). Cloning a parent repeatedly while
  inserting the clones under it multiplies the tree — see `cinema4d-takes`.
- Objects that link to each other (camera → focus null), or objects + their materials copied between
  open documents: `trans = c4d.AliasTrans(); trans.Init(src)`, `GetClone(c4d.COPYFLAGS_NONE, trans)` for
  every material and object, insert, `trans.Translate(True)` — links point into the copies (verified).
- `render_preview` returned "No image data" in a Redshift scene — render with `RenderDocument`
  instead (see `cinema4d-render-preview`).
- The user may edit the open scene or switch the active document while you work. Re-read the hierarchy
  before structural edits; for read-only steps find documents by name (`GetDocumentName()` from
  `c4d.documents.GetFirstDocument()` / `GetNext()`) instead of using `doc`; for edits assert
  `doc.GetDocumentName()` first so a switch aborts cleanly. Clean up temporary objects/documents
  immediately (`c4d.documents.KillDocument`, then `SetActiveDocument` back to their file).
- **Before any temporary viewport change** (hiding objects, display modes, track display) record
  the original values and restore those — the user may have hidden things on purpose; resetting to
  "default" overrides their choice.
- Look through a camera without rendering: `bd = doc.GetActiveBaseDraw(); bd.SetSceneCamera(cam)`,
  `SetTime`, `c4d.DrawViews(c4d.DRAWFLAGS_ONLY_ACTIVE_VIEW | c4d.DRAWFLAGS_NO_THREAD | c4d.DRAWFLAGS_FORCEFULLREDRAW)`,
  then a background `computer_app_screenshot` of the C4D window (+ `computer_app_zoom` on the view).
- Cameras may carry a **Protection tag** that locks some position axes (e.g. X/Y locked, Z free =
  dolly-only). Keys on locked axes are silently ignored — read the tag before animating a camera.
- UI-only actions (Add to HUD, some buttons): computer use. On macOS the app resolves as
  `"Cinema 4D"` (bundle `net.maxon.cinema4d`); on Windows as `"Maxon Cinema 4D <year>"`
  (`computer_resolve_access` → `computer_request_access`). Background clicks into C4D windows are
  refused (no accessibility tree); screenshots and zooms work. A context-menu item may need two clicks.
- On Windows, Mac-only tools (`sips`) don't exist — use the in-memory render path in
  `cinema4d-render-preview`.
- **Baking MoGraph clone positions** (verified 2026.4): after `SetTime` + `ExecutePasses`,
  `cloner.GetCache()` is a Null whose children are the clones ("Type 1 0" … "Type 1 19", index =
  last word); `GetMg()` on objects inside them is world space. 20 clones × 841 frames took 7 s.
  Check against a frame with `render_preview_image(renderer="hardware")` (2.5 s) when Redshift is
  slow; RS lights inside clones made a Redshift preview sit at 0 % for 70 s.
- **Python Generator outputs** (verified 2026.4): clones of scene objects (`GetClone`) and nested
  generators (Extrude + Text spline) placed in the returned hierarchy render in Redshift; their
  caches only exist at render time, so `GetCache()` on them from a script returns None. Turn
  `OPYTHON_OPTIMIZE` off and cache by your own signature (include doc time for animation).
- Extrude in 2026: depth is `EXTRUDEOBJECT_EXTRUSIONOFFSET` (default **100 cm**);
  `EXTRUDEOBJECT_MOVE` is ignored — a "flat" text extrude needs the offset set near 0.
- Text spline font from Python: `bc = c4d.bitmaps.GeClipMap.GetFontDescription("IBMPlexMono",
  c4d.GE_FONT_NAME_POSTSCRIPT)`; `fd = c4d.FontData(); fd.SetFont(bc)`; `txt[c4d.PRIM_TEXT_FONT] = fd`.
- `c4d.utils.RotAxisToMatrix(axis, a)` turns opposite to the right-hand rule (left-handed space):
  to rotate direction a0 onto a1 with axis = a0 × a1, use −angle. Check `R.MulV(a0)` against a1.

## Saving and rendering (verified C4D 2026, macOS)
- **Save-As** (the open tab becomes the new file, the old file stays untouched):
```python
doc.SetDocumentName(new_name); doc.SetDocumentPath(folder)
c4d.documents.SaveDocument(doc, folder + "/" + new_name, c4d.SAVEDOCUMENTFLAGS_DONTADDTORECENTLIST, c4d.FORMAT_C4DEXPORT)
```
  Follow the user's versioning convention (e.g. bump a date suffix) instead of overwriting.
- **Render Queue** (async, survives the main-thread limit):
```python
br = c4d.documents.GetBatchRender()
br.AddFile(path, br.GetElementCount()); br.SetRendering(c4d.BR_START)   # returns immediately; AddFile(path, 0) puts the job on top
br.EnableElement(i, False)                                              # skip an old job (verified)
```
  - The queue renders the file **from disk**. By default it uses the take that was current when the
    file was saved; pick another take per job with `br.SetActiveTakeIndex(job, takeIndex, False)` —
    several jobs on the same file, one per take, no per-take file copies (recipe and binding quirks
    in `cinema4d-takes`). A take with no camera renders the editor "Default Camera".
  - Status codes (`c4d.RM_*`): 1000 PROGRESS, 1001 FINISHED, 1002 STOPPED, 1003 ERROR, 1004 ERROR2,
    1005 PAUSED, 1006 QUEUE, 1007 PROGRESS_WITH_WARNING, 1008 NONE. `br.GetJsonJobs()` gives every
    job's status, message ("Error - Missing Files"), progress and output path — read errors there.
  - **"Error - Missing Files" although every texture resolves:** `br.SetCheckTexture(False)`, then
    `BR_START` again — the errored job re-ran and finished (verified C4D 2026, macOS).
  - `GetAllTakeNames(job)` lists the takes in `SetActiveTakeIndex` order (depth-first, `Main` = 0).
    The getters `GetActiveTakeIndex` / `GetActiveTakeName` / `GetActiveCameraName` take
    `(job, filename)` — called with the job alone they raise "Required argument 'filename'".
  - **Never call `br.SetRendering(c4d.BR_STOP)` from the bridge** — it deadlocked C4D (0% CPU, UI
    frozen, force quit needed). Ask the user to stop renders in the Render Queue window.
  - **Don't loop on `DelFile`** — it did not remove a waiting job. Disable old jobs instead.
  - Watch progress from a shell (output file size/mtime); bridge calls can block while a job loads.
  - **Queue calls load the scene file on C4D's main thread**: `AddFile`, `GetAllTakeNames`,
    `GetActiveTakeName`. With a heavy file (65 MB + 25 Alembic particle groups) 24 jobs took ~2 min
    and a second listing call that asked each job's take froze the UI again ("Not Responding", but
    reading ~27 MB/s — busy, not dead; wait it out, never kill). Fill a big queue in one call, read
    back with `GetElement`/`GetElementStatus`/`GetJsonJobs()` only, and warn the user first.
    `BatchRender` has `SetUseNet` (Team Render) but no `GetUseNet`.
  - **"Error – Saving Image"**: the queue doesn't create missing output folders (Commandline does) —
    create `<shot>/<take>/` folders before starting. **"Error – Missing Files"** also flags absolute
    paths from another machine (`/Users/...`) that `GetAllAssetsNew` resolves by name: relink them
    project-relative (`tex/...`), or `SetCheckTexture(False)` when the missing files are unused.
- **Render settings frame rate:** `RDATA_FRAMERATE` is ignored while "Use Project Frame Rate"
  (param id `5023`) is on — set `rd[5023] = False` first, on the parent render settings too (a child
  followed its parent). Use this to render 30 fps from a 60 fps scene.
- IDs seen: Viewport renderer `RDATA_RENDERENGINE = 300001061`; `RDATA_FORMAT = 1125`
  (`FILTER_MOVIE`) wrote an .mp4 on macOS. Absolute output paths are safest; a Windows path like
  `./D:/…` saved on Windows is treated as relative on macOS.
- ACEScg EXR like the user's renders: RenderData Format 1016606 (OpenEXR), `[5077]` Depth 2 (32-bit),
  `[5036]` Alpha on, `[5038]` Straight off (premultiplied), `[5219]` Bake View Transform off,
  `[28507]` profile Linear. Setting `RDATA_FORMATDEPTH = RDATA_FORMATDEPTH_16` on it raised
  "parameter set failed". `doc.GetActiveOcioColorSpacesNames()` → (render, display, view,
  thumbnail view), e.g. ('ACEScg', 'sRGB', 'ACES 1.0 SDR-video', …); it returned empty strings for a
  document that wasn't the active one.

## Keys from Python (verified C4D 2026)
- Explicit tangents on a spline key: clear `NBIT_CKEY_AUTO` (and `NBIT_CKEY_CLAMP`), set
  `NBIT_CKEY_BREAK`, then `key.SetTimeLeft(curve, c4d.BaseTime(-h/3, fps))`, `SetValueLeft(curve, -s*h/3)`,
  `SetTimeRight` / `SetValueRight` (offsets from the key). Slope `s` is value per frame; `h` = gap to
  the neighbour key. `NBIT_CKEY_ZERO_O` / `ZERO_A` don't exist in 2026 (AttributeError) — guard
  optional bits with `getattr`. Print `curve.GetValue(BaseTime)` samples and per-frame speeds to verify.
- Ease a move past its last key without touching what comes before (e.g. a camera that should keep
  drifting): keep the key value, give it a small continuing slope on both sides, add a new end key
  with value + delta and zero slope (delta = slope × gap / 2 gives a clean ease-out), delete a
  trailing hold key.
- `BaseContainer.GetClone()` needs a flags argument in 2026 (`GetClone(c4d.COPYFLAGS_NONE)`).

## Testing without touching the user's project (verified)
- For import/attribute questions, work in a throwaway `c4d.documents.BaseDocument()` (MergeDocument
  into it, ExecutePasses, read) — nothing lands in the open scene.
- **But a Python-created blank document is not fully initialised** for Alembic particles: it can show
  data a real scene never will (particle colour channel). Native particle simulations (emitters,
  modifiers, forces) do run correctly in a blank `BaseDocument()` — fine as a sandbox for those.
  For Alembic-particle or scene-dependent questions, test in an in-memory copy of the real file:
  `c4d.documents.LoadDocument(path, SCENEFILTER_OBJECTS | SCENEFILTER_MATERIALS, None)` — never
  inserted into the document list, so the open file is untouched. Also the cheap way to inspect files
  the user has not opened (cameras, takes, render settings).
- Bisect a scene-dependent problem on such a copy: remove top-level objects one at a time, then
  materials; compare document parameters and scene hooks (`doc.GetBranchInfo()` → "Scene Hooks").

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

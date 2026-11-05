---
name: cinema4d-mcp
description: Core rules for driving Cinema 4D through the cinema4d MCP server (github.com/ttiimmaacc/cinema4d-mcp) — installing and configuring it on macOS and Windows (uv venv, mcp pin, versioned plugin folder, Claude Desktop config), Python bridge rules (result-size limit, 60 s main-thread timeout, undo, safe object insertion, safe test documents, UI-only steps via computer use), and the index of Cinema 4D sub-skills. Use EVERY time a task touches Cinema 4D via MCP, or when a C4D MCP tool fails.
---

# Cinema 4D via MCP — core

## Sub-skills — load the one that matches the task
- `cinema4d-alembic` — Alembic import from Python, importer options, frame/scale checks, Particle
  Groups vs Thinking Particles, attribute mapping, reading particle data.
- `cinema4d-redshift` — Redshift node materials through the maxon API, node/port IDs, RS Object tag,
  test renders with pixel checks, known dead ends.
- `cinema4d-particles` — native 2024+ particle system: emitters, groups, Data Mapper/Math/Look
  modifiers, forces with measured units, Cloner on particles, RS rendering, sim traps.
- `cinema4d-rigging` — control nulls with user data, Python tag drivers, self-updating dropdowns,
  spline travel, HUD, procedural splines/meshes.
- `cinema4d-render-preview` — look at renders from the sandbox: clone → step sim → RenderDocument →
  base64 JPEG, contact sheets, reference-video comparison, viewport screenshots.
- `cinema4d-takes` — reading/creating takes, overrides (incl. user data), override groups,
  per-take camera/render data, verifying/rendering a take via TakeToDocument.
- `cinema4d-motion-tracker` — Motion Tracker: reading 2D tracks/solve, why a solve stops, running
  the solver from a script, extending a solve past an occlusion, real-world scale, baking a camera.
- `houdini-to-cinema4d` — the Houdini side of the Alembic hand-off (export recipe, verification).
- `project-notes` — per-production notes (scene map, state) kept outside the skills.

## Maxon's own MCP adapter (verified C4D 2026.4, adapter 1.0.0.22, Windows)
C4D 2026.4 ships `mxn_plugins/mcp_adapter` (stdio relay to `http://127.0.0.1:5556/mcp`); its tools
(`ping`, `list_entities`, `get/set_parameters`, `exec_python`, `capture_viewport`, …) differ from the
socket plugin described below. Notes:
- `exec_python(code, undo=true)` records nothing by itself: call `add_undo_create(op)` /
  `add_undo_change(op)` before each edit. `SetTime` alone triggers a harmless "not undoable" warning.
- File writes with `open()` work there — export JSON and do heavy maths locally.
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
- **Rendering to disk** (verified 2026.4): `start_render(output_path=…exr)` wrote a 3-channel EXR
  (alpha dropped); without `output_path` it uses the RenderData save settings and wrote RGBA. A
  save path with `$prj` turns spaces in the scene name into underscores and creates that folder.
  Render Queue from Python: `br = c4d.documents.GetBatchRender()`, `br.AddFile(path, 0)` puts a job
  on top, `br.SetRendering(c4d.BR_START)`; status 1006 = queued, 1004 = error (others' jobs stay).
- **After a C4D upgrade (2026.4 → 2027.0, verified)** the new version's MCP adapter was not listening
  (nothing on 127.0.0.1:5556) — check the port before trying tools; the user has to switch it on
  again in the new version. Renders can continue without it through the bundled command-line renderer,
  which runs next to the open GUI:
  `"C:/Program Files/Maxon Cinema 4D 2027/Commandline.exe" g_licenseModel=LICENSEMODEL::MAXONAPP
  -render "scene.c4d" -frame 48 242 -oimage "D:\out\Name_"` (stdin from /dev/null, log to a file,
  run in the background). It keeps the scene's format/alpha (RGBA float32 EXR) and names frames
  `Name_0048.exr`; the log ends each frame with "Rendering successful: N sec." Before continuing a
  sequence across versions, render one already-finished frame to a scratch folder and diff it: a
  Redshift line scene came out bit-identical in 2027.0 vs 2026.4.
- **Changing a scene with no MCP** (verified 2027.0): `c4dpy.exe g_licenseModel=LICENSEMODEL::MAXONAPP
  script.py …` can `LoadDocument(path, SCENEFILTER_OBJECTS | SCENEFILTER_MATERIALS)`, set a Python
  Generator's user data by name (`for did, bc in op.GetUserDataContainer(): bc[c4d.DESC_NAME]`),
  and `SaveDocument(doc, copy, SAVEDOCUMENTFLAGS_DONTADDTORECENTLIST, FORMAT_C4DEXPORT)` to a
  scratch copy; render settings and links survive, and a Commandline render of the copy matched the
  original pixel for pixel outside the changed elements. Don't save over a scene the user has open
  in the GUI — their next save silently overwrites it; give them the values to type instead.
  Which document is in front shows in the window title: `tasklist //V //FI "IMAGENAME eq Cinema 4D.exe"`
  → `Cinema 4D 2027.0.0 - [02 Satellite Data Flow.c4d] - Main`. `LoadDocument` returns None (no
  error) for a missing path — users rename scenes (here "Ship Data Flow.c4d" → "02 Ship Data
  Flow.c4d"), so list the folder first; a renamed scene also renames its `$prj` output folder.
- ACEScg EXR like the user's renders: RenderData Format 1016606 (OpenEXR), `[5077]` Depth 2 (32-bit),
  `[5036]` Alpha on, `[5038]` Straight off (premultiplied), `[5219]` Bake View Transform off,
  `[28507]` profile Linear. Setting `RDATA_FORMATDEPTH = RDATA_FORMATDEPTH_16` on it raised
  "parameter set failed". `doc.GetActiveOcioColorSpacesNames()` → (render, display, view,
  thumbnail view), e.g. ('ACEScg', 'sRGB', 'ACES 1.0 SDR-video', …); it returned empty strings for a
  document that wasn't the active one.
- `c4d.utils.RotAxisToMatrix(axis, a)` turns opposite to the right-hand rule (left-handed space):
  to rotate direction a0 onto a1 with axis = a0 × a1, use −angle. Check `R.MulV(a0)` against a1.
- The user may switch the active document while you work: for read-only steps find documents by name
  instead of using `doc`; for edits assert `doc.GetDocumentName()` first so a switch aborts cleanly.
- Copy objects + their materials between open documents with links intact: `trans = c4d.AliasTrans();
  trans.Init(src)`, `GetClone(c4d.COPYFLAGS_NONE, trans)` for every material and object, then
  `trans.Translate(True)`, then insert into the target (texture tags point at the copied materials).
- `add_undo_change(doc)` does not capture document settings: `doc.DoUndo()` reverted the render data
  but left SetFps/SetMinTime/SetMaxTime changes in place. Get settings right first time; record old values.
- `add_undo_create` only works for the active document (`doc`); objects inserted into another open
  document are kept but the call errors and Ctrl-Z there won't remove them — say so.
- **Before any temporary viewport change** (hiding objects, display modes, track display) record
  the original values and restore those — the user may have hidden things on purpose; resetting to
  "default" overrides their choice.

## What it is (reviewed Sep 2026, commit 6bab376)
- C4D plugin `c4d_plugin/mcp_server_plugin.pyp`: socket server on **127.0.0.1:5555** only.
- Python MCP server (`main.py`, deps `mcp`, `starlette`), no outbound network calls.
- Tools: scene info, add/modify/list objects, materials, `inspect_redshift_materials`,
  render_frame/preview, keyframes, save/load scene, MoGraph, dynamics, cameras, lights,
  `execute_python_script`. In practice nearly everything goes through `execute_python_script`.

## Install on macOS — VERIFIED working (Sep 2026, C4D 2026, mcp 1.30.0)
```bash
cd ~/cinema4d-mcp
~/.local/bin/uv venv && ~/.local/bin/uv pip install -e .
~/.local/bin/uv pip install --python ~/cinema4d-mcp/.venv/bin/python "mcp>=1.2,<2"   # see pitfalls
P="$(ls -d "$HOME/Library/Preferences/Maxon/Maxon Cinema 4D 2026_"*/ | head -1)plugins"   # suffix differs per install
mkdir -p "$P" && cp c4d_plugin/mcp_server_plugin.pyp "$P/"
```
Config entry (goes INTO `~/Library/Application Support/Claude/claude_desktop_config.json` →
`mcpServers`; pasting it into zsh gives `parse error near '}'`):
`"cinema4d": {"command": "/Users/<you>/cinema4d-mcp/.venv/bin/python", "args": ["/Users/<you>/cinema4d-mcp/main.py"]}`
(absolute paths — `~` is not expanded there).
In C4D: Extensions → Socket Server Plugin → Start Server. After a Claude restart the tools reach the
**same conversation** — find them with `tool_search("cinema4d")`.

## Install pitfalls (verified)
- `pip3 install -e .` fails (Homebrew Python, PEP 668 externally-managed) → use `uv` as above.
- **`mcp` 2.x breaks this repo** (pyproject only says `mcp>=1.2.0`): the server exits with
  `No module named 'mcp.server.fastmcp'` right after "Successfully connected to Cinema 4D socket".
  Pin `mcp<2`; check with `.venv/bin/python -c "from mcp.server.fastmcp import FastMCP"`.
- Plugin folder is versioned (2025 folders also exist) — `mkdir -p` the 2026 one.
- `claude mcp add` configures **Claude Code**, not Claude Desktop.
- Server log: `~/Library/Logs/Claude/mcp-server-cinema4d.log` — first place to look.
- **Editing claude_desktop_config.json** is a persistent-config change: ask the user first, back it up,
  print only server names (it may hold secrets). **Claude Desktop overwrites the file with its
  in-memory copy when it quits** — edit only after the main process
  (`/Applications/Claude.app/Contents/MacOS/Claude`, PID via `ps -axo pid,comm`) has exited. Working
  method: one-shot background watcher waiting on that PID (`kill -0 $PID`) → backup → json load/set/
  tmp/validate/`os.replace` → `chmod 600` (rewriting resets it to 644) → `open -a Claude` → exit
  (30-min timeout). `pgrep -f '...MacOS/Claude$'` did NOT match the running app — use the PID.

## Working with the bridge (verified)
- `execute_python_script` echoes EVERY top-level variable back — big lists blow the 1 MB result
  limit. Always wrap scripts in `def main(): ...` + `main()`.
- Blocked keywords: `import os`, `subprocess`, `exec(`, `eval(` — stay within the c4d / maxon API.
- **60 s main-thread timeout.** Anything that reloads heavy data (e.g. changing a parameter on an
  object reading a 2 GB Alembic) takes long — one such change per call, never a loop of them.
- Animated data: `doc.SetTime(c4d.BaseTime(f, fps)); doc.ExecutePasses(None, True, True, True, c4d.BUILDFLAGS_NONE)`.
- Wrap scene edits in `doc.StartUndo() / AddUndo(...) / EndUndo()` so the user can ⌘Z; `c4d.EventAdd()` after.
  Don't save their file unless asked.
- A script that errors midway leaves its earlier edits in place — inspect the scene before retrying.
- Find objects by walking `GetDown()/GetNext()` and matching `GetName()`; toggle an object with
  `op[c4d.ID_BASEOBJECT_GENERATOR_FLAG] = False`.
- `render_preview` returned "No image data" in a Redshift scene — render with `RenderDocument`
  instead (see `cinema4d-render-preview`).
- **Insert objects with `doc.InsertObject(op, parent=p, pred=prev)`, never `op.InsertUnder(p)`** —
  InsertUnder'd objects silently broke the whole native particle sim (see `cinema4d-particles`).
- Replies over ~50k characters are not shown inline; they are saved to a `tool-results/*.txt` JSON
  file — parse it in the sandbox (used for base64 render previews).
- Big strings (e.g. Python tag code) go inside `main()`, otherwise they are echoed back.
- `CallCommand(12414)` (next frame) doesn't evaluate synchronously — step with SetTime+ExecutePasses.
- The user may edit the open scene while you work (lights, views, selection). Re-read the hierarchy
  before structural edits; clean up temporary objects/documents immediately
  (`c4d.documents.KillDocument`, then `SetActiveDocument` back to their file).
- UI-only actions (Add to HUD, some buttons): computer use on "Maxon Cinema 4D 2026"
  (`computer_resolve_access` → `computer_request_access`); a context-menu item may need two clicks.
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

## Testing without touching the user's project (verified)
- For import/attribute questions, work in a throwaway `c4d.documents.BaseDocument()` (MergeDocument
  into it, ExecutePasses, read) — nothing lands in the open scene.
- **But a Python-created blank document is not fully initialised** for Alembic particles: it can show
  data a real scene never will (particle colour channel). Native particle simulations (emitters,
  modifiers, forces) do run correctly in a blank `BaseDocument()` — fine as a sandbox for those.
  For Alembic-particle or scene-dependent questions, test in an in-memory copy of the real file: `c4d.documents.LoadDocument(path, SCENEFILTER_OBJECTS |
  SCENEFILTER_MATERIALS, None)` — never inserted into the document list, so the open file is untouched.
- Bisect a scene-dependent problem on such a copy: remove top-level objects one at a time, then
  materials; compare document parameters and scene hooks (`doc.GetBranchInfo()` → "Scene Hooks").

## Keeping this skill current
After any session that used Houdini/Cinema 4D via MCP, or whenever something new is verified:
1. Add gotchas/recipes ONLY if tested and working in a real scene; mark anything else "(unverified)".
2. Correct entries that proved wrong — don't append contradictions.
3. Put each finding in the skill it belongs to (see the indexes in `houdini-mcp` and `cinema4d-mcp`);
   project-specific facts go to that project's notes (see `project-notes`), never into a skill.
4. Keep each SKILL.md under ~300 lines; split into a new sub-skill or `references/` when it grows.
5. Re-package every changed skill (keep names) and, if the skills live in a git repo, commit and push.
   Tell the user in one line what changed.

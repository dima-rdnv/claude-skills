---
name: houdini-mcp
description: Core rules for driving SideFX Houdini through the houdini MCP bridge (execute_houdini_code, get_scene_info). Use EVERY time a task touches Houdini via MCP — inspecting scenes, building networks, sims, caching, exporting, flipbooks. Covers bridge timeouts, display-flag parking, hou API traps (expressions vs set(), menu tokens, node type names), Alembic/FBX import, installing the bridge (verified on Windows), how to keep the notes current, and an index of the specialised Houdini/C4D sub-skills to load alongside it.
---

# Houdini via MCP — core

Verified in Houdini 21 Indie (macOS) and Houdini 22.0.429 Indie (Windows, Python 3.13).
Prefer these notes over memory.
Default approach: use Houdini's native systems (POPs, stock SOPs/DOPs) over custom solutions;
faking is fine when abstract/art-directed; output is aimed at After Effects compositing or
Cinema 4D rendering.

## Sub-skills — load the one that matches the task
- `houdini-pop-particles` — POP sims: emission, collisions/containers, spray physics, clumping,
  speed ramps, diagnostics.
- `houdini-vdb-surfacing` — particles → VDB SDF → mesh blobs with transferred colour.
- `houdini-network-layout` — network boxes, sticky notes, comments, safe cleanup of unused nodes.
- `houdini-flipbook` — viewport flipbooks to PNG sequences.
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
  relaunch via `Get-StartApps` AUMID. Entry: command = venv `python.exe`, args = [bridge path].
- Cowork on Windows: terminals are click-only for computer use and the desktop Filesystem MCP
  tools fail (draft-07 outputSchema error). Working method: write files with `device_bash` into a
  connected folder, give the user one PowerShell command to run.
- After the relaunch the tools appear in the SAME conversation as `mcp__remote-devices__houdini__*`.
- This bridge version also has dedicated tools (create_node, set_parameters, connect_nodes,
  get_geometry_info, cook_node, find_error_nodes, render_single_view, create_wrangle…) and calls
  `execute_houdini_code` a last resort; the recipes below use `execute_houdini_code` (dedicated
  tools unverified).

## Working with the bridge

- Always start with `get_scene_info`, then inspect with `execute_houdini_code` printing JSON.
- If the bridge errors "Could not connect ... localhost:9876", ask the user to start the Houdini-side
  plugin (Windows: the MCP shelf button; console shows "HoudiniMCP server started on 127.0.0.1:9876").
- **Timeouts:** loops over every prim for many frames (e.g. 30 frames × 150k prims) time out the bridge.
  Sample a few frames, subsample points (`pts[::step]`), or compare bboxes instead.
- Node type names in Python are not always the UI names. Before `createNode`, list the category:
  `hou.sopNodeTypeCategory().nodeTypes().keys()` / `hou.dopNodeTypeCategory()...` and grep.
  Examples: "Transform Pieces" = `xformpieces`; POP Source = `popsource::2.0`; POP Solver = `popsolver::2.0`.
- Menu parms need their tokens, not labels: read `parm.parmTemplate().menuItems()` first.
- **`parm.set()` does NOT override an expression-driven parm** (verified twice): ROP `f1/f2` are
  `$FSTART/$FEND`, the Alembic SOP `frame` is `$FF`. Always `parm.deleteAllKeyframes()` first, then
  `set()`, then check `parm.rawValue()`. (A 571–1400 export silently wrote the full 1–3600 range.)
- DOP nodes have no `setRenderFlag` (only display flag). DOP nodes have no `maxNumInputs`; use `inputLabels()`.
- Wrap each build step in one script and print a verification (counts, bbox, a few sampled values) at the end.
- **A script that errors stops at the error line — everything after it did NOT run.** Re-check parms
  you meant to set after any failed call (a spray kept full-scale velocity this way).
- **Bridge timeout ≈ 15–20 s per call.** Step heavy sims in 100–150-frame chunks. If a call times
  out, Houdini keeps cooking: poll `hou.frame()` with a tiny call until it answers, then continue.
- **FIRST STEP OF EVERY SESSION: park the display flag on a node without the sim** (e.g. the
  animated Alembic) and restore the user's display node at the end. Violated twice in one session.
- **Never jump the timeline while a sim is in the displayed network.** `hou.setFrame(3600)` with a
  displayed merge that includes the dopnet makes the viewport cook the whole sim up to that frame
  (verified: hung Houdini for minutes, bridge stopped answering). Before probing animated geometry
  across frames, move the display flag to a node without the sim, or read the geometry with
  `node.geometryAtFrame(f)` if available, then restore the flag. If Houdini hangs, ask the user to
  press Esc in Houdini to interrupt the cook.
- **VEXpression variable names** for any POP node's local-expression parm:
  `vexpressionmenu.buildSnippetMenu('<nodetype>/<parm>', kwargs={'node':n,'parm':n.parm(p)})`
  lists presets that reveal them (popwind: `wind`, `windspeed`, `airresist`, `amp`, `swirlsize`;
  popspeedlimit: `speedmin`, `speedmax`, `spinmin`, `spinmax`; popcolor: `ramp`).
- `chf("parm", time)` inside a per-particle VEXpression is very slow. Precompute per-frame values
  as spare parms with hscript `bbox()` expressions (use a `timeshift` SOP for the previous frame).
- VEX: `point(0,"P",i)[1]` is an "ambiguous call" error — assign to `vector p` first, then `p.y`.

## FBX / Alembic

- `kinefx::fbxanimimport` carries animation on a skeleton; the static `file` SOP geo does not move.
  Rebuilding motion with `xformpieces` is fragile (FBX unit conversion scaled positions ~10× but not
  motion). **Preferred: an Alembic export of the animated asset**, retimed with `simple_retime`.
- Alembic pieces are identified by the prim `path` attribute (leaf names end in `Shape`).
- Unpack packed Alembic prims (`unpack`) before using them as a collider; they arrive as PolySoups →
  `convert` to polygons.
- **Check that parts actually animate before planning around them** (sample the part's bbox every
  ~300 frames). Verified case: an engine Alembic had an animated piston/crank but static valves.

## Keeping this skill current
After any session that used Houdini/Cinema 4D via MCP, or whenever something new is verified:
1. Add gotchas/recipes ONLY if tested and working in a real scene; mark anything else "(unverified)".
2. Correct entries that proved wrong — don't append contradictions.
3. Put each finding in the skill it belongs to (see the indexes in `houdini-mcp` and `cinema4d-mcp`);
   project-specific facts go to that project's notes (see `project-notes`), never into a skill.
4. Keep each SKILL.md under ~300 lines; split into a new sub-skill or `references/` when it grows.
5. Re-package every changed skill (keep names) and, if the skills live in a git repo, commit and push.
   Tell the user in one line what changed.

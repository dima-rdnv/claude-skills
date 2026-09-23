---
name: cinema4d-mcp
description: Core rules for driving Cinema 4D through the cinema4d MCP server (github.com/ttiimmaacc/cinema4d-mcp) — installing and configuring it on macOS (uv venv, mcp pin, versioned plugin folder, Claude Desktop config), Python bridge rules (result-size limit, 60 s main-thread timeout, undo, safe test documents), and the index of Cinema 4D sub-skills. Use EVERY time a task touches Cinema 4D via MCP, or when a C4D MCP tool fails.
---

# Cinema 4D via MCP — core

## Sub-skills — load the one that matches the task
- `cinema4d-alembic` — Alembic import from Python, importer options, frame/scale checks, Particle
  Groups vs Thinking Particles, attribute mapping, reading particle data.
- `cinema4d-redshift` — Redshift node materials through the maxon API, node/port IDs, RS Object tag,
  test renders with pixel checks, known dead ends.
- `houdini-to-cinema4d` — the Houdini side of the Alembic hand-off (export recipe, verification).
- `project-notes` — per-production notes (scene map, state) kept outside the skills.

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
  instead (see `cinema4d-redshift`).

## Testing without touching the user's project (verified)
- For import/attribute questions, work in a throwaway `c4d.documents.BaseDocument()` (MergeDocument
  into it, ExecutePasses, read) — nothing lands in the open scene.
- **But a Python-created blank document is not fully initialised** (simulation system): it can show
  data a real scene never will (particle colour channel). For anything simulation/particle related,
  test in an in-memory copy of the real file: `c4d.documents.LoadDocument(path, SCENEFILTER_OBJECTS |
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

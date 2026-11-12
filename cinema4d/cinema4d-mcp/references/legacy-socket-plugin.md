# Legacy: community socket plugin (verified Sep 2026, C4D 2026, mcp 1.30.0)

On C4D 2026.4+ use Maxon's built-in server (see `../SKILL.md`). This is
[ttiimmaacc/cinema4d-mcp](https://github.com/ttiimmaacc/cinema4d-mcp), for older versions. Step by step
for Windows and macOS: `../SETUP.md`.

## What it is (reviewed Sep 2026, commit 6bab376)
- C4D plugin `c4d_plugin/mcp_server_plugin.pyp`: socket server on **127.0.0.1:5555** only.
- Python MCP server (`main.py`, deps `mcp`, `starlette`), no outbound network calls.
- Tools: scene info, add/modify/list objects, materials, `inspect_redshift_materials`,
  render_frame/preview, keyframes, save/load scene, MoGraph, dynamics, cameras, lights,
  `execute_python_script`. In practice nearly everything goes through `execute_python_script`.

## Install on macOS
```bash
cd ~/cinema4d-mcp
~/.local/bin/uv venv && ~/.local/bin/uv pip install -e .
~/.local/bin/uv pip install --python ~/cinema4d-mcp/.venv/bin/python "mcp>=1.2,<2"   # see pitfalls
P="$(ls -d "$HOME/Library/Preferences/Maxon/Maxon Cinema 4D 2026_"*/ | head -1)plugins"   # year and suffix differ per install
mkdir -p "$P" && cp c4d_plugin/mcp_server_plugin.pyp "$P/"
```
Config entry (goes INTO `~/Library/Application Support/Claude/claude_desktop_config.json` →
`mcpServers`; pasting it into zsh gives `parse error near '}'`):
`"cinema4d": {"command": "/Users/<you>/cinema4d-mcp/.venv/bin/python", "args": ["/Users/<you>/cinema4d-mcp/main.py"]}`
(absolute paths — `~` is not expanded there).
In C4D: Extensions → Socket Server Plugin → Start Server, again after every C4D restart (check
`lsof -nP -iTCP:5555 -sTCP:LISTEN`). After a Claude restart the tools reach the **same conversation** —
find them with `tool_search("cinema4d")`.

## Pitfalls (verified)
- `pip3 install -e .` fails (Homebrew Python, PEP 668 externally-managed) → use `uv` as above.
- **`mcp` 2.x breaks this repo** (pyproject only says `mcp>=1.2.0`): the server exits with
  `No module named 'mcp.server.fastmcp'` right after "Successfully connected to Cinema 4D socket".
  Pin `mcp<2`; check with `.venv/bin/python -c "from mcp.server.fastmcp import FastMCP"`.
- The plugin folder is versioned (older folders also exist) — `mkdir -p` the current one. A new C4D
  version needs the plugin copied again.
- `claude mcp add` configures **Claude Code**, not Claude Desktop.
- Server log: `~/Library/Logs/Claude/mcp-server-cinema4d.log` — first place to look.
- **Editing `claude_desktop_config.json` by hand** is a persistent-config change: ask the user first,
  back it up, print only server names (it may hold secrets). **Claude Desktop overwrites the file with
  its in-memory copy when it quits** — edit only after the main process
  (`/Applications/Claude.app/Contents/MacOS/Claude`, PID via `ps -axo pid,comm`) has exited. Working
  method: one-shot background watcher waiting on that PID (`kill -0 $PID`) → backup → json load/set/
  tmp/validate/`os.replace` → `chmod 600` (rewriting resets it to 644) → `open -a Claude` → exit
  (30-min timeout). `pgrep -f '...MacOS/Claude$'` did NOT match the running app — use the PID.

## Without any MCP server
The plugin speaks newline-delimited JSON on 127.0.0.1:5555, so a 10-line Python client in a shell drives
it: send `{"command": "execute_python", "code": "..."}` + `\n`, read one JSON line back (`output` holds
the printed text). Its sandbox namespace: `c4d`, `math`, `random`, `time`, `json`, `doc` (verified Nov
2026). The user must still press Start Server.

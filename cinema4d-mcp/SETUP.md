# Cinema 4D MCP: setup guide (Windows & macOS)

These steps connect Claude Desktop to Cinema 4D through
[ttiimmaacc/cinema4d-mcp](https://github.com/ttiimmaacc/cinema4d-mcp). They were verified in
September 2026 with Cinema 4D 2026, server commit `6bab376` and `mcp` 1.30.0, on Windows and on
macOS.

## How it fits together

1. **C4D plugin** (`c4d_plugin/mcp_server_plugin.pyp`) opens a socket server inside Cinema 4D on
   `127.0.0.1:5555` (local only).
2. **MCP server** (`main.py`) is a small Python program that Claude Desktop starts. It talks to the
   plugin.
3. **Claude Desktop config** has one `cinema4d` entry that tells Claude how to start the server.

## Before you start

- Cinema 4D 2026, started at least once so that its preferences folder exists.
- Claude Desktop.
- The server code: `git clone https://github.com/ttiimmaacc/cinema4d-mcp.git`, or download the ZIP.
  Put it somewhere permanent, because Claude runs it from there.

Two things cost us the most time:

- **Pin `mcp` below version 2.** The server only asks for `mcp>=1.2.0`, so a fresh install pulls 2.x.
  Version 2 removed `FastMCP`, and the server dies with `No module named 'mcp.server.fastmcp'`.
- **Edit Claude's config only while Claude is fully quit.** Claude Desktop rewrites
  `claude_desktop_config.json` from memory when it quits, so an edit made while it runs is lost.

## Windows: one script

1. Clone or unzip `cinema4d-mcp`, for example to `Documents\Maxon\cinema4d-mcp`.
2. Copy [`windows/install-windows.ps1`](windows/install-windows.ps1) and
   [`windows/_claude_setup.py`](windows/_claude_setup.py) into that folder, next to `main.py`.
3. Run it in PowerShell:
   ```powershell
   powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\Documents\Maxon\cinema4d-mcp\install-windows.ps1"
   ```
4. When the script asks, quit Claude from the tray icon → **Quit**. Closing the window is not enough.
   The script then adds the server to Claude's config and reopens Claude.
5. Restart Cinema 4D, then go to **Extensions → Socket Server Plugin → Start Server**.

The script writes its log to `install.log` in the same folder. Step by step, it:

- copies the plugin into `%APPDATA%\Maxon\Maxon Cinema 4D 2026_<id>\plugins\`. It skips the
  `_c`/`_p`/`_s`/`_w` sibling folders;
- installs [uv](https://docs.astral.sh/uv/) if it's missing;
- creates a Python 3.12 environment in `%LOCALAPPDATA%\cinema4d-mcp\.venv` with `mcp>=1.2,<2` and
  `starlette`, then checks that the server imports;
- finds Claude's config. The Microsoft Store (MSIX) build keeps it in
  `%LOCALAPPDATA%\Packages\Claude_<id>\LocalCache\Roaming\Claude\`, other installs in
  `%APPDATA%\Claude\`;
- waits for Claude to quit, backs the config up as `.bak-<date>`, adds the entry and reopens Claude.

The entry it writes:

```json
"cinema4d": {
  "command": "C:\\Users\\<you>\\AppData\\Local\\cinema4d-mcp\\.venv\\Scripts\\python.exe",
  "args": ["C:\\Users\\<you>\\Documents\\Maxon\\cinema4d-mcp\\main.py"]
}
```

For a Cinema 4D version other than 2026, change `2026` in the script's prefs-folder pattern.

## macOS: a few commands and one config edit

1. Install [uv](https://docs.astral.sh/uv/) if needed: `curl -LsSf https://astral.sh/uv/install.sh | sh`.
   Homebrew's `pip3` refuses to install here (`externally-managed-environment`).
2. Build the environment and install the plugin:
   ```bash
   cd ~/cinema4d-mcp                      # wherever you cloned it
   uv venv && uv pip install -e .
   uv pip install --python .venv/bin/python "mcp>=1.2,<2"
   P="$(ls -d "$HOME/Library/Preferences/Maxon/Maxon Cinema 4D 2026_"*/ | head -1)plugins"
   mkdir -p "$P" && cp c4d_plugin/mcp_server_plugin.pyp "$P/"
   ```
3. Quit Claude Desktop with ⌘Q.
4. Open `~/Library/Application Support/Claude/claude_desktop_config.json` in a text editor. Add this
   inside `"mcpServers"`, using absolute paths because `~` is not expanded there:
   ```json
   "cinema4d": {
     "command": "/Users/<you>/cinema4d-mcp/.venv/bin/python",
     "args": ["/Users/<you>/cinema4d-mcp/main.py"]
   }
   ```
5. Reopen Claude. Restart Cinema 4D, then go to **Extensions → Socket Server Plugin → Start Server**.

## Check that it works

- Ask Claude: *"Get the Cinema 4D scene info."* It should answer with the open scene's name, object
  count and frame range. This also works in a conversation that was already open before the restart.
- To test the Python side on its own, run the venv's python with
  `-c "from mcp.server.fastmcp import FastMCP"`. It should print nothing.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Server log shows `No module named 'mcp.server.fastmcp'` | `mcp` 2.x got installed. Pin `mcp>=1.2,<2` in the venv and restart Claude. |
| The `cinema4d` entry disappeared from the config | It was edited while Claude was running. Quit Claude fully and edit it again. |
| Tools can't connect to Cinema 4D | Start the socket server in C4D before asking Claude, and again after every C4D restart. |
| No Socket Server Plugin in the Extensions menu | The plugin is in the wrong prefs folder. Use `Maxon Cinema 4D 2026_<id>` itself, then restart C4D. |
| `claude mcp add` changed nothing in Claude Desktop | That command configures Claude Code, not Claude Desktop. |

On macOS the server log is `~/Library/Logs/Claude/mcp-server-cinema4d.log`.

Once the tools respond, load the [`cinema4d-mcp`](SKILL.md) skill for the rules of working through
the bridge.

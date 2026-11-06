# Calling the Maxon MCP server from a shell (verified 2027.0, adapter 1.0.0.26, Windows)

- plain HTTP to :5556 gets 401. Run Maxon's relay with its token file instead of
  handling the token: `python <C4D>/resource/mxn_plugins/mcp_adapter/scripts/stdio_relay.py
  http://127.0.0.1:5556/mcp --token-file %APPDATA%/Maxon/Maxon Cinema 4D 2027_<id>/prefs/mcp/token`,
  newline JSON-RPC: initialize → notifications/initialized → tools/call. An `exec_python` reply that
  times out after 30 s ("adapter dispatch timed out") keeps running in C4D — never resend.
  Verified 2027.0 (adapter 1.0.0.26, Windows): one relay process per call, the three messages written
  to its stdin at once, works for every tool; `exec_python` (`code`, `timeout_seconds`) answers with
  text content holding JSON `{"stdout": …, "warnings": [...]}`. Keep the code in a file and send it —
  a session whose own cinema4d tools disconnected kept working this way.
- Helper: `python -I scripts/c4d_mcp_call.py ping`, `… list_documents`, `… TOOL '{"json": "args"}'`,
  `… py script.py [timeout_s]` (sends the file as `exec_python`). It finds the newest installed C4D
  and that version's token (Windows paths).
- **Write scripts that contain Windows paths with the file-writing tool, not a shell heredoc.** In the
  Bash tool, `"\\03 …"` inside a quoted heredoc arrived as `"\03 …"` (a Python octal escape, so
  `LoadDocument` silently returned None), and `"…\\${N}_"` arrived as `"…\${N}_"`. Prefer
  `os.path.join(folder, name)` or raw strings in files written with Write/Edit (verified 2027.0).
- `c4d.documents.KillDocument` on the active document inside `exec_python` closes it fine, but the
  call then ends with "ReferenceError: the object 'c4d.documents.BaseDocument' is not alive" (the
  adapter's own `doc`); the script's stdout is intact. `SetActiveDocument` to another open one after.

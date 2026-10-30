---
name: unreal-mcp
description: Core rules for driving Unreal Editor (UE 5.8) from Claude — Epic's built-in Unreal MCP plugin (ModelContextProtocol + EditorToolset, tool-search mode with list_toolsets/describe_toolset/call_tool) plus Python remote execution for everything the toolsets don't cover (Sequencer, Movie Render Queue, bulk edits). Covers enabling and auto-starting the MCP server, registering it in Claude Code, the remote-execution helper script, viewport captures you can actually look at, editor crash traps, where the logs are, and an index of the Unreal sub-skills. Use EVERY time a task touches Unreal Engine / Unreal Editor / a .uproject.
---

# Unreal Editor via MCP + Python — core

Verified on Unreal Engine 5.8.4 (launcher build), Windows 11, Claude Code desktop app, Oct 2026.
Prefer these notes over memory. Anything not tested is marked *(unverified)*.

## Sub-skills — load the one that matches the task
- `unreal-materials-python` — building materials, material functions and parameter collections from
  Python (MaterialEditingLibrary), Custom HLSL nodes, injecting a function into existing materials,
  reading compile errors, a flat unshaded colour look.
- `unreal-ultra-dynamic-sky` — adding Ultra Dynamic Sky, setting its Blueprint variables via
  ObjectTools, locking exposure for renders.
- `project-notes` — per-production notes; read them at the start of any task on a named production.

## Two channels, use both
| | Unreal MCP (Epic plugin) | Python remote execution |
|---|---|---|
| What | `mcp__unreal__list_toolsets / describe_toolset / call_tool` | `scripts/ue_exec.py` runs any Python in the editor |
| Good for | viewport/asset captures, inspecting objects and Blueprint properties, material graph queries, actor/asset tools, logs | bulk spawning, Sequencer, Movie Render Queue, anything the toolsets lack, long scripts kept in files |
| Limits | no raw Python or console tool (`execute_tool_script` is a sandbox that only chains toolset tools; imports limited to json/math/re/...) | no images back; output = what the script prints |

The UE 5.8 Film/Video template also enables the **Remote Control** web API on :30010, but it refuses
`PythonScriptLibrary` ("cannot be accessed remotely") — don't use it as a Python channel.

## Enabling the Unreal MCP plugin (per project)
1. Add to the `.uproject` `Plugins` array (or Edit → Plugins, search "Unreal MCP"):
   `{"Name": "ModelContextProtocol", "Enabled": true}` and `{"Name": "EditorToolset", "Enabled": true}`.
   Both are Experimental. Other toolsets live in `Engine/Plugins/Experimental/Toolsets/`
   (PCGToolset, NiagaraToolsets, ConfigSettingsToolset, AllToolsets ...).
2. Auto-start the server: create `Config/DefaultEditorPerProjectUserSettings.ini` with
   ```ini
   [/Script/ModelContextProtocolEngine.ModelContextProtocolSettings]
   bAutoStartServer=True
   ServerPortNumber=8000
   ServerUrlPath=/mcp
   ```
   (The settings class is `config=EditorPerProjectUserSettings`; putting it in the project's Default
   layer avoids the editor overwriting `Saved/Config/...` while it is open.) Alternatives: console
   `ModelContextProtocol.StartServer [port]`, or launch with `-ModelContextProtocolStartServer`.
   `ModelContextProtocol.GenerateClientConfig ClaudeCode` writes a `.mcp.json` in the project dir.
3. Restart the editor (plugins only load at startup). Server: `http://127.0.0.1:8000/mcp`
   (binds localhost only; rejects non-localhost `Origin` headers).
4. Register in Claude Code from the folder the sessions run in:
   `claude mcp add --transport http --scope local unreal http://localhost:8000/mcp`
5. The tools appear only in a Claude session started AFTER registering; restarting Unreal makes the
   server briefly "still connecting" in the session, then it reconnects by itself.
- Quick health check without the tools: POST a JSON-RPC `initialize` to the URL with
  `Accept: application/json, text/event-stream`; a 200 with an `Mcp-Session-Id` header = alive.

### Using the toolsets
- `bEnableToolSearch` is on by default: only 3 native tools. Call `list_toolsets`, then
  `describe_toolset` (full JSON schemas), then `call_tool(toolset_name, tool_name, arguments)`.
- Toolset names are mixed style: `EditorToolset.EditorAppToolset`,
  `editor_toolset.toolsets.material.MaterialTools`, `editor_toolset.toolsets.object.ObjectTools`, ...
- Object refs are `{"refPath": "/Game/Map.Map:PersistentLevel.Actor_C_0"}`.
- **Every struct parameter in a schema must be passed, even "optional" ones** — omitting
  `annotations` or `captureTransform` fails with "needs a default value".
- `ObjectTools.list_properties` on a Blueprint actor returns a JSON schema of ALL variables
  (Ultra Dynamic Sky: ~1000 keys, 330 KB) — it lands in a tool-results file; parse it with Python,
  don't read it raw. Keys are the display names with a lower-case first letter
  (`"time of Day"`, `"cloud Coverage"`).

### Looking at the viewport
`EditorToolset.EditorAppToolset.CaptureViewport` returns a base64 PNG inside JSON (~3 MB) — always
too big for the context, so it is saved to a tool-results file. Decode and downscale it, then Read
the image:
```
python -I scripts/decode_capture.py <tool-result.txt> <out.png> 1400
```
Pass a `captureTransform` (location cm, rotation pitch/yaw/roll deg) to shoot from a fixed pose,
and `annotations` with zeros (`gridSpacing 0, maxLabelDistance 0, maxLabels 0, classFilter
{"refPath": ""}`) for a clean image. The image has the viewport's aspect ratio (a wide editor
viewport gives e.g. 1400x444).

## Python remote execution
- Enable: Project Settings → Plugins → Python → *Enable Remote Execution?* or in `DefaultEngine.ini`:
  ```ini
  [/Script/PythonScriptPlugin.PythonScriptPluginSettings]
  bRemoteExecution=True
  RemoteExecutionMulticastBindAddress=127.0.0.1
  ```
  (multicast group 239.0.0.1:6766, bound to localhost by default). Toggling it in the UI takes
  effect immediately; the ini route needs a restart.
- Client: `scripts/ue_exec.py` wraps Epic's
  `Engine/Plugins/Experimental/PythonScriptPlugin/Content/Python/remote_execution.py`. Run it with
  the engine's own Python and `-I`:
  ```
  "<UE>/Engine/Binaries/ThirdParty/Python3/Win64/python.exe" -I ue_exec.py script.py
  "<UE>/Engine/Binaries/ThirdParty/Python3/Win64/python.exe" -I ue_exec.py -c "import unreal; print(1)"
  ```
  Set `UE_ROOT` if the engine is not in `C:\Program Files\Epic Games\UE_5.8`.
- Code runs as a file (`MODE_EXEC_FILE`), so multi-line scripts work; `__file__` is not set —
  `sys.path.insert(0, r"<scripts dir>")` then `import` + `importlib.reload()` your own modules.
- The editor's Python is 3.11 with **numpy** available (UE 5.8); PIL is not guaranteed.
- A Python exception comes back as `COMMAND_FAILED` with the traceback.
- UE Python structs often take **no constructor kwargs** (`unreal.CustomInput(input_name=...)` →
  TypeError). Create empty, then `set_editor_property`. Some (e.g. `Vector4f`) expose no fields at
  all: use `.import_text("(X=1,Y=0,Z=0,W=0)")`.
- `SubobjectDataSubsystem.add_new_subobject` returns `(handle, fail_text)`; an empty fail text is
  truthy-looking — check `SubobjectDataBlueprintFunctionLibrary.is_handle_valid(handle)` instead.
  Adding an InstancedStaticMeshComponent to a plain `unreal.Actor` this way works.
- Editor-world parameter-collection values (what the viewport shows):
  `unreal.MaterialLibrary.set_scalar_parameter_value(editor_world, mpc, "Name", v)`.
- Console commands: `unreal.SystemLibrary.execute_console_command(editor_world, "r.Foo 1")`.

## Crash traps (each one killed the editor)
- **Never `EditorAssetLibrary.duplicate_asset()` a map and then `load_level()` it in the same
  session** → fatal "World Memory Leaks" (EditorServer.cpp). The duplicate stays in memory as
  standalone. Create levels with `LevelEditorSubsystem.new_level_from_template(new, template)`.
- After a crash a *CrashReportClientEditor* window stays open; the editor can be relaunched with
  `UnrealEditor.exe "<path>.uproject"` (launching without the Epic launcher skips its login —
  fine for editing; Fab needs the launcher).

## Logs and errors
- `<Project>/Saved/Logs/<Project>.log`. Search `Critical error`, `Fatal error` for crashes,
  `Failed to compile Material` (the error lines follow it) for shaders, `LogPython: Error`.
- Tip: note `wc -l` of the log before a script, then grep only the new lines.
- Saving a level may log "Unable to Check Out From Revision Control" with an auto-closed dialog even
  without source control; the package still saves.

## Helper scripts
- `scripts/ue_exec.py` — remote Python runner (file or `-c`).
- `scripts/decode_capture.py` — CaptureViewport / CaptureEditorImage result → PNG/JPG (needs PIL in
  the Python that runs it, e.g. the system Python).

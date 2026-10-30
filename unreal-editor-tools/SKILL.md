---
name: unreal-editor-tools
description: Giving the user one-click tools inside Unreal Editor 5.8 from Python — a custom menu in the Level Editor's main menu bar (ToolMenus), registering it at every editor start (PythonScriptPlugin StartupScripts), undoable actions (ScopedEditorTransaction), progress dialogs, message boxes that don't block your own remote calls, piloting actors and reading/setting the viewport camera, Game View for clean views. Load with unreal-mcp when the user wants to do something themselves in the editor (move a rig, re-run a bake) instead of asking you each time.
---

# One-click editor tools for the user (Python)

Verified Oct 2026, UE 5.8.4, editor driven through `ue_exec.py` (see `unreal-mcp`). Built for a
production where the user moves a camera rail and re-bakes an effect from a project menu.

## A menu in the main menu bar
```python
import unreal
menus = unreal.ToolMenus.get()
main = menus.find_menu("LevelEditor.MainMenu")
menu = menus.find_menu("LevelEditor.MainMenu.MyTools") or \
       main.add_sub_menu("MyTools", "", "MyTools", "My Tools", "tooltip")   # owner, section, name, label
menu.add_section("Rail", "Camera rail")                                      # section name, label
entry = unreal.ToolMenuEntry(name="Rebake", type=unreal.MultiBlockType.MENU_ENTRY)  # kwargs work here
entry.set_label("Re-bake")
entry.set_tool_tip("...")
entry.set_string_command(unreal.ToolMenuStringCommandType.PYTHON, "", "import my_menu; my_menu.rebake()")
menu.add_menu_entry("Rail", entry)        # same entry name replaces -> re-running register() is safe
menus.refresh_all_widgets()
```
The sub-menu's path is `LevelEditor.MainMenu.<name>`; it appears right after Help (verified with a
window screenshot). Keep the callbacks in a module (`import my_menu; my_menu.fn()`), with the module's
folder on `sys.path`.

## Run it at every editor start
`Config/DefaultEngine.ini`:
```ini
[/Script/PythonScriptPlugin.PythonScriptPluginSettings]
+StartupScripts=D:/Project/Scripts/startup/my_menu.py
```
Entries run as commands (`RunTimedStartupScript(..., bRunAsFile=false)`), so a path to a `.py` file is
executed as a file; use an absolute path without spaces. Runs before the first tick. For the session
you're in, just exec the same file over remote execution.

## Making actions safe for the user
- **Undo:** `with unreal.ScopedEditorTransaction("Start rail from view"):` and call `obj.modify()` on
  each actor / component before changing it. Verified: `TRANSACTION UNDO` (console) put a moved
  rail and its spline back exactly.
- **Progress:** `with unreal.ScopedSlowTask(n, "Baking...") as t: t.make_dialog(False); t.enter_progress_frame(1)`.
- **Message boxes block your remote calls:** `unreal.EditorDialog.show_message(title, text,
  unreal.AppMsgType.OK)` is modal — called from `ue_exec.py` it waits until someone clicks OK. Route
  every message through one helper with a module flag (`QUIET = True` in tests → `unreal.log` instead).
- Long work (a ~45 s bake) freezes the editor; say so in the tooltip.
- Re-running a setup script from a menu: `exec(compile(open(path).read(), path, "exec"),
  {"__name__": "x", "FIELD_ONLY": True})` — the dict is the script's globals, so `globals().get(...)`
  switches work, and anything it defines (e.g. a REPORT string) can be read back from the dict.

## Viewport camera and piloting
```python
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
loc, rot = ues.get_level_viewport_camera_info()          # what the user looks at (also while piloting)
ues.set_level_viewport_camera_info(loc, rot)
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
les.pilot_level_actor(actor); les.eject_pilot_level_actor()
les.editor_set_game_view(True)                           # = G: hides sprites, volume outlines, gizmos
```
- **Piloting an actor moves it with every mouse / WASD move in that viewport.** Never leave a pilot
  active after a test — the user may be using the viewport (verified: a rail moved 16 m while a test
  pilot was left on). Eject and check the actor's transform afterwards.
- Piloting a camera that is attached to a rig moves the CAMERA relative to its parent (an offset),
  not the rig. For "position the shot by flying there", read the viewport camera and move the rig to
  it ("Start rail from current view"), then zero the camera's offset.
- Sequencer's camera-cut lock keeps the viewport on the shot camera:
  `LevelSequenceEditorBlueprintLibrary.set_lock_camera_cut_to_viewport(False)` before piloting.
- Editor-only helpers (Blueprint sprites, PCG / post-process volume outlines, spline lines of selected
  actors) show up in viewport captures; Game View hides them and they never render in MRQ.

## Screenshots of the editor window (to check a menu)
`CaptureEditorImage` (MCP) works; or PowerShell `System.Drawing` + `GetWindowRect` of the
`UnrealEditor` process's main window, crop to the area you need. A maximised window can extend past
the screen, so its bottom bar may not be on screen.

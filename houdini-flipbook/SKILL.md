---
name: houdini-flipbook
description: Rendering Houdini viewport flipbooks to PNG sequences through MCP (resolution, frame range, dark background, output folder) and monitoring long flipbooks. Includes a timestamped output-folder convention (Assets/Flipbooks/YYMMDD HHMM index). Use when asked for a flipbook, playblast, viewport render or preview frames from Houdini. Load with houdini-mcp.
---

# Viewport flipbooks

## Recipe (verified: 1920×1080 PNGs)
```python
sv = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
vp = sv.curViewport()
prev = vp.settings().colorScheme()
vp.settings().setColorScheme(hou.viewportColorScheme.Dark)   # dark background
s = sv.flipbookSettings().stash()
s.frameRange((start, end)); s.frameIncrement(1)
s.output(os.path.join(out_dir, 'name_$F4.png'))
s.outputToMPlay(False)
s.useResolution(True); s.resolution((1920, 1080))
sv.flipbook(vp, s)
# vp.settings().setColorScheme(prev)   # restore, unless the user prefers it dark
```
- A dark background reads better for particles. If the user wants it kept dark, set it on all
  SceneViewer viewports: `for vp in pt.viewports(): vp.settings().setColorScheme(Dark)`.
- Flipbooks the CURRENT viewport view and the displayed node — set the display node first.
- It cooks frames in order, so sims build correctly, but the call blocks the bridge for minutes.
  Monitor from a separate shell tool (e.g. MacOS-MCP Shell, read-only): count files in the output
  folder, check size with `sips -g pixelWidth -g pixelHeight` (macOS).
- Suggested folder convention (check the project notes for the real root):
  `<project root>/Assets/Flipbooks/<YYMMDD HHMM> <index>/` (index starts at 1).
  Build the name from `datetime.now()` at start time; `os.makedirs(..., exist_ok=True)`.

## Keeping this skill current
After any session that used Houdini/Cinema 4D via MCP, or whenever something new is verified:
1. Add gotchas/recipes ONLY if tested and working in a real scene; mark anything else "(unverified)".
2. Correct entries that proved wrong — don't append contradictions.
3. Put each finding in the skill it belongs to (see the indexes in `houdini-mcp` and `cinema4d-mcp`);
   project-specific facts go to that project's notes (see `project-notes`), never into a skill.
4. Keep each SKILL.md under ~300 lines; split into a new sub-skill or `references/` when it grows.
5. Re-package every changed skill (keep names) and, if the skills live in a git repo, commit and push.
   Tell the user in one line what changed.

# Claude skills for Houdini, Cinema 4D, Unreal Engine, After Effects & Premiere Pro

[Agent Skills](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview) that teach
Claude to drive **SideFX Houdini**, **Maxon Cinema 4D** and **Unreal Engine** through MCP servers,
and **Adobe After Effects** and **Premiere Pro** through small file-based script bridges: particle
sims, VDB surfacing, Alembic hand-offs, native C4D particles, rigs and takes, Redshift materials,
Unreal materials built from Python, flipbooks, tidy node networks, retiming AE animation to a
voice-over, and relinking Premiere projects to transcoded media.

Everything here comes from real production sessions. A recipe gets in only after it has been tested
in a real scene. Anything else is marked *(unverified)*. Failed approaches are written down too, so
Claude doesn't try them again.

## Skills

| Skill | What it covers |
|---|---|
| [houdini-mcp](houdini-mcp/SKILL.md) | **Core.** Bridge install, timeouts, display-flag parking, `hou` API traps, FBX/Alembic import, index of Houdini sub-skills |
| [houdini-pop-particles](houdini-pop-particles/SKILL.md) | POP sims: collisions that actually contain particles, spray deceleration, clumping, speed ramps, diagnostics |
| [houdini-vdb-surfacing](houdini-vdb-surfacing/SKILL.md) | Particles → VDB SDF → mesh blobs with transferred colour |
| [houdini-network-layout](houdini-network-layout/SKILL.md) | Network boxes, sticky notes, comments, safe cleanup of "unused" nodes |
| [houdini-flipbook](houdini-flipbook/SKILL.md) | Viewport flipbooks to PNG sequences, monitoring long flipbooks |
| [houdini-to-cinema4d](houdini-to-cinema4d/SKILL.md) | Houdini side of the Alembic hand-off to C4D (attribute clean-up, scale, `width` vs `pscale`) |
| [cinema4d-mcp](cinema4d-mcp/SKILL.md) | **Core.** C4D MCP install ([setup guide for Windows & macOS](cinema4d-mcp/SETUP.md)), bridge rules, safe test documents, index of C4D sub-skills |
| [cinema4d-alembic](cinema4d-alembic/SKILL.md) | Alembic import from Python, frame/scale checks, particle attribute mapping |
| [cinema4d-redshift](cinema4d-redshift/SKILL.md) | Redshift node materials via the maxon API, node/port IDs, light-free emissive recipe, RS Object tag, verifiable test renders, dead ends |
| [cinema4d-particles](cinema4d-particles/SKILL.md) | Native particles (2024+): emitters, groups, Data Mapper/Math/Condition/Reproduce, measured forces, Cloner on particles, trail and burst recipes |
| [cinema4d-rigging](cinema4d-rigging/SKILL.md) | Control rigs: user data, keyed controls, Python tag drivers, self-updating dropdowns, spline travel, HUD, procedural geometry |
| [cinema4d-render-preview](cinema4d-render-preview/SKILL.md) | Looking at renders from the sandbox: stepped-clone renders to base64 JPEG, contact sheets, reference-footage comparison |
| [cinema4d-motion-tracker](cinema4d-motion-tracker/SKILL.md) | Motion Tracker: diagnosing a solve that stops, solver from Python, extending a camera solve past an occlusion (PnP + triangulation + bundle adjustment scripts), real-world scale from a person, baking a clean camera |
| [cinema4d-takes](cinema4d-takes/SKILL.md) | Takes: reading and adding overrides (incl. user data), override groups, per-take camera/render data, TakeToDocument |
| [unreal-mcp](unreal-mcp/SKILL.md) | **Core.** Epic's built-in Unreal MCP plugin (UE 5.8) + Python remote execution ([ue_exec.py](unreal-mcp/scripts/ue_exec.py)): enabling and auto-starting the server, toolset usage, viewport captures you can look at, crash traps, logs |
| [unreal-materials-python](unreal-materials-python/SKILL.md) | Materials, material functions and parameter collections from Python: Custom HLSL nodes, per-instance pivots, injecting a function into existing materials, data textures, compile errors, verified traps |
| [unreal-sequencer-python](unreal-sequencer-python/SKILL.md) | Level Sequences from Python: keyed cine camera, a camera on a movable rail (Camera Rig Rail), camera cut, animating a parameter collection, auto-play on Play, checking the result in PIE |
| [unreal-led-volume-rig](unreal-led-volume-rig/SKILL.md) | Multi-screen LED box / CAVE rigs: reading a C4D rig with c4dpy, C4D film offsets → UE sensor offsets, a level rig on a rail, one shot + MRQ preset per screen |
| [unreal-editor-tools](unreal-editor-tools/SKILL.md) | One-click tools for the user inside the editor: a custom main-menu entry registered at every start, undoable actions, progress / message dialogs, piloting and the viewport camera, Game View |
| [unreal-content-management](unreal-content-management/SKILL.md) | Reorganising content safely: batch moves and redirectors, tidying a level's Outliner, moving maps, World Partition / one-file-per-actor levels, what imported samples do to config, backups, folder colours |
| [unreal-ultra-dynamic-sky](unreal-ultra-dynamic-sky/SKILL.md) | Ultra Dynamic Sky from Claude: replacing a template sky, setting its Blueprint variables through MCP ObjectTools, locking exposure for renders |
| [aftereffects-bridge](aftereffects-bridge/SKILL.md) | After Effects without MCP: a file-based ExtendScript bridge ([ClaudeBridge.jsx](aftereffects-bridge/scripts/ClaudeBridge.jsx)), safe script hand-off, inspecting comps, preview renders, retiming keys to a VO, building UI layers |
| [premiere-bridge](premiere-bridge/SKILL.md) | Premiere Pro without MCP: a self-signed CEP panel ([panel/](premiere-bridge/panel)) that runs `.jsx` from an inbox, CEP 12 signing workaround, inspecting sequences and bins, safe frame export, relinking to transcoded media with before/after proof, HEVC settings that keep the picture identical |
| [vo-timing](vo-timing/SKILL.md) | Word-level voice-over timings (faster-whisper) → frame numbers |
| [project-notes](project-notes/SKILL.md) | How to keep per-production notes across sessions, separate from the skills |

The three **core** skills are meant to be loaded every time Claude touches that app. They point to
the sub-skills to load next.

## Requirements

- An MCP bridge for the app you want Claude to control:
  - Houdini: [capoomgit/houdini-mcp](https://github.com/capoomgit/houdini-mcp)
  - Cinema 4D: [ttiimmaacc/cinema4d-mcp](https://github.com/ttiimmaacc/cinema4d-mcp)
  - Unreal Engine 5.8: the engine's own experimental **Unreal MCP** plugin (`ModelContextProtocol`
    + `EditorToolset`) and Python remote execution — no third-party server (see `unreal-mcp`)
  - After Effects: no MCP needed — run the included
    [ClaudeBridge.jsx](aftereffects-bridge/scripts/ClaudeBridge.jsx) panel (see `aftereffects-bridge`)
  - Premiere Pro: no MCP needed — install the included CEP panel with
    [install.ps1](premiere-bridge/scripts/install.ps1) (see `premiere-bridge`; Windows, self-signed
    with Adobe's ZXPSignCmd because CEP 12 ignores debug mode)
- Tested with Houdini 21–22 Indie, Cinema 4D 2026, Unreal Engine 5.8, After Effects 2026, Premiere Pro 2026 and Redshift. Install notes, including the
  pitfalls we hit, are in `houdini-mcp` and `cinema4d-mcp`. For a step-by-step Cinema 4D setup on
  Windows or macOS, see [cinema4d-mcp/SETUP.md](cinema4d-mcp/SETUP.md).

## Installation

**Claude Code** — copy or symlink the skill folders into your skills directory:

```bash
git clone https://github.com/dima-rdnv/claude-skills.git
mkdir -p ~/.claude/skills
for d in claude-skills/*/; do cp -R "${d%/}" ~/.claude/skills/; done
```

**Claude apps (claude.ai / Desktop)** — zip a skill folder (the folder itself, containing
`SKILL.md`) and upload it in Claude's Skills settings. You can also use the
skill-creator's `package_skill` script to build `.skill` files.

## How the skills stay current

Each skill ends with a short *Keeping this skill current* section. It tells Claude to write down new
findings after a session: verified facts only, fixes to entries that turned out wrong, and each
finding in the skill it belongs to. Details about a specific production belong in private project
notes (see `project-notes`), never in a skill.

## Contributing

Issues and pull requests are welcome, especially recipes verified on other versions or platforms.
Please follow the same rule: say what you tested it on, and mark anything untested *(unverified)*.

## License

[MIT](LICENSE)

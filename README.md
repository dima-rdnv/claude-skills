# Claude skills for Houdini & Cinema 4D

[Agent Skills](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview) that teach
Claude to drive **SideFX Houdini** and **Maxon Cinema 4D** through MCP servers: particle sims,
VDB surfacing, Alembic hand-offs, Redshift materials, flipbooks and tidy node networks.

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
| [cinema4d-mcp](cinema4d-mcp/SKILL.md) | **Core.** C4D MCP install on macOS, bridge rules, safe test documents, index of C4D sub-skills |
| [cinema4d-alembic](cinema4d-alembic/SKILL.md) | Alembic import from Python, frame/scale checks, particle attribute mapping |
| [cinema4d-redshift](cinema4d-redshift/SKILL.md) | Redshift node materials via the maxon API, RS Object tag, verifiable test renders, dead ends |
| [vo-timing](vo-timing/SKILL.md) | Word-level voice-over timings (faster-whisper) → frame numbers |
| [project-notes](project-notes/SKILL.md) | How to keep per-production notes across sessions, separate from the skills |

The two **core** skills are meant to be loaded every time Claude touches that app. They point to
the sub-skills to load next.

## Requirements

- An MCP bridge for the app you want Claude to control:
  - Houdini: [capoomgit/houdini-mcp](https://github.com/capoomgit/houdini-mcp)
  - Cinema 4D: [ttiimmaacc/cinema4d-mcp](https://github.com/ttiimmaacc/cinema4d-mcp)
- Tested with Houdini 21–22 Indie, Cinema 4D 2026 and Redshift. Install notes, including the
  pitfalls we hit, are in `houdini-mcp` and `cinema4d-mcp`.

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

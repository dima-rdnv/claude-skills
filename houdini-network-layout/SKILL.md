---
name: houdini-network-layout
description: Making Houdini networks readable for other people via MCP — numbered network boxes, sticky notes, node comments, README notes, legacy boxes, grid layout, overlap checks — plus the safe way to delete "unused" nodes (path-reference scan). Use when asked to arrange, organise, annotate, tidy or clean up a Houdini graph. Load with houdini-mcp.
---

# Organising Houdini networks
## Organising networks (boxes, notes, comments) — verified

Goal: graphs readable by other people — numbered network boxes per stage, a sticky note in
each box, short node comments, a README note, unused nodes in a "Legacy - not used" box.
- **Moving a network box moves its contents.** Never `setPosition` a box after adding items.
  Recipe: `box = parent.createNetworkBox(name)`, `box.setAutoFit(False)`, `setPosition`/`setSize`
  on the EMPTY box, then `box.addItem(node)` / `box.addItem(note)`.
- `fitAroundContents()` does not account for sticky-note width — compute the rect yourself
  (nodes ≈ 1.2 × 0.35 units, + ~3.3 units to the right for a displayed comment, + note rect,
  + padding 0.35, + ~0.4 for the title bar).
- Sticky notes: `parent.createStickyNote(name)`, `setText`, `setPosition` (lower-left), `setSize`,
  `setColor`, `setTextColor`. List with `parent.stickyNotes()` (there is no `stickyNote(name)`).
- Node comments: `node.setComment(txt)` + `node.setGenericFlag(hou.nodeFlag.DisplayComment, True)`.
- Lay out on a grid (vertical step 1.2, columns ~7 apart), keep a free lane for long wires
  (e.g. to the display merge), then verify: no box-rect overlaps, no node displaced.
- Note path-based links (object paths, dopimport) in comments/notes — they have no wires.
- **Before deleting "unused" nodes, scan for path references** — a node with no output wires may
  still be read by `soppath`/object-path parms (verified failure: deleting an experiment node that
  `STATIC_chamber.soppath` still pointed at removed the chamber collider → 24% of fuel leaked).
  Scan: for every node in `parent.allSubChildren()`, for every string parm value starting with
  `/obj/`, check `hou.node(value)` exists; also grep values for the name you're about to delete.
  Re-verify the sim after any cleanup.

## Keeping this skill current
After any session that used Houdini/Cinema 4D via MCP, or whenever something new is verified:
1. Add gotchas/recipes ONLY if tested and working in a real scene; mark anything else "(unverified)".
2. Correct entries that proved wrong — don't append contradictions.
3. Put each finding in the skill it belongs to (see the indexes in `houdini-mcp` and `cinema4d-mcp`);
   project-specific facts go to that project's notes (see `project-notes`), never into a skill.
4. Keep each SKILL.md under ~300 lines; split into a new sub-skill or `references/` when it grows.
5. Re-package every changed skill (keep names) and, if the skills live in a git repo, commit and push.
   Tell the user in one line what changed.

---
name: project-notes
description: Loading and maintaining per-project notes for CG / motion-design productions across sessions — brief, storyboard beats, VO timings, scene and file map, pipeline conventions, verified state, deliverables, open tasks. Use at the START of any task on a named production (a client video, a shot, a campaign) to read its notes before touching scenes, and at the END to update them. Notes live in a separate, private notes folder as SLUG/NOTES.md; project data never goes into a skill.
---

# Project notes

Skills hold reusable know-how. Anything specific to one production (names, paths, timings,
decisions, current state) lives in that project's notes file instead.

## Where
- A private notes folder kept OUTSIDE the skills (ideally its own private git repo), e.g.
  `~/Documents/claude-project-notes/`. If the user hasn't set one up, ask where it should live and
  remember the answer.
- One folder per production: `<notes-folder>/<slug>/NOTES.md` (slug = short lowercase project name).
- List existing projects with `ls <notes-folder>` in any available shell tool; read with `cat`.

## When
- **Start of a task on a named production:** list the notes folder, read the matching NOTES.md,
  then work. If none exists and the work will span sessions, create one from the template below.
- **End of the session (or after a milestone):** update NOTES.md; if the folder is a git repo,
  `git add -A && git commit && git push`. No packaging needed — notes are not skills.

## Template (sections, keep the ones that apply)
Brief · Beats / storyboard · VO or music timings (with frame numbers + fps) · Scene map (DCC files,
node/object paths) · Pipeline & exports (file paths, frame ranges, scale and axis conventions) ·
Current state (verified numbers only) · Deliverables (where outputs went) · Decisions & per-project
preferences · Open tasks.

## Rules
- Verified facts only; mark anything else "(unverified)". Correct stale lines, don't append contradictions.
- General lessons (API traps, recipes) go to the relevant skill; project facts go here. When a project
  fact turns out to be a general rule, move it into a skill.
- Absolute paths are fine here. No credentials, contract terms or other sensitive client data.
- Never put project notes in a public repo.
- Keep NOTES.md under ~300 lines; split into `<slug>/<topic>.md` when it grows.

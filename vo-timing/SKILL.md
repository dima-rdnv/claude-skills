---
name: vo-timing
description: Extracting word-level timings from a voice-over audio file (mp3/wav) in the sandbox with faster-whisper and converting them to frames at the project fps, to key animation/simulation events to the words. Use when the user shares a VO/narration/audio and wants timings, beats or frame numbers.
---

# Voice-over timings
- Word-level VO timings: `pip install faster-whisper --break-system-packages`, model `base.en`,
  `transcribe(..., word_timestamps=True)`, convert seconds × fps to frames. Runs fine on CPU in the
  sandbox for a ~3 min file. Key sim events (bursts, ignition, exhaust) to the words.
- Frame numbers from seconds×fps are 0-based; Houdini frames are 1-based (+1); C4D is 0-based.
- To line words up with an animated part in Houdini, sample `prim.boundingBox()` of the one prim
  whose `path` ends with the part name at ~15 frames — never loop every frame.

## Keeping this skill current
After any session that used Houdini/Cinema 4D via MCP, or whenever something new is verified:
1. Add gotchas/recipes ONLY if tested and working in a real scene; mark anything else "(unverified)".
2. Correct entries that proved wrong — don't append contradictions.
3. Put each finding in the skill it belongs to (see the indexes in `houdini-mcp` and `cinema4d-mcp`);
   project-specific facts go to that project's notes (see `project-notes`), never into a skill.
4. Keep each SKILL.md under ~300 lines; split into a new sub-skill or `references/` when it grows.
5. Re-package every changed skill (keep names) and, if the skills live in a git repo, commit and push.
   Tell the user in one line what changed.

# Is C4D stalled or just busy? Check from outside (verified 2027.0, Windows)

Asked "is C4D stuck, should I restart?" — answer from outside the app, without sending work into it:

1. Process: `Get-Process "Cinema 4D"` → `Responding`, CPU over a few seconds
   (`TotalProcessorTime` twice), `PrivateMemorySize64`. The main thread is the oldest one
   (`$p.Threads | Sort-Object StartTime | Select -First 1`): `ThreadState` Wait + 0 CPU = blocked
   waiting, not computing.
2. Redshift log `C:\ProgramData\Redshift\Log\Log.Latest.0\log.html` (strip HTML): the time of the last
   line, and `Waiting until idle` (see the hang section in SKILL.md). `PreviewScheduler: Periodic Cache
   Cleanup` is written every minute while things are normal, so the last one roughly dates a freeze.
3. **Render Queue / Team Render job** — look here before calling it a hang:
   `%APPDATA%\Maxon\Maxon Cinema 4D <ver>_<id>\teamrender\users\c4d\rq_take_<n>_<id>\job.log`
   (plus `job.ini`, and the scene copy it renders). One line per frame per machine:
   `<time>  <machine>: Rendering frame N of job '…'`; the local machine shows as `Machine`, render
   nodes by host name. The first frame per machine shows how the range was split (e.g. 0 and 420).
   Count lines per machine for progress and rate; grep for error/fail/lost.
4. MCP `ping` through the relay with a hard limit (`timeout 25 python -I scripts/c4d_mcp_call.py ping`).
   No answer = the main thread is busy; the request stays queued and is answered later (harmless).
   Don't follow it with `exec_python`.

Seen 6 Nov 2026 (2027.0): the window had been "Not Responding" for ~50 min with the main thread
waiting (0 CPU), the RS log quiet since before the job started, and ping unanswered, while job.log
showed a Team Render job of the open scene still finishing a frame every ~20–25 s on two machines.
That is busy, not dead: restarting would kill the job (the Team Render server lives in that C4D). Tell
the user to let it finish. Whether the GUI comes back by itself after the job ends is unverified.

## macOS (verified 2027.0, Nov 2026)
- `sample <pid> 2 -file /tmp/s.txt`, then read the `com.apple.main-thread` block. A "stall" seen this way: a mouse-down
  in a window → `python.xlib` `PyObject_CallMethod` → a modal event loop (`nextEventMatchingMask`) redrawing the
  viewport, which re-evaluated a heavy scene (31k clones with a Python effector) — busy in a UI interaction, not an
  MCP script. Percent CPU stayed low (12–26 %).
- `~/Library/Preferences/Maxon/Maxon Cinema 4D <ver>_<id>/prefs/mcp/audit.log` lists every MCP call with
  timestamps (COMMAND / EXEC_PYTHON / EXEC_RESULT / RESPONSE): a logged `ping` without a RESPONSE means the main
  thread is busy; the last EXEC tells whether a script of yours could be the cause.
- A force-quit leaves no `_bugreports` entry and no autosave; tell the user which unsaved work is likely lost.

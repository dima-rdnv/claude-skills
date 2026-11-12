# Render Queue and Team Render from Python (verified C4D 2026 macOS / 2027.0 Windows)

```python
br = c4d.documents.GetBatchRender()
br.AddFile(path, br.GetElementCount()); br.SetRendering(c4d.BR_START)   # returns immediately; AddFile(path, 0) puts the job on top
br.EnableElement(i, False)                                              # skip an old job (verified)
```
- The queue renders the file **from disk**. By default it uses the take that was current when the
  file was saved; pick another take per job with `br.SetActiveTakeIndex(job, takeIndex, False)` —
  several jobs on the same file, one per take, no per-take file copies (recipe and binding quirks
  in `cinema4d-takes`). A take with no camera renders the editor "Default Camera".
- Status codes (`c4d.RM_*`): 1000 PROGRESS, 1001 FINISHED, 1002 STOPPED, 1003 ERROR, 1004 ERROR2,
  1005 PAUSED, 1006 QUEUE, 1007 PROGRESS_WITH_WARNING, 1008 NONE. `br.GetJsonJobs()` gives every
  job's status, message ("Error - Missing Files"), progress and output path — read errors there.
  In 2027.0 it returns a **Python list of dicts**, not a JSON string (`json.loads` fails); keys include
  `status`, `message`, `progress`, `image_path`, `total_frames` (= last frame + 1), `outputwidth/height`.
- **Several frame spans of one take without the `_i1` rename** (verified 2027.0, queue level): give the take's
  render setting children that change only the frame range **and the file prefix** (`…_s2`, `…_s3`), one job
  per child via `SetActiveRenderSettingsIndex`; `image_path` came back with each prefix and no `_i1`. Rename the
  span files to one sequence afterwards.
- **No API moves rows.** To change the order, switch the rows that should wait off (`EnableElement(i, False)`,
  safe while the queue renders) and switch them back on once the queue is idle, then `BR_START`. Re-adding them
  at the end would give their output the `_i1` rename (the disabled rows still count).
- **A Team Render client without an activated Redshift licence** (verified 2027.0): it downloads the assets, takes
  a frame, then its `job.log` lines read `Redshift Error: Maxon licensing error: License not activated (9)`,
  `No devices available`, `Render-Job failed`, and the server renders on alone. Count frames per machine in
  `job.log` (`<machine>: Rendering frame N`) a few minutes after `BR_START` before trusting a Team Render estimate.
- **"Error - Missing Files" although every texture resolves:** `br.SetCheckTexture(False)`, then
  `BR_START` again — the errored job re-ran and finished (verified C4D 2026, macOS).
- `GetAllTakeNames(job)` lists the takes in `SetActiveTakeIndex` order (depth-first, `Main` = 0).
  The getters `GetActiveTakeIndex` / `GetActiveTakeName` / `GetActiveCameraName` take
  `(job, filename)` — called with the job alone they raise "Required argument 'filename'". In another
  2027.0 session the same getters accepted only `(job)` ("takes at most 1 argument") — try both.
- "Incremental Image Name" came back after a C4D restart although the user had switched the
  auto-renaming off before: a half-added job from a failed script made the next identical job `_i1`.
  Disable it, have the user delete the extra rows, re-add, re-check every `message`.
- **Never call `br.SetRendering(c4d.BR_STOP)` from the bridge** — it deadlocked C4D (0% CPU, UI
  frozen, force quit needed). Ask the user to stop renders in the Render Queue window.
- **Don't loop on `DelFile`** — it did not remove a waiting job (2027.0: returns False, count
  unchanged, also for disabled jobs). Disable old jobs instead, or ask the user to delete them.
- **Render missing frames without touching the take** (verified 2027.0, Team Render): child render
  setting under the take's own setting that only narrows the frame range, then per job
  `rds = br.GetAllRenderSettingsNames(job)`; `br.SetActiveRenderSettingsIndex(job, rds.index(name))`.
  The Team Render `job.log` started at the child's first frame. Jobs keep the render setting by
  index: after removing or reordering a file's settings, a queued job pointed at another one.
- **Two jobs with the same resolved output (same file and take) → "Incremental Image Name"**: the
  later job's `image_path` gets `_i1`/`_i2` appended, and disabled jobs count too. Never accept it
  (the frames leave the sequence): one job per take — widen the range instead of queuing two — and
  check every `GetJsonJobs()` `message` before `BR_START`. The auto-renaming can be switched off in
  C4D (a user did; where is not recorded here); jobs added afterwards came in clean.
- `br.SetRendering(c4d.BR_START)` from `exec_python` started a Team Render queue fine in a healthy
  session (2027.0; the GUI-render hang in SKILL.md was in a session where Redshift was already stuck).
- Watch progress from a shell (output file size/mtime, the Team Render `job.log` — see
  `is-c4d-stalled.md`); bridge calls can block while a job loads.
- **Queue calls load the scene file on C4D's main thread**: `AddFile`, `GetAllTakeNames`,
  `GetActiveTakeName`. With a heavy file (65 MB + 25 Alembic particle groups) 24 jobs took ~2 min
  and a second listing call that asked each job's take froze the UI again ("Not Responding", but
  reading ~27 MB/s — busy, not dead; wait it out, never kill). Fill a big queue in one call, read
  back with `GetElement`/`GetElementStatus`/`GetJsonJobs()` only, and warn the user first.
  `BatchRender` has `SetUseNet` (Team Render) but no `GetUseNet` — and `SetUseNet(job, False)` right after
  `AddFile` did NOT untick the Team column (the job rendered with Team Render: its log lists `.b3d` frames
  out of order). Ask the user to check the Team column before starting.
- **After a C4D restart the queue keeps its jobs but resets each job's take to Main** (with the
  document's active render setting and its output path): a restored job rendered the wrong take into
  another folder. After any restart, disable the old take jobs and add them fresh; read back each job's
  `image_path` from `GetJsonJobs()` before starting.
- Redshift crash "ASSERT FAILED Scene.cpp … RSScene is locked" (Redshift disabled) on every machine at
  the same frame = an RS Volume whose only loaded grid is all zeros (pure-emission fire after the burn):
  `cinema4d-redshift` volumes section.
- **Team Render jobs fail "Error – Saving Image" (before any client renders, 0–17 s) when ANY scene
  asset is missing** — even an unused, hidden Alembic Generator with another machine's path; the
  queue's `SetCheckTexture(False)` doesn't cover Team Render. Verified by elimination (frame rate,
  volumes, particles, render settings were not it): `GetAllAssetsNew` must report nothing missing —
  delete unused objects or relink. Assets local to the server (`D:/cache/*.vdb`, `.abc`) are
  transferred to the clients fine. Test such things with a copy saved NEXT to the real file
  (relative `./tex` paths break in a scratch folder and confound the test).
- **"Error – Saving Image"** (local queue): the queue doesn't create missing output folders (Commandline does) —
  create `<shot>/<take>/` folders before starting. **"Error – Missing Files"** also flags absolute
  paths from another machine (`/Users/...`) that `GetAllAssetsNew` resolves by name: relink them
  project-relative (`tex/...`), or `SetCheckTexture(False)` when the missing files are unused.
- **"Error – Invalid Output Multi-Pass Path"** (verified 8 Nov 2026, C4D 2027) although the job's render setting has
  multi-pass and its saving off: the queue validates the **multi-pass filename** (`RDATA_MULTIPASS_FILENAME`), and also that of the
  document's **active** render setting — an old relative `./C:/Other/...` path from another machine refused the job. Give every
  render setting of the copy a valid multi-pass filename and make the job's setting the active one.
- **"Error – Missing Files" can be transient**: jobs of a heavy file showed it right after `AddFile` (while C4D was still loading
  the files) and then rendered normally when the queue reached them (re-checked at job start; `GetAllAssetsNew` reported nothing
  missing). Check with c4dpy before believing it; `SetCheckTexture(False)` for the queue's own check.
  Seen again (2027, 7 rows of one 63 MB file added in a row): rows 2–7 flagged although `SetCheckTexture(False)` was called
  before `AddFile`; the queue still rendered each of them when it got there. Don't re-add such rows — a second row with the
  same output gets the Incremental Image Name rename.
- `BatchRender.DelFile(i)` returned False and removed nothing (2027, queue idle) — rows can only be switched off
  (`EnableElement(i, False)`). A new row whose output path equals an old row's (even an errored, disabled one) gets the
  **auto-renamed `_i1` path** ("Incremental Image Name"): give re-queued jobs a new output path instead.
- Disabling only `"In Queue"` rows is not enough to keep the user's jobs from running: a **"Stopped"** row stays enabled and the
  queue resumes it after yours. Disable both, record them, re-enable afterwards (`GetEnableElement(i)` reads the state).
- An `exec_python` that loads several heavy files into the queue hits the MCP adapter's 30 s dispatch timeout, but the handler keeps
  running and finishes (holding C4D's main thread for minutes) — never resend it; read the queue afterwards.
- Single-frame jobs write `name.exr` without a frame number; a frame range writes `name.####.exr`.
- **Team Render tails (2027, Nov 2026):** a slow client (~22 s/frame vs 1–3 s locally) took the last frames of jobs and held them
  7 min and 50+ min; the queue waits for them before the next job. For deadline renders switch `SetUseNet` off or render locally
  with Commandline; switching waiting rows off with `EnableElement(i, False)` while the queue renders was safe.
- **Commandline `CRITICAL: Stop [ge_container.h(440)]`**: thousands of these lines right after "Loading Project" are noise for some
  scenes (renders that worked printed 1 700–9 100). Under full CPU load from other processes (two pyro sims in hython) loading slowed
  from seconds to many minutes and looked like a hang — check CPU, lower the other processes' priority
  (`(Get-Process hython).PriorityClass = 'BelowNormal'`) before killing anything.

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
- **"Error - Missing Files" although every texture resolves:** `br.SetCheckTexture(False)`, then
  `BR_START` again — the errored job re-ran and finished (verified C4D 2026, macOS).
- `GetAllTakeNames(job)` lists the takes in `SetActiveTakeIndex` order (depth-first, `Main` = 0).
  The getters `GetActiveTakeIndex` / `GetActiveTakeName` / `GetActiveCameraName` take
  `(job, filename)` — called with the job alone they raise "Required argument 'filename'".
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

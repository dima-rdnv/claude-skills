# After upgrading Cinema 4D (verified 2026.4 → 2027.0, Windows)

- The new version's adapter was not listening (nothing on 127.0.0.1:5556; macOS:
  `lsof -nP -iTCP:5556 -sTCP:LISTEN`). Check the port before trying tools; the user has to switch it on
  again in the new version.
- Preferences and plugins are per version (`Maxon Cinema 4D <year>_<id>`), and a path with the old year
  stops working once that version is removed: a plugin in the old folder doesn't come along.
- Renders can continue without MCP through the bundled command-line renderer, which runs next to the
  open GUI: `"C:/Program Files/Maxon Cinema 4D 2027/Commandline.exe" g_licenseModel=LICENSEMODEL::MAXONAPP
  -render "scene.c4d" -frame 48 242 -oimage "D:\out\Name_"` (stdin from /dev/null, log to a file,
  run in the background; on macOS the binary is `Commandline.app/Contents/MacOS/Commandline`, not run
  yet). It keeps the scene's format/alpha (RGBA float32 EXR) and names frames `Name_0048.exr`; the log
  ends each frame with "Rendering successful: N sec." Before continuing a sequence across versions,
  render one finished frame to a scratch folder and diff it: a Redshift line scene came out
  bit-identical in 2027.0 vs 2026.4. Also verified: `-frame 0 240 120` (start end step) renders
  three frames; `-oresolution 1920 1080` renders at that size (good for quick motion tests).
- **"Rendering failed: Out of memory" from Commandline** (verified 2027.0) while the GUI was
  rendering a sequence with Redshift: the GUI held ~23 of 24 GB VRAM and the Commandline Redshift
  log said "199 MB was available for Redshift". The GUI's log is
  `C:\ProgramData\Redshift\Log\Log.Latest.0\log.html` (Application Path `Cinema 4D.exe`), the
  Commandline run gets its own `Log.Latest.N` (Application Path `Commandline.exe`). A new
  "Rendering blocks… (resolution …)" line every few seconds in the GUI log = the user is rendering:
  wait (watch the output folder fill), then retry — it worked as soon as their render ended.
- **Changing a scene with no MCP** (verified 2027.0): `c4dpy.exe g_licenseModel=LICENSEMODEL::MAXONAPP
  script.py …` can `LoadDocument(path, SCENEFILTER_OBJECTS | SCENEFILTER_MATERIALS)`, set a Python
  Generator's user data by name (`for did, bc in op.GetUserDataContainer(): bc[c4d.DESC_NAME]`),
  and `SaveDocument(doc, copy, SAVEDOCUMENTFLAGS_DONTADDTORECENTLIST, FORMAT_C4DEXPORT)` to a
  scratch copy; render settings and links survive, and a Commandline render of the copy matched the
  original pixel for pixel outside the changed elements. Don't save over a scene the user has open
  in the GUI — their next save silently overwrites it; give them the values to type instead.
  Which document is in front shows in the window title: `tasklist //V //FI "IMAGENAME eq Cinema 4D.exe"`
  → `Cinema 4D 2027.0.0 - [02 Satellite Data Flow.c4d] - Main`. `LoadDocument` returns None (no
  error) for a missing path — users rename scenes (here "Ship Data Flow.c4d" → "02 Ship Data
  Flow.c4d"), so list the folder first; a renamed scene also renames its `$prj` output folder.

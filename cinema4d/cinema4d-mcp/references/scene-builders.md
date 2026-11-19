# Building scenes from scripts: builders, controls, viewport (verified C4D 2027.0, macOS, Nov 2026)

## Builders that make a new file
- `c4d.CallCommand(12094)` (New Project) gives a real new document with the user's defaults (OCIO/ACEScg).
  Assert it's empty and different from the previous active document, `SetDocumentName/Path`, build, then
  `SaveDocument`. Refuse to overwrite: `open(path, "rb")` succeeding → raise.
- Wrap the build in try/except and `KillDocument` the new document on any error, then `SetActiveDocument` back.
  One build failed once while creating its materials in a fresh project (cause unknown, did not recur) and left a
  half-built document open.
- Sharing code between builders: `src = open(other_builder).read(); exec(src[:src.rindex("\nmain()")], globals())`
  works inside `exec_python`. Watch for global names: the shared code's `P` (an RS node-id prefix string) was
  shadowed by a local helper `P()` and broke material creation; set your own constants (e.g. `NAME`) after the exec.
- Rebuilding a file you created this session: close its document (`KillDocument`, ReferenceError "not alive" at the
  end of the call is harmless), delete the file, rebuild. Never do that to a user's file.
- Publish the builder scripts next to the scene (e.g. `Assets/_scripts/`) so the scene can be regenerated.

## Viewport: thin offsets z-fight
Faces 0.1 cm apart seen from 9000 cm (dies on a wafer) z-fought badly with the default clipping (near 1 cm). Project
clipping `doc[c4d.DOCUMENT_CLIPPING_PRESET] = c4d.DOCUMENT_CLIPPING_PRESET_CUSTOM`, `..._NEAR = 150`,
`..._FAR = 60000` made it clean (50 still left specks). Viewport only; renders are unaffected. Keep near below the
closest camera distance.

## User-data controls driven by a Python tag
- Put the controls the user needs on a null: groups (`DTYPE_GROUP`, children via `DESC_PARENTGROUP`), reals with
  `DESC_MIN/MAX/STEP/UNIT` (`DESC_UNIT_PERCENT` shows 0..1 as %, `DESC_UNIT_DEGREE` stores radians), sliders
  (`DESC_CUSTOMGUI = CUSTOMGUI_REALSLIDER`), a "Links" group of `DTYPE_BASELISTLINK` entries to the driven objects
  (robust to renames), a hidden int to select the driver mode.
- A Python tag (`1022749`, code in `c4d.TPYTHON_CODE`) on the null reads its user data and writes the targets
  **only when a value differs**. Initialise every control from the current scene value so installing changes
  nothing; check that by comparing values before and after one `ExecutePasses`.
- **`DESC_MAX` clamps the value you initialise it with.** A spot falloff the user had set to 90° became 60° (the
  control's max), and the driver then wrote 60° to the light. Set limits wider than any plausible value, and compare
  every driven value with the saved file (`LoadDocument` read-only) after installing.
- Know the parameter type before mapping a bool onto it: RS Camera `[12110]` is an enum (1 Off, 0 Render Settings,
  2 Override); `True` wrote 1 = Off.

## Python Generator
- Code parameter: `c4d.OPYTHON_CODE` (not `OPYTHON_STRING`; the Python effector's is `OEPYTHON_STRING`), cache
  switch `c4d.OPYTHON_OPTIMIZE`. With optimisation off, cache the result yourself in a module dict keyed by
  `op.GetGUID()` and a signature (user-data values, source `GetDirty`, field-list dirty) and return
  `cached.GetClone()`.
- A **FieldList user data** (`c4d.GetCustomDataTypeDefault(c4d.CUSTOMDATATYPE_FIELDLIST)`; value: `c4d.FieldList()`
  with `FieldLayer(c4d.FLfield).SetLinkedObject(field)`) can be sampled in the generator:
  `fl.SampleListSimple(op, c4d.modules.mograph.FieldInput(points, n), c4d.FIELDSAMPLE_FLAG_VALUE).GetValue(i)`.
  Used to thin street lamps out from the centre: a spherical field (Size `1000` = radius, Inner Offset `1005007`) gave
  11 → 0.9 lamps per m² from the centre to the rim. Keep field objects outside the generator (siblings).

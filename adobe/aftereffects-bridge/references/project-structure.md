# The user's usual After Effects project structure (written down Nov 2026; "could be refined")

Follow it when adding renders, precomps or layers to the user's projects.

## Project panel

```
ASSETS/
  Audio/                 VO (+ music)
  Footage/               reference videos, earlier films
  Renders/               one folder per shot (F01, F03, F09-10 …) or per render batch (e.g. "RS v5 fuel <date>",
                         "v4 engine <date>", "VP", "Houdini GL passes")
  Solids/
  Stills/
  Stock/
  Storyboard/<version>/  frames/, pages/
COMPS/
  <main edit>            e.g. "<Project> animatic v5" (3840x2160, 30 fps)
  <storyboard edit>      nested under the main edit, switched off, for reference
  <stills / styleframes>
  _nested/               shot precomps (one per CG shot or split-screen half), audio, graphics
  _old/                  superseded comps
```

Project: 32 bpc, ACEScg working space. The view transform is an `OCIO` adjustment layer in the main comp, then a `LUT`
adjustment layer.

## Main comp, top to bottom

1. Storyboard picture-in-picture (off).
2. Titles and text per shot (`F09 | Up to 60% less NOx`).
3. Split-screen labels, two per split shot: `Fxx | label left` / `Fxx | label right`.
4. `NULL`: the parent of almost every layer (one global transform).
5. Display-referred graphics shots (e.g. a Sankey precomp).
6. `OCIO` (display transform), then `LUT` adjustment layers. Below them everything is linear ACEScg CG; graphics and text sit
   above them.
7. CG shots in edit order, the newest version of a shot right above its old one:
   - one shot = one layer or precomp: `Fxx | RS v4 F04`;
   - split screen = two half-width precomps (1920x2160): `Fxx | … untreated (left panel)` / `… treated (right panel)`;
   - superseded versions stay switched off (`[off] F05 | storyboard v4`), never deleted.
8. `BG`: a white solid (1.0 in ACEScg) under everything.
9. The storyboard underneath (off) and the VO at the bottom.

Layer names start with the shot: `Fxx | what it is`.

## Refinement ideas (not applied unless asked)

- New precomps belong in `COMPS/_nested`, not next to their footage in `ASSETS/Renders`.
- `ASSETS/Renders` mixing per-shot and per-batch folders is harder to scan; one rule (per shot, version in the item name)
  would be cleaner.
- Unused precomps → `_old`.
- A divider layer between display-referred graphics and the linear CG (above `OCIO`) would make the rule visible.

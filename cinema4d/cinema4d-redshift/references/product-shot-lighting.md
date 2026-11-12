# Product shots in Redshift: HDRI reflections + one key (verified C4D 2027.0, Windows, Nov 2026)

Built for 3/4 shots of rack hardware (matte powder-coated chassis, metal port cages, chrome hardware).

## What the user wanted
- **Few lights, real contrast.** A rig of key + fill + rim + overhead softbox + wall wash gave an
  evenly soft, flat image ("too many lights… shouldn't be completely well soft lit"). The accepted
  setup: a studio HDRI on the dome plus **one small key**. It gives a real cast shadow and a
  light/shade split between front, side and top.
- **Contrast on metals comes from the HDRI.** Pick an HDRI with large softboxes on a black surround
  (preview the small versions as a contact sheet first). Set the area lights' **Reflection
  contribution to 0**. Metals then mirror only the HDRI's bright panels and black, and chrome reads
  as chrome. With the area lights still reflecting, the HDRI made almost no visible difference.

## IDs (RS Light, plugin 1036751)
- **Dome texture:** `dome[c4d.REDSHIFT_LIGHT_DOME_TEX0, c4d.REDSHIFT_FILE_PATH] = path` (the same
  sub-id pattern as the RS Volume file).
- **Dome controls:** intensity `[12024]`, exposure `[12015]`, rotate on horizon
  `[c4d.REDSHIFT_LIGHT_DOME_ROTATE_ON_HORIZON]` (12026, degrees), flip `[12013]`, camera visibility
  `[10042]`. Set camera to 0 to keep your own set as the background.
- **Contributions:** `[10034]` Reflection, `[10035]` Transmission, `[10031]` GI, `[10042]` Camera.
  Read any others with `GetDescription(c4d.DESCFLAGS_DESC_NONE)` before assuming an id.
- **Normalize Intensity is off on Python-made area lights** (`[11014] = 0`), so output scales with
  the light's area. Shrinking a key from 140 to 60 cm (for firmer shadows) cut its light about 5×,
  and doubling the intensity changed nothing visible. Scale the intensity by (old/new size)²; here
  intensity 30 at 60 cm.

## Set and camera
- **Lens and camera height:** with a long lens (100 mm, 36 mm aperture) and the camera ≤ ~14°
  down, the frame sees only the floor, so no backdrop wall is needed. A cyclorama wall placed close
  behind the product showed as a lighter band at the top of the frame; push it out of view (or turn
  the whole studio to face the camera).
- **Framing:** projected width ≈ W·cos(az) + D·sin(az). Frame width = projected / fill (0.70–0.74).
  Distance = frame width · focal / aperture.
- **3/4 angle for deep rack units:** 25° azimuth and 9° elevation keep the front panel leading. At
  35° / 17° the long side and top took over the image.
- **Rack ears:** match the vendor's photos. Here the 2–3U units were shown without ears, the 1U
  with them.
- **Keep it in a take** (studio group visible, the default light rig hidden, final render setting),
  so the shot re-renders in 10–40 s from Commandline.
- **HDRI location:** copy the chosen HDRI next to the project assets on the shared drive, not a
  personal library path, so other machines resolve it.

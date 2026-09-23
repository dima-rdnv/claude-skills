---
name: cinema4d-redshift
description: Redshift in Cinema 4D through Python — building and editing Redshift node materials with the maxon graph API (node and port IDs for RS Standard, attribute lookups, user data), the RS Object tag particle settings, fast test renders with RenderDocument and pixel-level verification, viewing renders from the sandbox, and verified dead ends (per-particle colour on Alembic Particle Groups). Use when shading or test-rendering with Redshift in C4D. Load with cinema4d-mcp.
---

# Redshift in Cinema 4D (verified, C4D 2026.3)

## Node materials through the maxon API
- Every material is type 5703; the Redshift graph lives in a node space:
  `RS = maxon.Id("com.redshift3d.redshift4c4d.class.nodespace")`,
  `graph = mat.GetNodeMaterialReference().GetGraph(RS)` (`HasSpace(RS)` to test).
  The MCP tool `inspect_redshift_materials` skips these as "not_redshift_like" — use the API.
- New material: `mat = c4d.BaseMaterial(c4d.Mmaterial); doc.InsertMaterial(mat);
  graph = mat.GetNodeMaterialReference().CreateDefaultGraph(RS)` → RS Standard + Output.
- List nodes: `graph.GetViewRoot().GetChildren(lst, maxon.NODE_KIND.NODE)`; node type:
  `n.GetValue("net.maxon.node.attribute.assetid")`. List ports:
  `n.GetInputs().GetChildren(lst, maxon.NODE_KIND.PORT_MASK)`.
- Edit inside `with graph.BeginTransaction() as t: ... t.Commit()`:
  `graph.AddChild(maxon.Id(), maxon.Id(node_type))`, `n.GetInputs().FindChild(port_id)`,
  `port.SetPortValue(maxon.String(...) / maxon.Float(...) / maxon.ColorA(...))`, `out.Connect(inport)`,
  `n.Remove()`. Assign: `tag = obj.MakeTag(c4d.Ttexture); tag[c4d.TEXTURETAG_MATERIAL] = mat`.
- Find node types: `maxon.AssetInterface.GetUserPrefsRepository().FindAssets(
  maxon.AssetTypes.NodeTemplate(), maxon.Id(), maxon.Id(), maxon.ASSET_FIND_MODE.LATEST)` and filter
  ids for "redshift" (161 templates). Build a node in a throwaway doc's material to list its ports.

## IDs (prefix `com.redshift3d.redshift4c4d.nodes.core.`)
- `standardmaterial`: `.base_color`, `.base_color_weight`, `.emission_color`, `.emission_weight`,
  `.refl_weight`, `.refl_roughness`, `.overallaffectsemission`. Output: `com.redshift3d.redshift4c4d.node.output`.
- `vertexattributelookup`: `.attribute`, `.defaultcolor` (magenta), `.defaultscalar`, `.outcolor`, `.outscalar`.
- `particleattributelookup`: `.attribute`, `.outcolor`, `.outscalar`.
- `rsuserdatacolor`: `.attribute`, `.default`, `.out` (also `rsuserdatascalar/vector/integer/string`).
- Others seen: `texturesampler`, `triplanar`, `fresnel`, `bumpmap`, `bumpblender`, `roundcorners`,
  `rsscalarramp`, `rscolorconstant`, `incandescent`, `state`, `c4dhairattribute`, `volume*attribute`.

## RS Object tag (plugin 1036222)
- Particles: override 2999, mode 3000 (0 Disabled, 1 Point, 2 Sphere, 3 Quad instances, 4 Custom
  objects, **5 Optimized Spheres**), 3001 Scale Multiplier (× the particle radius channel).
- Motion blur: 6999 override, 6000 mode (0 Global, 1 Off, 2 Transformation, 3 + Deformation).
- Verified: an Alembic Particle Group renders as Optimized Spheres at its `width` radius.

## Test renders you can verify
```python
rd = doc.GetActiveRenderData().GetClone()
rd[c4d.RDATA_XRES], rd[c4d.RDATA_YRES] = 480, 270
rd[c4d.RDATA_FRAMESEQUENCE] = c4d.RDATA_FRAMESEQUENCE_CURRENTFRAME; rd[c4d.RDATA_SAVEIMAGE] = False
bmp = c4d.bitmaps.MultipassBitmap(480, 270, c4d.COLORMODE_RGB)
res = c4d.documents.RenderDocument(doc, rd.GetDataInstance(), bmp, c4d.RENDERFLAGS_EXTERNAL)  # 0 = ok
```
- Returns well under the 60 s limit at this size. Set `doc.SetTime(...)` first.
- Verify numerically: sample `bmp.GetPixel(x, y)` in the region of interest and bucket colours
  (a magenta default on a lookup node = "attribute not found").
- To look at it: `bmp.Save('/tmp/x.png', c4d.FILTER_PNG)`, then open the file with any image-capable
  tool (e.g. a shell tool: `sips -s format jpeg ...` → `base64` → decode and view).
- A scene's render output path may be a Windows path (`D:/...`) — on macOS that creates a folder named
  `D:` next to the scene; keep SAVEIMAGE off for tests.

## Verified dead end: per-particle colour on Alembic Particle Groups
- Positions and radius render, but colour does not reach Redshift: Vertex Attribute Lookup `__cd__`
  → default (magenta); Particle Attribute Lookup `color` / `__cd__` → black; Color User Data
  `__cd__` → black. Cause: the colour channel is empty in real documents (see `cinema4d-alembic`).
  Ruled out: render engine, OCIO, fps/time range, doc path, scene objects, materials.
- Routes instead: Redshift Proxy from Houdini (needs Redshift for Houdini; Cd via RS Point
  Attribute), polygon mesh with point Cd (spheres copied to points or a VDB mesh → Vertex Color tag →
  Vertex Attribute Lookup; heavy files), or a procedural colour in the RS shader (age/position driven;
  whether Particle Attribute Lookup reads `age` is untested).

## Keeping this skill current
After any session that used Houdini/Cinema 4D via MCP, or whenever something new is verified:
1. Add gotchas/recipes ONLY if tested and working in a real scene; mark anything else "(unverified)".
2. Correct entries that proved wrong — don't append contradictions.
3. Put each finding in the skill it belongs to (see the indexes in `houdini-mcp` and `cinema4d-mcp`);
   project-specific facts go to that project's notes (see `project-notes`), never into a skill.
4. Keep each SKILL.md under ~300 lines; split into a new sub-skill or `references/` when it grows.
5. Re-package every changed skill (keep names) and, if the skills live in a git repo, commit and push.
   Tell the user in one line what changed.

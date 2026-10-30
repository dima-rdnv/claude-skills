---
name: unreal-materials-python
description: Building and editing Unreal Engine 5.8 materials from Python (MaterialEditingLibrary) — materials, material functions with inputs/outputs, Material Parameter Collections, Custom HLSL nodes (helper functions, texture sampling), per-instance pivots, injecting a function between a material's existing inputs and its outputs, importing data textures, and finding compile errors. Includes verified traps (struct constructors, ComponentMask defaults, delete_all skipping nodes, MPC reordering). Load with unreal-mcp.
---

# Unreal materials from Python

Verified on UE 5.8.4 with Substrate enabled in the project (legacy material inputs still work and
are converted). Load `unreal-mcp` first for how to run code in the editor.

## Basics
```python
MEL = unreal.MaterialEditingLibrary
AT = unreal.AssetToolsHelpers.get_asset_tools()
mat = AT.create_asset("M_Foo", "/Game/Dir", unreal.Material, unreal.MaterialFactoryNew())
mf  = AT.create_asset("MF_Foo", "/Game/Dir", unreal.MaterialFunction, unreal.MaterialFunctionFactoryNew())
mpc = AT.create_asset("MPC_Foo", "/Game/Dir", unreal.MaterialParameterCollection,
                      unreal.MaterialParameterCollectionFactoryNew())
n = MEL.create_material_expression(mat, unreal.MaterialExpressionMultiply, x, y)
n = MEL.create_material_expression_in_function(mf, unreal.MaterialExpressionMultiply, x, y)
MEL.connect_material_expressions(src, "", dst, "A")     # returns False on a bad pin name
MEL.connect_material_property(src, "", unreal.MaterialProperty.MP_BASE_COLOR)
MEL.update_material_function(mf); MEL.recompile_material(mat)
unreal.EditorAssetLibrary.save_loaded_asset(asset)
```
- Output/input pin names: `""` = first/only pin. Lerp: `A`, `B`, `Alpha`; Multiply/Add: `A`, `B`;
  FunctionOutput / ComponentMask / TransformPosition input: `""`; Custom node inputs: their names.
- Wrap `connect_material_expressions` and raise when it returns False — silent failures otherwise.
- Read an existing material's wiring:
  `MEL.get_material_property_input_node(mat, prop)` and
  `MEL.get_material_property_input_node_output_name(mat, prop)` (works, 5.8).
- With Substrate on, `connect_material_property` to `MP_BASE_COLOR` etc. still works on a new
  material (`MP_FRONT_MATERIAL` stays unconnected; legacy inputs are auto-converted).

## Traps (all hit in practice)
- **Struct constructors take no kwargs**: `unreal.CustomInput()` then
  `set_editor_property("input_name", n)`; same idea for `CollectionScalarParameter` /
  `CollectionVectorParameter` (`parameter_name`, `default_value`).
- **`Vector4f` has no Python fields** (FunctionInput `preview_value`):
  `pv = node.get_editor_property("preview_value"); pv.import_text("(X=0.5,Y=0.5,Z=0.5,W=0)");
  node.set_editor_property("preview_value", pv)`.
- **ComponentMask defaults are not all off.** Setting only `r=True` gave a float2 and a
  "float3 * float2" compile error. Always set all four: `for c in "rgba": m.set_editor_property(c, c in "r")`.
- **`delete_all_material_expressions_in_function` removes only every other node per call.**
  Leftover FunctionOutputs then break compiles ("Missing function output connection"). Loop until
  `MEL.get_num_material_expressions_in_function(mf) == 0`.
- **Never reorder an MPC's parameter arrays.** Append new parameters at the END. Inserting in the
  middle shifts the collection's layout; already-compiled materials read the wrong slots.
  `MEL.recompile_material` on each user afterwards.
- **Rebuilding a material function in place (delete all nodes, recreate) silently disconnects every
  MaterialFunctionCall that uses it**: the new FunctionInput/Output nodes get new ids, the calling
  material keeps compiling without errors, but its property pins (BaseColor, Emissive...) are now
  empty → black surfaces. After a structural rebuild, re-create or re-inject the calling materials;
  check with `MEL.get_material_property_input_node(mat, MP_BASE_COLOR)` (None = broken).
- `MaterialExpressionCollectionParameter`: setting `collection` then `parameter_name` via
  `set_editor_property` resolves the parameter id (compiles, values verified in the viewport).
- `MaterialExpressionTextureObject`: setting `texture` auto-picks the sampler type.
- **Changing MPC defaults resets the editor world's live MPC values on the next tick.** Setting a
  preview value (`MaterialLibrary.set_scalar_parameter_value(editor_world, ...)`) in the same Python
  call as a default change gets wiped — set previews in a separate call.
- Deleting a material that is loaded and assigned fails ("Failed to unload all packages" ensure)
  and `create_asset` then returns None — clear its nodes instead (loop
  `MEL.delete_all_material_expressions(mat)` until `get_num_material_expressions == 0`) and rebuild.

## Compile errors
`MEL` has no compile-error getter. Read the log: after a recompile, lines like
`LogMaterial: Warning: [AssetLog] /Game/..: Failed to compile Material for platform PCD3D_SM6`
are followed by tab-indented lines with the real error, e.g.
`(Function MF_X) (Node Multiply) Arithmetic between types float3 and float2 are undefined`.
A transient "Custom material ... missing input" can appear while a graph is still being wired.
The MCP `MaterialTools.get_expressions` lists every node in a material/function (handy to spot
leftovers).

## Custom HLSL node
```python
c = MEL.create_material_expression_in_function(mf, unreal.MaterialExpressionCustom, x, y)
c.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT2)
c.set_editor_property("code", HLSL)
c.set_editor_property("inputs", custom_inputs(["Tex", "P", "Pivot", "Now"]))
```
- Helper functions inside a Custom node: wrap them in a struct and instantiate it
  (`struct N { float h(float3 p){...} }; N n; ... n.h(p)`) — compiles in 5.8.
- A TextureObject wired to input `Tex` is sampled in code as
  `Texture2DSampleLevel(Tex, TexSampler, uv, 0)`.
- Don't name an input `Time` (use e.g. `Now`) to stay clear of engine names.
- World position: `MaterialExpressionWorldPosition` (absolute) into a float3 input.
- Per-object / per-instance pivot: `MaterialExpressionTransformPosition` with
  `transform_source_type = TRANSFORMPOSSOURCE_INSTANCE`, `transform_type = TRANSFORMPOSSOURCE_WORLD`,
  input = Constant3Vector(0). Verified visually: StaticMeshActors AND each instance of an
  InstancedStaticMeshComponent switch on their own. (`ObjectPositionWS` exposes no Python properties.)
- Per-instance object SIZE: `MaterialExpressionBounds` (default type "Instance Local" = the
  instance's mesh bounds; output 0 = half extent, local units) → `MaterialExpressionTransform` with
  `transform_source_type = MaterialVectorCoordTransformSource.TRANSFORMSOURCE_INSTANCE`,
  `transform_type = MaterialVectorCoordTransform.TRANSFORM_WORLD` → world half extent incl. scale.
  `length(.xy)` separates small instances from a huge floor (verified). Don't use ObjectRadius /
  ObjectBounds for this: they are primitive-level, i.e. the whole ISM component.
- Whole-object / chunked switching without noise: time = field(pivot) + hash(pivot) jitter; for
  big objects use cubes `ci = floor(P / size + 0.37)` (the offset keeps the grid off z = 0 floors —
  an exact boundary there flickers between two cells) and time = field(cell centre) + hash(ci).

## Keeping emissive out of Lumen GI (no colour spill onto neighbours)
`MaterialExpressionRayTracingQualitySwitch` (pins `Normal`, `RayTraced`): the RayTraced branch is
used by ray-tracing shaders AND by Lumen's surface-cache card capture (`LUMEN_CARD_CAPTURE` in
Common.ush `GetRayTracingQualitySwitch`). Feed the full emissive to Normal and a reduced/zero
emissive to RayTraced → the surface looks the same on screen but adds no bounce light (verified in
PIE: a pink cast on the neighbouring wall disappeared). Side effect: it looks dark in ray-traced
reflections; screen-space reflections still show it.

## Material function with pass-through inputs
FunctionInput: `input_name`, `input_type` (`unreal.FunctionInputType.FUNCTION_INPUT_VECTOR3`,
`_SCALAR`...), `sort_priority`, `use_preview_value_as_default=True` + `preview_value` (the default
when the caller leaves it unconnected). FunctionOutput: `output_name`, `sort_priority`.
Call it from a material: `MaterialExpressionMaterialFunctionCall` +
`set_editor_property("material_function", mf)`; its pins are the function's input/output names.

## Injecting a function into existing materials
For each property (BaseColor, Emissive, Roughness, Metallic, Specular, Normal): read the current
source node + output name, connect it to the function input of the same name, then connect the
function output to the property. Unconnected properties fall back to the input's preview value
(use the engine's defaults: BaseColor 0.5 grey *(engine default unverified)*, Roughness 0.5,
Specular 0.5, Metallic 0, Normal (0,0,1)). Skip materials that already contain the call.
*(Not yet tried on Substrate-native materials with a Slab node on Front Material, nor on
Material-Attributes materials.)*

## Flat, unshaded colour on lit materials (graphic "cut-out" look)
Verified with Lumen + Ultra Dynamic Sky: BaseColor 0, Specular 0, Roughness 1, Normal (0,0,1),
colour only from Emissive → every pixel of a surface renders the same sRGB (p10 = p90). What still
changes it: auto exposure (lock it), vignette (the largest variation), bloom, local exposure, lens
flares, fringe, film grain → an unbound PostProcessVolume with high priority overriding
`vignette_intensity 0, bloom_intensity 0, local_exposure_highlight/shadow_contrast_scale 1,
lens_flare_intensity 0, scene_fringe_intensity 0, film_grain_intensity 0` (set `override_<name>`
True on the `settings` struct, then set the struct back). Height fog still tints distant surfaces;
the emissive still bounces into Lumen GI on neighbours (no per-material switch found in 5.8).
Calibrate the emissive by measuring rendered pixels (saturated colours shift toward orange/white
when too bright; the tonemapper is non-linear, so tune the weak channels separately).

## Screen-space colour over sky / whole frame (post-process)
Post-process material: `material_domain = MD_POST_PROCESS`,
`blendable_location = BlendableLocation.BL_SCENE_COLOR_AFTER_TONEMAPPING`; `MaterialExpressionSceneTexture`
with `scene_texture_id = SceneTextureId.PPI_POST_PROCESS_INPUT0` (pin `"Color"`) and `PPI_SCENE_DEPTH`
(mask R); a Custom node `lerp(Col.rgb, Red, max(step(SkyDist, Depth) * SkyOn, FullOn))` → Emissive.
After tonemapping the input is display-encoded: a target sRGB value / 255 lands exactly
((0.914, 0.165, 0.110) rendered (233, 42, 28)). Depth > ~2 km catches sky, volumetric clouds and the
empty horizon. Put it on a PostProcessVolume: `settings.weighted_blendables.array` += a
`WeightedBlendable` (weight 1, object = material), then set the settings struct back.

## Data textures (e.g. a float field)
- Write a 16-bit grayscale PNG with numpy + zlib (no PIL needed), import with `AssetImportTask`
  (`replace_existing=True, automated=True`), then set `srgb=False`,
  `compression_settings=TC_SINGLE_FLOAT` (R32F), `mip_gen_settings=TMGS_NO_MIPMAPS`,
  `never_stream=True`, `address_x/y=TA_CLAMP`. Import goes through Interchange in 5.8.
- Row 0 of the PNG = V 0 of the texture.

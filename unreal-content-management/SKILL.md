---
name: unreal-content-management
description: Moving, renaming and reorganising Unreal Engine 5.8 content from Python without breaking it — batch asset moves and redirectors, moving maps (Save As route and the crash to avoid), World Partition and one-file-per-actor levels (external actors, the WorldPartitionRenameDuplicateBuilder commandlet), what adding a sample project's content does to project config, backups, and Content Browser folder colours. Load with unreal-mcp before any folder clean-up or asset move.
---

# Reorganising Unreal content safely

Verified Oct 2026 on UE 5.8.4 while cleaning up a project that had our own assets plus the Electric
Dreams sample (44 GB, 24k files) and Ultra Dynamic Sky. Load `unreal-mcp` first.

## Before touching anything
- **Back up** `Content`, `Config` and the `.uproject` (no source control here). `robocopy <src> <dst>
  /E /MT:16 /R:1 /W:1 /NFL /NDL /NP /LOG:<log>` copied 44 GB / 24k files in 29 s on NVMe; exit codes
  0–7 are success (1 = files copied). Compare file count and bytes afterwards.
- **Survey first:** top-level folders with size and file count, every `.umap` outside
  `__ExternalActors__`, and every `/Game/...` string in `Config/*.ini`.
- **Count maps that store actors as separate files:** walk `Content/__ExternalActors__/` — the path up
  to the first hashed 1–2 char folder is the owning map (`Levels/ElectricDreams_Env` owned 15,174
  files). A crude World Partition check: the `.umap` bytes contain `WorldPartition`.
- Stop PIE; know which level is open and what is dirty
  (`EditorLoadingAndSavingUtils.get_dirty_content_packages()` / `get_dirty_map_packages()`).

## Moving ordinary assets
- `EditorAssetLibrary.rename_asset(src, dst)` works and saves. **Move a set in one batch**
  (`AssetToolsHelpers.get_asset_tools().rename_assets([AssetRenameData...])`) or dependencies first:
  moving one at a time, an asset moved before what it references saved the OLD paths, and no
  redirector was left for them (redirectors only appear where an on-disk referencer still points) →
  "LoadErrors: ... dependent package ... was not available". Fix = rebuild/resave the asset.
- `AssetTools.fixup_referencers` is **not exposed to Python** in 5.8. Instead load the referencers
  (e.g. open the level), save them (references through redirectors get written with the new paths),
  then delete the `ObjectRedirector` assets (`find_asset_data(p).asset_class_path.asset_name`).
- Rename prompt: "Source code, config INI, and text files may need Find/Replace ... Continue with
  rename?" (`AssetRenameManager.cpp`). It fires when any asset in the batch is referenced (hard or
  soft) from a **native class default object** — config-driven settings like `GameMapsSettings`
  (startup/default map, game mode, game instance), audio settings, etc. It is ONE OkCancel per
  `rename_assets` call; unattended scripts get Cancel → the whole call returns False. Either clear
  those settings temporarily or run that one call non-unattended so a human clicks OK.
- Deleting a loaded asset can fail ("Failed to unload all packages during ForceDeleteObjects") and a
  following `create_asset` returns None — clear and reuse instead.
- Files the editor reports deleted may stay on disk while it holds them; moving them aside (outside
  `Content`) after the editor let go is fine.

## Moving maps
- Never `load_asset` / `duplicate_asset` a map you will open with `load_level` in the same session
  (crash, see `unreal-mcp`).
- `EditorLoadingAndSavingUtils.save_map(editor_world, new_path)` writes a **copy** and keeps the old
  map open; the copy is then in memory as an asset → restart the editor, `load_level(new)`, save it,
  delete the old map (only delete it — never open it again that session).
- Sequencer possessable bindings did not survive the level move (camera stopped animating) →
  rebuild the bindings (re-run the sequence setup).
- **World Partition / one-file-per-actor maps:** a rename re-homes only the external actor packages
  that are loaded at that moment (`AssetRenameManager` uses `Package->GetExternalPackages()`;
  `ExternalPackageHelper` repackages loaded objects). A WP map that isn't open has none loaded → its
  actor files would stay under the old `__ExternalActors__/<old path>` and the moved map comes up
  empty. Supported route: the headless builder, editor closed, one map per run:
  `UnrealEditor-Cmd.exe <project> <MapPath> -run=WorldPartitionBuilderCommandlet
  -Builder=WorldPartitionRenameDuplicateBuilder -NewPackage=<NewPackagePath> -Rename`
  *(found in source `WorldPartitionRenameDuplicateBuilder.h`; not run yet — unverified)*.
  Non-WP one-file-per-actor levels (level-instance assemblies) have no safe scripted move.
  Electric Dreams had 105 such maps → we decided to leave its layout alone.

## What adding a sample's content does (Electric Dreams via the launcher "Add to project")
- Content lands as ~20 top-level folders (not one folder).
- `DefaultEngine.ini` was **replaced**: our sections vanished (Python remote execution, our startup
  map); new `EditorStartupMap` (its Startup info level), `GameDefaultMap`, `GlobalDefaultGameMode`
  (a character game mode), game instance, audio submix/sound class; also `DefaultGame.ini`
  (soundscape, control bus mixes), `DefaultGameplayTags.ini`, `DefaultEditor.ini` (map list).
  Renderer settings stayed compatible (Substrate, Lumen, HW RT, VSM).
- Restore: re-add your ini sections, set `GameMapsSettings` CDO `editor_startup_map` (SoftObjectPath)
  AND the ini line (read back with `.export_text()` — SoftObjectPaths print as `{}`), and give your own
  levels a game mode override (`world_settings.default_game_mode = unreal.GameModeBase`) so Play keeps
  the free camera.
- A duplicate plugin entry can appear in the `.uproject` (fix with a JSON round-trip while the editor
  is closed or before it reads it).

## Folder colours (Content Browser)
No Python API. Stored by `AssetViewUtils::SetPathColor` in GConfig section `[PathColor]` of
`Saved/Config/<Platform>Editor/EditorPerProjectUserSettings.ini`, key = content path, value =
`(R=..,G=..,B=..,A=1.000000)`, cached in memory → write the ini only while the editor is **closed**
(it rewrites the file on exit), or select folders in the Content Browser → right-click → Set Color
(multi-select applies one colour to all). *(ini route not yet verified in the editor)*

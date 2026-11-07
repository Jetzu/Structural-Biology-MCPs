---
name: sessions-and-export
title: Sessions, files and export
app: pymol
description: Save/load .pse sessions (version compatibility, partial merge), export coordinates (pdb/cif/mmtf/sdf/mol2/pqr/mae, multi-state, multisave), sequences (fasta/aln), images, 3D formats (obj/wrl/dae/gltf/pov), maps, camera views, command logs; load/fetch options and paths
tags: save, load, session, pse, pdb, cif, fasta, export, gltf, view, log, fetch
---
Paths are relative to PyMOL's working directory (shown by `pwd`); use absolute paths or `cd /dir` first.
`save` picks the format from the extension. Example object `prot`, selection `lig`.

## Sessions
```pml
save work.pse
set pse_export_version, 1.74
save work_for_old_pymol.pse
set pse_export_version, 0
load work_for_old_pymol.pse, partial=1
load work.pse
```
- `.pse` stores everything (objects, maps, scenes, movies, settings, view). `pse_export_version 1.74` writes
  a file readable by PyMOL 1.7.4+ (loses newer features); 0 = current format. `set pse_binary_dump, 1` makes
  smaller/faster files that older versions cannot read.
- `load x.pse` REPLACES the whole session; `partial=1` merges it into the current one, `partial=2` merges but
  keeps the current camera.
- Before saving for someone else: `set seq_view, 0` (unless wanted) and check `scene` for leftover objects.

## Coordinates
```pml
save lig.sdf, lig
save lig.mol2, lig
save chainA.pdb, prot and chain A
save prot.cif, prot
save prot_all_states.pdb, prot, state=0
save prot.pqr, prot and polymer
save prot.mmtf, prot
multisave several.pdb, prot or lig
```
- `save file, selection, state, format`: `state=-1` (default) current state, `0` all states (multi-model PDB /
  multi-record SDF). Formats: pdb cif mmtf sdf mol mol2 xyz pqr mae pkl (`format=` overrides the extension).
- `multisave` writes one HEADER/END block per object (reloads as separate objects); `save` with a multi-object
  selection writes them flat into one PDB.
- PDB writing switches: `set pdb_use_ter_records, 1`, `set retain_order, 1` (keep input atom order),
  `set pdb_conect_all, 1` (CONECT for every bond, useful for ligands), `set pdb_retain_ids, 1` (keep atom IDs).
- Hydrogens are written if present (`h_add` first if needed); `remove hydro` to drop them.
- Save a superposed structure: coordinates are written in the object's current (transformed) frame.

## Sequences and alignments
```pml
save prot.fasta, prot
save aln.aln, aln_obj
save aln.fasta, aln_obj
```
`python`: `result = cmd.get_fastastr("prot and chain A")` returns the FASTA text directly (one record per
chain, `>prot_A` headers). `get_fastastr` is not a command-line keyword - Python only.

## Images, 3D scenes, maps
```pml
png figure.png, width=1600, height=1200, dpi=300, ray=1
save scene.obj
save scene.wrl
save scene.dae
save scene.gltf
save scene.pov
save lig_map.ccp4, map_obj
```
- See the rendering skill for `png`. `obj`/`wrl`/`dae`/`gltf` export the displayed geometry (cartoon, sticks,
  surfaces) for Blender/Unity; `.gltf` uses the bundled `collada2gltf` (verified). `.pov` for POV-Ray.
- Maps: `save x.ccp4, map_obj` writes a map object (e.g. after `map_trim`).

## Camera and command history
```pml
view fig1, store
view fig1
get_view
log_open commands.pml
color red, lig
log_close
```
- `get_view` prints an 18-number `set_view (...)` block; paste it back with `set_view (...)` to reproduce a
  camera exactly (the `get_view`/`set_view` tools do the same with a list). `view key, store` keeps it in the
  session.
- `log_open file.pml` records every subsequent command to a replayable script (`@file.pml` or `run` tool
  with the lines); `log_close` stops.

## Loading
```pml
fetch 1ubq, prot, async=0
load model.pdb, prot
load traj_frame2.pdb, prot, state=2
load poses.sdf, poses, discrete=1
load frames.xyz, traj
```
- `fetch code, name, type=cif|pdb|pdb1|2fofc|fofc|emd, async=0` (always `async=0` from the agent). `set fetch_path, /dir`
  caches downloads; `set assembly, 1` before fetching a cif loads the biological assembly.
- `load file, object, state`: `state=0` appends a new state (trajectories, docking poses); `discrete=1` keeps
  per-state topologies; `multiplex=1` splits multi-record files into separate objects. `split_states poses`
  makes one object per state afterwards.
- `delete prot` removes an object, `delete all` everything; `reinitialize` resets settings too.

## Pitfalls
- Overwrites silently; check `python`: `import os; result = os.path.exists("work.pse")` before clobbering.
- `fetch`/`load` of a cif into an object name that already exists fails ("loading mmCIF into existing object
  not supported"): `delete prot` first or use a new name.
- `save x.png` ray-traces only if `ray=1` (or in headless mode); otherwise it saves the OpenGL frame.
- Selections (`select`) are saved in .pse but not in PDB files; alignment objects are session-only.
- `.cif` output uses `auth` identifiers; `set cif_use_auth, 0` when LOADING switches to label_* numbering.
- Large sessions with maps: `map_trim` and `set pse_binary_dump, 1` reduce size.

## Verify
- `python`: `import os; result = {f: os.path.getsize(f) for f in ["work.pse", "lig.sdf"] if os.path.exists(f)}`.
- Reload check: `load lig.sdf, lig_check` then `selection_info("lig_check")` -> same atom count; `delete lig_check`.
- `scene` after `load x.pse` lists the restored objects, scenes and view; `log(n=20)` shows PyMOL's "Save: wrote" lines.

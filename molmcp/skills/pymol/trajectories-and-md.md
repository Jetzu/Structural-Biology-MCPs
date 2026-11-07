---
name: trajectories-and-md
title: Trajectories and multi-state objects
app: pymol
description: Load MD trajectories (load_traj dcd/xtc/trr/nc onto a topology, subsample, append), NMR/docking ensembles, intra_fit and smooth, per-state RMSD/RMSF/distance/SASA via python, create/split_states/join_states/delete_states, linear morph, state-sweep movies (mset, mpng), topology-mismatch and memory pitfalls
tags: trajectory, md, dcd, xtc, load_traj, states, intra_fit, smooth, rmsd, rmsf, split_states, join_states, morph, nmr, ensemble, mset
---
In PyMOL a trajectory is one object with many states (frames). Example object `traj`; without trajectory
files use `fetch 1nmr, ens, async=0` (20-state NMR ensemble). Memory/`defer_builds_mode` are in
performance-and-large-systems, camera keyframes and mp4 encoding in movies-and-scenes, pairwise alignment in
structure-alignment, load/save options in sessions-and-export.

## Load
```pml
load system.pdb, traj
remove traj and not polymer
load_traj run.dcd, traj, state=0
load_traj run.xtc, traj, state=0, start=1, stop=5000, interval=10
load_traj run2.nc, traj, state=0, max=200
load poses.pdb, poses, state=0
```
- Topology first (`load`), then `load_traj filename, object, state, format, interval, average, start, stop, max,
  selection, image, shift, plugin`. Always name the object: the default is "object named like the file, else
  the last object". Format comes from the extension (dcd, xtc/trr via the gromacs plugin, nc = Amber NetCDF,
  crd/mdcrd); for another extension pass `format=dcd` or `plugin=dcd` (otherwise "unknown format 'bin'").
- `state=0` appends after the last state and keeps the topology coordinates as state 1 (handy reference
  frame); `state=1` (default) overwrites from state 1. `start`/`stop`/`interval` subsample on read (frames 2-8
  step 2 -> 4 states), `max=N` caps the number of states. Prune atoms (`remove`) BEFORE `load_traj` - after it
  the atom count no longer matches the file.
- Atom count must match exactly or PyMOL prints "number of atoms in the object (602) did not equal the number
  of atoms in the 'dcd' file (660)" and raises "Could not load trajectory"; a missing file prints "plugin 'dcd'
  cannot open ..." and raises the same exception.
- A multi-model PDB loads all models as states; `load file.pdb, obj, state=0` or `load_traj file.pdb, obj,
  state=0` appends them. Check with `python`: `result = cmd.count_states("traj")`.

## Navigate states
```pml
frame 25
set state, 25, traj
set all_states, 1, ens
```
- With no movie defined `frame N` sets state N for every object (`get_state`, settings `state` and `frame`
  follow); `rewind`/`ending`/`forward`/`backward`/`middle` step states. `set state, N, obj` changes only that
  object. `set all_states, 1, obj` draws every state at once (NMR bundle); `0` restores.

## Fit and smooth
```pml
intra_fit traj and name CA, 1
intra_rms_cur traj and name CA, 1
smooth traj, 1, 3
```
- `intra_fit selection, state` fits every state of ONE object onto the reference state and returns the
  per-state RMSD list (-1.0 at the reference). `intra_rms` (fit without moving) and `intra_rms_cur` (no fit)
  return the same list shape. A reference state that does not exist gives a list of all -1.0 with no error;
  a selection spanning two objects raises an empty "Error:".
- `pbc=1` is the default (periodic unwrap); the warning "PBCUnwrap-Warning: Space group is not 'P 1'" on a
  crystal topology is harmless; `pbc=0` skips it.
- To superpose a trajectory on a separate reference object, do NOT loop `fit`/`align` with `mobile_state=s`:
  the transform is computed from state s but applied to ALL states (verified). Instead load the reference as
  state 1 (`load ref.pdb, traj` then `load_traj run.dcd, traj, state=0`) and `intra_fit traj and name CA, 1`,
  or build one object with `join_states`.
- `smooth selection, passes, window, first, last, ends` (`cutoff`, `pbc`) is a running window average of
  coordinates: fit first; even windows round up (`window=4` equals 5); `ends=0` (default) leaves the first and
  last states untouched; it rewrites the states, so reload to undo.

## Per-state analysis via `python`
```python
import numpy as np
obj, ref = "traj", 1
n = cmd.count_states(obj)
cmd.intra_fit(f"{obj} and name CA", ref, pbc=0)
rmsd = cmd.intra_rms_cur(f"{obj} and name CA", ref)                       # -1.0 at ref
d = [cmd.get_distance(f"{obj}///1/CA", f"{obj}///76/CA", state=s) for s in range(1, n + 1)]
xyz = np.array([cmd.get_coords(f"{obj} and name CA", s) for s in range(1, n + 1)])
rmsf = np.sqrt(((xyz - xyz.mean(0)) ** 2).sum(2).mean(0))
keys = []
cmd.iterate(f"{obj} and name CA", "keys.append((chain, resi))", space={"keys": keys})
stored.rmsf = dict(zip(keys, rmsf.tolist()))
cmd.alter(obj, "b = stored.rmsf.get((chain, resi), 0.0)")
cmd.spectrum("b", "blue_white_red", f"{obj} and name CA")
result = {"states": n, "rmsd": [round(x, 2) for x in rmsd], "d_1_76": [round(x, 2) for x in d],
          "rmsf_max": round(float(rmsf.max()), 2)}
```
- `cmd.get_coords(sel, state)` -> (atoms, 3); `state=0` stacks all states (n*atoms, 3). `cmd.get_coordset(obj,
  state)` is the per-object equivalent. `iterate_state N, sel, expr` reads x/y/z of one state (0 = every
  state), `alter_state N, sel, x=x+5` edits them.
- RMSD against another object without moving anything: `cmd.rms_cur("traj and name CA", "ref and name CA",
  mobile_state=s, target_state=1)`; for a different topology use `align ..., transform=0` per state.
- Per-frame SASA: `set dot_solvent, 1` then `cmd.get_area("traj and polymer", state=s)`.
- `distance name, a, b` with the default `state=0` builds one measurement that follows the frame
  (`dynamic_measures` on) and RETURNS THE MEAN over states; `state=N` measures one state. Secondary structure
  is per atom, not per state: `dss traj, 1` assigns it from state 1 and the cartoon keeps it in every frame.

## Extract, merge, prune, export
```pml
create frame50, traj, 50, 1
create ends, traj, 1, 1
create ends, traj, 200, -1
split_states ens, 1, 5, prefix=m
join_states ens2, m*, mode=1
delete_states traj, 1-10 101-200
save frames.pdb, traj, state=0
save frame50.pdb, traj, state=50
```
- `create name, sel, source_state, target_state`: `target_state=-1` appends to an existing object.
  `split_states obj, first, last, prefix` -> `m0001`... (default prefix `obj_0001`); `join_states name, sel,
  mode` with mode 0 discrete (different molecules), 1 identical topology, 2 (default) common atoms only,
  3 sequence-matched. `delete_states obj, 1-3 8-10` takes space-separated ranges.
- `save` with `state=0` writes a multi-model PDB (MODEL records) or multi-state mmCIF; `state=N` one state.
  PyMOL cannot write dcd/xtc/trr/crd/nc ("File format not supported for export") - export PDB/mmCIF or `.pse`.
  The MCP `save_file(path, selection, format, state)` defaults to `state=-1` (current state only); pass
  `state=0` for every state.

## Morph (interpolated trajectory)
```pml
morph mo, open, closed, method=linear, steps=30
morph sweep, ens, state1=0, method=linear, steps=5, refinement=0
```
- `morph name, sele1, sele2, state1, state2, refinement, steps, method, match`: `method=linear` works in the
  open-source build; `rigimol` (the default) needs an incentive licence ("No license file found"). Two states
  of one object: `morph mo, traj, state1=1, state2=200` (defaults: state 1 -> state 2); `state1=0` chains all
  consecutive states and back (N*steps states), `state1=0, state2=0` stops at the last ((N-1)*steps).
  `refinement` = sculpting cycles (0 = fastest).

## Movies from states
```pml
mset 1 -200
mpng frames/md_, 1, 200, width=1280, height=720, mode=2
mset
```
- `mset 1 -200` maps frame i -> state i (`mset 1 -200 -1` bounces back; `mset 1 x30 1 -200` holds state 1 for
  30 frames; with `mset 1 x5 1 -10` frame 8 is state 3). `mset` alone (or `mset ""`) removes the movie, so
  `frame` again equals state; `mclear` only drops cached images.
- `mpng ..., mode=2` ray-traces every frame headless (default `mode=-1` follows `ray_trace_frames`); `mode=1`
  returns without error but writes NOTHING headless ("MoviePNG-Error: Missing rendered image") - check the
  directory. Camera keyframes (`mview`),
  `movie.add_state_sweep` and ffmpeg encoding: movies-and-scenes.

## Pitfalls
- Each state stores ~12 bytes per atom plus cached geometry: 100k atoms x 1000 frames = 1.2 GB of
  coordinates alone. Subsample (`interval`, `max`), `remove` solvent before loading, `delete_states` later,
  and `set defer_builds_mode, 3` before loading (performance-and-large-systems).
- A `load_traj` with `state=1` on a loaded trajectory silently overwrites existing states instead of appending.
- An empty or truncated Amber `.crd`/`.mdcrd` hangs `load_traj` (verified, PyMOL 3.1): check the file first.
- `fit`/`align` move every state of the mobile object; `intra_fit` is the only per-state fit.
- Colours/representations are per atom, shared by all states; B-factors written by the RMSF recipe overwrite
  the crystallographic ones (keep a `create ref, traj, 1, 1` copy first).

## Verify
- `scene` -> each object lists `states`; `state`/`frame` give the current frame, and a `run` that changes it
  reports `state_or_frame` in `changes`. `python`: `result = (cmd.count_states("traj"), cmd.get_state())`.
- `measure("distance", ...)` reads the current state: `frame 150` first, then compare with
  `cmd.get_distance(..., state=150)`.
- `render()` at frame 1 and after `frame 100`, then `compare_renders()` -> `changed_fraction` > 0 proves the
  frames differ (a trajectory loaded onto the wrong topology shows 0).
- `residue_table("traj and name CA")` -> `b_mean` holds the RMSF after the recipe above; `ss` shows the
  per-atom assignment used in every frame.

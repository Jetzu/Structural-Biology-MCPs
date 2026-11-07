---
name: trajectories-and-coordsets
title: Trajectories, coordinate sets and morphs
app: chimerax
description: Open MD trajectories (dcd/xtc/trr/nc onto a topology model or PSF, multi-model PDB/mmCIF as coordsets), jump/play frames with coordset, morph between conformations, per-frame RMSD/distance/SASA with perframe, save frames or DCD, and record a trajectory movie
tags: trajectory, coordset, dcd, xtc, trr, psf, amber, gromacs, md, morph, perframe, rmsd, frames, nmr ensemble, movie
---
Use for "load my MD trajectory", "go to frame 50 / play it", "morph open → closed", "RMSD per
frame", "distance over time", "movie of the simulation". Verified against the ChimeraX 1.11 docs
and headless runs. Related skills: `movies` (record/encode options, motions), `structure-alignment`
(matchmaker/align/rmsd details), `sessions-and-export` (open/save basics, file paths).

## 1. Open a trajectory
```
open ~/md/topology.pdb                              # topology = any atomic model with the SAME atoms, same order (.pdb .cif .gro .mol2 .psf)
open ~/md/traj.dcd structureModel #1                # coordinates onto #1; also .xtc .trr (Gromacs), .nc (Amber NetCDF), .dump (LAMMPS)
open ~/md/traj.xtc structureModel #1 start 1 end 5000 step 10   # subsample while reading (integers; not for PDB/mmCIF)
open ~/md/system.psf coords ~/md/traj.dcd           # PSF topology + coordinate file in one command
open ~/md/part2.dcd structureModel #1 replace false # append frames (default: replace when #1 has 1 frame, append when it is a trajectory)
open ~/nmr/ensemble.pdb coordsets true              # multi-MODEL PDB/mmCIF as ONE trajectory (default = submodels #1.1, #1.2 …)
open 1plx coordsets true                            # fetch an NMR ensemble as a trajectory
open ~/traj.pdb coordsets true missingCoordsets fill   # gaps in MODEL numbers: fill | ignore | renumber (default)
open ~/md/traj.dcd structureModel #1 slider false   # no GUI slider
```
Log (`output`): "Replaced existing frames of X #1 with 2000 new frames" (appending: "Added 2000 frames
to X #1") / "ensemble.pdb has 20 coordinate sets"; `info #1` → "… 660 atoms, … 1 chains (A), 2000
coordsets". Atom-count mismatch fails with "Specified structure has 1218 atoms whereas the coordinates
are for 660 atoms": strip water/ions/hydrogens on the same side (gmx trjconv / cpptraj) before opening.
`.gro` opens as a plain structure (fine as topology); `.tpr`/`.prmtop` cannot be read; `.xtc`/`.trr`/`.nc`
are read-only. With exactly one atomic model open it is used automatically; with several you must give
`structureModel` ("Must specify an atomic model to read the coordinates into").

## 2. Jump and play (coordset)
```
coordset #1 50                         # show frame 50;  coordset #1 -1 = last frame
coordset #1                            # play 1 → last, one trajectory frame per graphics frame
coordset #1 1,200 ; wait 200           # explicit range; wait N = frames × pauseFrames, else later commands run early
coordset #1 .,300 ; coordset #1 50, ; coordset #1 200,1    # from current frame; from 50 to end; backwards
coordset #1 1,2000,10 ; wait 200       # every 10th frame
coordset #1 1,200 pauseFrames 3 ; wait 600            # slower (3 graphics frames per trajectory frame)
coordset #1 1,200 loop 3 bounce true ; wait 1200      # repeat; bounce = forward then backward (ends at frame 1)
coordset #1 1,200 holdSteady #1/A:20-80@CA            # re-fit each frame on a core: removes tumbling/diffusion
coordset #1 1,200 computeSs true       # dssp every frame so cartoons follow (un)folding; slower
coordset stop #1
coordset slider #1 pauseFrames 2 movieFramerate 25    # GUI only: slider, play/pause, record button, Plot menu
```
The slider's context menu → Plot: distances, angles, torsions, SASA, best-fit RMSD and H-bonds over
all frames from a selection, with Save CSV. Only one frame is ever displayed; `coordset #1 N` is
the way to put a specific frame on screen before `render`, `save` or a measurement.

## 3. Morph between conformations
```
open 1ake ; open 4ake ; mm #2 to #1          # superimpose first — morph interpolates, it does not fit
morph #1,2 frames 50                         # → model "Morph - …" (#3) with 1 + 50 frames; plays once; inputs hidden
morph #1,2,3 frames 30 wrap true             # several stages (1 + 30×3 frames), last → first included
morph #1.1-20 same true                      # same numbering/naming (NMR members, same construct): faster pairing
morph #1,2 frames 50 hideModels false play false slider false modelId 5
morph #1,2 frames 50 cartesian true          # straight-line interpolation: fast, fine for ribbons, distorts side chains
morph #1,2 frames 50 rate sinusoidal         # linear (default) | "ramp up" | "ramp down" | sinusoidal
morph #1,2 frames 50 colorSegments true      # colour rigid segments; colorCore gold colours the initial core
morph #1,2 method linear coreFraction 0.5 minHingeSpacing 6   # hinge detection knobs (defaults corkscrew/0.5/6)
```
Log: "Computed 51 frame morph #3", then ChimeraX itself runs `coordset #3 1,51`. Only atoms common
to all inputs survive (chains paired by ID or order, residues by sequence alignment, ligands only
when bonded to paired residues); unequal chain counts fail ("models have different number of chains,
1 (…) and 2 (…)") → `delete`/`split` extra chains first.
Replay with `coordset #3 …`; record as in section 6.

## 4. Per-frame measurements (perframe drives the frame with $1)
```
combine #1 modelId 9 name ref ; coordset #9 1      # frozen copy as reference (copies all frames; its active frame stays put)
perframe "coordset #1 $1; rmsd #1@CA to #9@CA" range 1,200 ; wait 200 ; ~perframe                  # in-place RMSD per frame
perframe "coordset #1 $1; align #1@CA toAtoms #9@CA move nothing" range 1,200 ; wait 200 ; ~perframe  # best-fit RMSD, nothing moves
perframe "coordset #1 $1; distance #1:1@CA #1:76@CA monitor false" range 1,2000,10 ; wait 200 ; ~perframe
perframe "coordset #1 $1; measure sasa #1" range 1,200 ; wait 200 ; ~perframe
hbonds #1 restrict both log true                   # no perframe needed: on a trajectory one hbonds call does ALL frames
perframe "coordset #1 $1; hbonds #1 restrict both coordsets false" range 1,200 ; wait 200 ; ~perframe   # per-frame count only
perframe "coordset #1 $1; rmsd #1@CA to #9@CA" range 1,200 showCommands true ; wait 200 ; ~perframe   # echoes "perframe N: …" before each value
```
`range a,b,step` executes (b−a)/step+1 times → `wait` exactly that many. Always end with
`~perframe`. Values appear in order in the log: "RMSD between 76 atom pairs is 4.650" (align adds
"angstroms"), "Distance between … CA and … CA: 34.057Å", "Solvent accessible area for #1 (660 atoms) =
8887.7", "145 hydrogen bonds found". `distance` without `monitor false` errors from the 2nd frame on
("Distance already exists"). `hbonds` on a trajectory defaults to `coordsets true` → one call does every
frame ("787 hydrogen bonds found in 10 coordsets"; `log true` adds a "Coordinate set N / M H-bonds" block
per frame); the default `restrict any` also counts bonds to other open models (the `#9` copy, a second
topology) — `restrict both` or `interModel false` keeps them out.
For thousands of frames or a table, compute in Python (`python` tool) instead of logging:
```python
import numpy as np
m = [s for s in session.models.list() if s.id_string == "1"][0]       # trajectory model
ca = m.atoms.filter(m.atoms.names == "CA"); orig = m.active_coordset_id
m.active_coordset_id = int(m.coordset_ids[0]); ref = ca.coords.copy(); rows = []
for cs in m.coordset_ids:                                              # ca.coords always reads the active frame
    m.active_coordset_id = int(cs)
    rows.append([int(cs), round(float(np.sqrt(((ca.coords - ref) ** 2).sum(1).mean())), 3)])
m.active_coordset_id = orig
result = {"frames": int(m.num_coordsets), "rmsd_ca_vs_first": rows}
```

## 5. Save frames
```
save ~/out/frame_050.pdb #1                  # current frame only (set it with coordset first); .cif likewise
save ~/out/all_frames.pdb #1 allCoordsets true   # multi-MODEL PDB/mmCIF; re-open with coordsets true
save ~/out/subset.dcd models #1              # DCD of every frame of #1 (models listed must share one atom count)
```
Lighter copy of a huge run: `open … start/end/step`, then `save ….dcd`. `.xtc`/`.trr`/`.nc` cannot be
written ("Can only open, not save, .xtc files").

## 6. Record a trajectory or morph movie
```
coordset #1 1 ; view ; lighting soft ; graphics silhouettes true
movie record supersample 3
coordset #1 1,200 pauseFrames 2 holdSteady @CA ; wait 400
movie encode ~/out/traj.mp4 quality high framerate 30
```
Same for a morph with `coordset #3 1,51`. Image series instead of a movie:
`perframe "coordset #1 $1; save ~/frames/$1.png width 1200" range 1,200 zeroPadWidth 4 ; wait 200 ; ~perframe`.
Both need a graphics window (or Linux `--offscreen`); the GUI slider's record button writes
movie1.mp4, movie2.mp4 … into the `snapshot` directory. All encode options: skill `movies`.

## 7. Verify
- `scene` → every atomic model reports `coordsets` and, for trajectories, `active_coordset`: after
  `coordset #1 50` it reads 50; after a play + `wait` it is the end frame (loop/bounce: frame 1).
- `run` → the perframe lines appear in frame order in the `output` of the line that contains `wait` (the
  bridge splits commands on newlines, not `;`, and captures the log per line); `log` re-reads them if a
  line errored.
- `measure(kind="rmsd", spec1="#1@CA", spec2="#9@CA")`, `kind="distance"` or `kind="sasa"` on the
  current frame cross-checks one perframe value; `kind="count"` on topology and trajectory models
  confirms equal atom counts before `structureModel`.
- `render`, `coordset #1 -1`, `render`, `compare_renders` → a non-zero diff proves the frames differ;
  `residue_table` `ss` column changes only with `computeSs true` or an explicit `dssp`.
- Morph: `scene` lists "Morph - …" with `coordsets` = 1 + frames × stages and the inputs hidden.

## Pitfalls
- No `wait` → the next command (rmsd, save, movie encode) runs at the start frame. Count = frames × pauseFrames.
- One `run` call blocks for the whole `wait`; split plays longer than a few hundred frames across calls (600 s limit).
- Topology and coordinates must match atom by atom; a model fetched from the PDB rarely matches a
  simulation (hydrogens, caps, solvent) — use the structure file written by the MD package.
- Periodic-boundary jumps and drift are not corrected; `holdSteady` only re-fits. Unwrap/centre in gmx/cpptraj.
- `combine` copies all coordsets and keeps the frame #1 showed at that moment — set the reference frame explicitly.
- Cartoons keep the SS of the frame they were computed on; use `computeSs true` or `perframe dssp interval 5`.
- `morph` hides its inputs (`hideModels false` keeps them) and must be re-run after any re-superposition.
- Per-residue attribute colouring (B-factor, pLDDT) is static over frames; only geometry changes.

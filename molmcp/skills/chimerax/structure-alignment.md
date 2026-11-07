---
name: structure-alignment
title: Structure superposition and comparison
app: chimerax
description: Superimpose structures with matchmaker (sequence + secondary structure), align (explicit atom pairs), report RMSD without moving (rmsd), show the sequence alignment with its RMSD header, tile for side-by-side views, and save aligned coordinates
tags: alignment, matchmaker, align, rmsd, superposition, sequence viewer, tile, compare
---
Use for "superimpose / overlay / align these structures", "RMSD between…", "compare the two
conformations". Syntax verified against the ChimeraX 1.11 docs.

## 1. matchmaker (sequence alignment → iterative CA / C4' fit)
```
matchmaker #2 to #1                      # best chain pair, BLOSUM-62 + 30 % SS score, 2.0 Å pruning
mm #2-5 to #1                            # each of #2…#5 independently onto #1
mm #2 to #1 bring #3                     # move #3 rigidly together with #2
mm #2/B to #1/A pairing ss               # specific chain pairs (equal numbers of chains)
mm #2 to #1/A pairing bs                 # best chain of #2 onto chain A of #1
mm #2 to #1 showAlignment true           # open the pairwise alignment in the Sequence Viewer
mm #2 to #1 cutoffDistance none          # no iterative pruning (RMSD over all aligned pairs)
mm #2 to #1 cutoffDistance 5.0 alg sw matrix PAM-150 ssFraction false
mm #2 to #1 matrix Nucleic               # nucleic acids need the Nucleic matrix
mm #2:1-150 to #1:1-150                  # restrict to a domain (only when the default fit is wrong)
mm #2 to #1 reportMatrix true verbose true
```
Log (in `output`): "RMSD between N pruned atom pairs is X Å; (across all M pairs: Y)". `computeSS
true` (default) recomputes DSSP for scoring without changing assignments (`keepComputedSS true` keeps).

## 2. align (explicit atom pairs, equal counts)
```
align #2@CA toAtoms #1@CA                                     # paired in order; moves model #2
align #2/A:10-120@CA toAtoms #1/A:10-120@CA cutoffDistance 2.0
align #2@CA toAtoms #1@CA matchNumbering true matchChainIds true   # pair by residue number + chain
align #2:LIG toAtoms #1:LIG matchAtomNames true               # ligands by atom name
align #2@CA toAtoms #1@CA move nothing                        # report RMSD only, move nothing
align #2@CA toAtoms #1@CA each chain                          # fit every chain separately
align #2@CA toAtoms #1@CA reportMatrix true
```
`move` may be `atoms`, `residues`, `chains`, `structures` (default), `structure-atoms`, `nothing`.

## 3. RMSD in place (no fitting)
```
rmsd #1@CA to #2@CA                      # same atom count; paired by chain, residue number, atom name
rmsd #1/A:50-80@CA to #2/A:50-80@CA
```

## 4. Sequence tools
```
sequence chain #1/A                       # Sequence Viewer for one chain
mm #2 to #1 showAlignment true            # alignment + RMSD header (bar height = spatial deviation)
sequence match #2/A to #1/A               # superpose using an already open alignment
sequence identity 1.A                     # pairwise % identity for alignment id 1.A (viewer title bar)
sequence header rmsd save ~/rmsd.txt      # save the per-column RMSD header
```
The Sequence Viewer is a GUI panel: not part of `render`; its data goes to the log or files.

## 5. Show the comparison
```
color #1 cornflower blue; color #2 orange red            # one colour per model
hide atoms; cartoon                                      # ribbons only
tile #1,2 columns 2                                      # side by side; tile off re-superimposes
view
```
After `alphafold match`/`esmfold match`: `color byattribute c_alpha_distance #2 palette bluered range 0,5`.
For two experimental structures the RMSD header of the alignment plays that role.

## 6. Save results
```
save ~/aligned_2.pdb #2 relModel #1       # #2 written in #1's frame (re-opens superimposed)
save ~/both.cif #1,2                      # several models in one mmCIF
view matrix                               # model/camera transforms; measure rotation #2 toModel #1
save ~/session.cxs                        # keeps the positions of all models
```

## 7. Verify
- `run` → `changes` mentions the moved model; `scene` marks moved models with `positioned: true`.
- Read RMSD and pair count from `output`; a pruned count far below the chain length means only a
  core superimposed (domain motion, different conformations) — say so.
- `layout by="model"` → both models' `bbox`/`centroid_frac` should coincide; `occlusion=true`
  quantifies overlap. `render` → `palette` shows both colours.
- Bad fit (RMSD > 5 Å, few pairs): try `pairing ss` with explicit chains, `alg sw`,
  `cutoffDistance none`, restrict to the domain, or `align` with `matchAtomNames` for ligands.

## Pitfalls
- `matchmaker` fits CA (C4' for nucleic acids) only; use `align` for all-atom or ligand fits.
- The match spec may not contain parts of the reference model.
- `sym` copies are graphical clones unless `copies true`; they cannot be matched or saved.
- `rmsd` and `align` need identical atom counts; `selection_info` on both specs shows counts
  (missing residues or altlocs are frequent causes of mismatch).
- Coordinates saved without `relModel` are in scene coordinates (moved model written as moved).

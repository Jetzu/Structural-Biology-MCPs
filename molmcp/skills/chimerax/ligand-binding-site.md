---
name: ligand-binding-site
title: Ligand binding sites: pocket residues, contacts and figures
app: chimerax
description: Find ligands, select the pocket, show interactions (hbonds, contacts, clashes), style and render a binding-site figure
tags: ligand, binding site, pocket, hbonds, contacts, figure
---
When to use: "show the ligand and its binding site", "which residues contact the inhibitor", "make a binding-site figure".

1. Find the ligand(s): `scene` lists `non_polymer_residues`/`ligand_like` per model; or `run`:
   ```
   info residues ligand
   ```
   The `ligand` category excludes ions and solvent; add `ions` if a metal matters. For a specific residue name: `:LIG`.
2. Define the pocket (residues within 5 Å of the ligand, whole residues) and show it:
   ```
   select ligand
   name site ligand :< 5 & protein
   show site atoms
   style ligand ball
   style site stick
   color site byhetero
   color ligand byhetero
   hide solvent
   ```
   `selection_info(spec="site")` reports the residue list; `residue_table(spec="site")` gives numbers and chains.
3. Interactions:
   ```
   hbonds ligand restrict cross reveal true color yellow log true
   contacts ligand restrict cross reveal true intraMol false color gray log true
   clashes ligand restrict cross reveal true log true
   ```
   The `run` tool with json=True returns the listed pairs structured; otherwise the log text has the pair table.
   `contacts(spec1="ligand", spec2="protein", polar_only=True)` is the quick structured alternative.
4. Frame the figure:
   ```
   view ligand :< 6
   cartoon
   transparency 70 target c
   lighting soft
   graphics silhouettes true
   label site text "{0.name}{0.number}" height 0.7 bgColor none
   ```
   Optional pocket surface: `surface site enclose protein` then `transparency site 60 target s`.
5. Check with `render`: the ligand should be near the centre (`centroid_frac` ≈ 0.5), nothing clipped, labels
   legible; `layout(by="items", items=["ligand", "site"])` tells whether the ligand is occluded by the pocket.
6. Report residues (chain:name number), hydrogen-bond partners with distances, and the render path. Clean-up when
   asked: `~label`, `~hbonds`, `~contacts`, `transparency 0 target c`.
Pitfalls: `restrict cross` keeps only ligand↔other-atom pairs; use `both` to also include ligand-internal pairs.
Multiple copies of a ligand: `:LIG` selects all; `/A:LIG` one chain. Covalent ligands count as `ligand` too.

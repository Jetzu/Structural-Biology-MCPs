---
name: surfaces-and-electrostatics
title: Surfaces and electrostatics
app: pymol
description: Molecular/SAS surfaces, transparency and quality, ignore flags, carving a pocket surface, cavity modes, SASA, and surface colouring by electrostatic potential (APBS plugin API or vacuum ESP) with ramp_new
tags: surface, electrostatics, apbs, pdb2pqr, transparency, cavity, carve, sasa, ramp
---
Example object `prot` (protein), ligand selection `lig`. PyMOL 3.1 incentive bundles `apbs` and `pdb2pqr`
(verified under /Applications/PyMOL.app/Contents/bin); open-source builds need them on PATH.

## Surfaces
```pml
show surface, prot and polymer
set surface_quality, 1
set transparency, 0.35, prot
set surface_color, white, prot
set two_sided_lighting, 1
set surface_color_smoothing, 1
```
- `surface_quality` -4..4 (0 default, 1 for figures, 2+ only for small systems). `transparency` 0-1, per object.
- Solvent-accessible instead of molecular surface: `set surface_solvent, 1` (probe `solvent_radius`, 1.4).
- Dot/mesh style surface: `set surface_type, 1` (dots) or `2` (mesh); or `show mesh`/`show dots` reps.
- Ligands and other HETATM groups carry the `ignore` flag and are left out of surfaces and `get_area`. To
  include them: `flag ignore, lig, clear` (and `rebuild`). `set surface_mode, 1` surfaces all atoms regardless.
- Only surface part of an object: `show surface, prot and chain A` (surface is per atom); for a surface that
  ends cleanly use `set surface_smooth_edges, 1`.
- `surface_proximity 0` stops drawing triangles that touch hidden atoms (crisper partial surfaces).

Pocket surface (carve around the ligand, settings are per object):
```pml
set surface_carve_selection, lig, prot
set surface_carve_cutoff, 8, prot
show surface, prot and polymer
```
Undo with `unset surface_carve_selection, prot` / `unset surface_carve_cutoff, prot`.

Cavities/pockets only: `set surface_cavity_mode, 1` (0 normal; 1 cavities and pockets; 2/3 culled variants),
tune `surface_cavity_radius` (7) and `surface_cavity_cutoff` (-3); `cavity_cull 10` removes small interior pieces.

Area (SASA):
```pml
flag ignore, lig, clear
set dot_solvent, 1
set dot_density, 3
get_area prot and polymer
get_area lig, load_b=1
set dot_solvent, 0
```
`dot_solvent 1` = solvent-accessible, 0 = molecular surface area. `load_b=1` stores per-atom area in `b`.
The area is computed in the context of the whole object (neighbouring atoms shade the selection); for the
area of a part on its own, `create part, sel` and measure `part`.
Relative per-residue SASA in Python: `from pymol import util; result = util.get_sasa_relative("prot and chain A")`
(dict `{(model, segi, chain, resi): fraction}`, also writes it into `b`).

## Electrostatics A - quick vacuum potential (no external programs)
```pml
create prot_only, prot and polymer
util.protein_vacuum_esp("prot_only", mode=2, border=10)
```
Creates `prot_only_e_chg` (charged copy, surface shown, coloured by potential), `prot_only_e_map` (map) and
`prot_only_e_pot` (ramp). Needs an object name, not a selection. Coulombic vacuum model: fine for a qualitative
figure, not for quantitative claims. Hide the original: `disable prot_only`.

## Electrostatics B - APBS (Poisson-Boltzmann, same pipeline as the APBS plugin GUI)
Run via the `python` tool (takes a few seconds for ~3000 atoms; grid 0.5 A, raise to 1.0 for big systems):
```python
import pymol.plugins
from pmg_tk.startup.apbs_gui.creating import pdb2pqr_cli
from pmg_tk.startup.apbs_gui.electrostatics import map_new_apbs
warnings = pdb2pqr_cli("prep", "prot and polymer", options="--ff=AMBER", quiet=1)
map_new_apbs("apbs_map", "prep", grid=0.5, buffer=10.0, quiet=1)
result = {"pdb2pqr_warnings": warnings, "objects": cmd.get_names(), "atoms": cmd.count_atoms("prep")}
```
`prep` is a new object with hydrogens, partial charges and radii (`--ff=AMBER|CHARMM|PARSE`, add
`--with-ph=7.0` for pH-dependent protonation). `apbs_map` holds the potential in kT/e. Then colour:
```pml
ramp_new apbs_ramp, apbs_map, [-5, 0, 5], [red, white, blue]
set surface_color, apbs_ramp, prep
set surface_ramp_above_mode, 1, prep
show surface, prep
hide everything, prot
```
- Range -5..5 kT/e is the usual figure scale; use `[-3, 0, 3]` for subtler, `[-10, 0, 10]` for highly charged.
- `surface_ramp_above_mode 1` samples the potential one solvent radius above the surface (standard look).
- The ramp is an object (`object:ramp`) - it shows in `scene`, and `alignto` tries to align it: delete or ignore.
- Ligands/metals are dropped by pdb2pqr; electrostatics of a complex needs a prepared PQR (`load x.pqr`) and
  then `map_new_apbs("m", "pqr_obj")` directly.
- Alternative without pdb2pqr: `create prep, prot and polymer` + `util.protein_assign_charges_and_radii("prep")`
  (Amber charges, no hydrogens added) then `map_new_apbs`.

## Pitfalls
- Transparent surfaces + ray tracing: `set transparency_mode, 2` (default) is best; mode 1 for multiple layers.
- Surfaces of large complexes are slow to build; set `surface_quality 0`, or surface only the chain of interest.
- Colour by potential needs `surface_color` = ramp name on the SAME object the map was made from (coordinates).
- After `align`/moving objects the map does not move with the molecule (maps are fixed in space): recompute.

## Verify
- `scene(detail="full")` -> `reps_atom_counts.surface` > 0 for the object; object list shows `apbs_map`
  (`map`) and `apbs_ramp` (`ramp`).
- `settings(names=["transparency", "surface_quality", "surface_color", "surface_carve_cutoff"], object="prep")`.
- `render()` -> `palette` should contain red/blue/white shares for a potential surface; `compare_renders()`
  after `set transparency` shows the change.
- `python`: `result = cmd.get_area("prot and polymer")` for a number to report.

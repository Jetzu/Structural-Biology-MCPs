---
name: ligand-binding-site
title: Ligand and binding-site workflows
app: pymol
description: Find ligands, define the pocket (residues within N A), list contacts, polar-contact dashes, waters and metals, interface residues between chains, preset.ligand_sites family, pocket surface, SASA, binding-site figures
tags: ligand, binding site, pocket, polar contacts, h-bonds, interface, organic, preset
---
Example object `prot` with a small-molecule ligand. Run `scene(detail="full")` first: `hetero_residues`
per object lists ligand residue names and counts, so you can pick the right one.

## 1. Define ligand and pocket
```pml
select lig, prot and organic and not resn HOH+GOL+SO4+EDO+PEG+PO4+ACT+DMS
select pocket, byres (prot and polymer within 4.5 of lig)
select pocket_sc, pocket and not name N+C+O
select waters_near, prot and solvent within 3.5 of lig
select metals_near, prot and metals within 3 of lig
```
- One specific ligand: `select lig, prot and resn 478 and chain A` (resn from `hetero_residues`);
  several copies: add `and chain X` or `byres (organic within 1 of (prot and resi 500))`.
- 4-5 A is the usual contact shell; 8 A for the "second shell". `selection_info("pocket")` returns the residue
  list with chains and ranges for the report.
```python
stored.res = []
cmd.iterate("pocket and name CA", "stored.res.append((chain, resn, int(resi)))")
result = sorted(set(stored.res))
```

## 2. Show it
```pml
hide everything
show cartoon, prot and polymer
set cartoon_transparency, 0.6, prot
show sticks, lig
show sticks, pocket_sc
set cartoon_side_chain_helper, 1
show spheres, waters_near
set sphere_scale, 0.2, waters_near
show spheres, metals_near
set sphere_scale, 0.4, metals_near
util.cbaw pocket_sc
util.cbag lig
set stick_radius, 0.2, pocket_sc
set stick_radius, 0.3, lig
set valence, 1
orient lig
zoom lig, 5
clip slab, 24
```
`util.cbag lig` = green carbons for the ligand, `util.cbaw` = white carbons for protein (distinguishable);
`cartoon_side_chain_helper 1` connects side chains to the cartoon. `zoom lig, 5` = ligand plus 5 A margin,
`clip slab, 24` cuts away everything deeper than 24 A so the pocket is not buried behind the protein.

## 3. Interactions
```pml
distance hbonds, lig, pocket, 3.5, mode=2
distance pistack, lig, pocket, mode=6
distance pication, lig, pocket, mode=7
distance water_hb, lig, waters_near, 3.5, mode=2
set dash_color, yellow, hbonds
set dash_color, cyan, pistack
set dash_radius, 0.06
hide labels, hbonds
```
- `mode=2` = polar contacts (N/O pairs within cutoff, no hydrogens needed; donor/acceptor geometry is
  checked loosely). For explicit hydrogens: `h_add lig` then `distance ..., mode=2` still works;
  `h_add` uses PyMOL valences, so check ligand bond orders (`set valence, 1` to see them).
- `mode=5` = pi-pi and pi-cation together, 6 pi-pi, 7 pi-cation (aromatic ring detection is automatic).
- Count polar contacts for the report via `python`:
  `result = len(cmd.find_pairs("lig and elem N+O", "pocket and elem N+O", cutoff=3.5))`.
- Per-residue nearest distances: `python` loop with `cmd.get_distance` or `cmd.find_pairs` and group by residue.
- Empty `hbonds` object (no dashes)? Check `selection_info("lig")` has N/O atoms and the cutoff is sane.

## 4. Presets (one call does steps 2-3 roughly)
```pml
preset.ligand_sites("prot")
preset.ligand_sites_trans("prot")
preset.ligand_cartoon("prot")
```
`preset.ligand_sites` (and `_hq`, `_trans`, `_trans_hq`, `_mesh`, `_dots` variants) finds ligands itself,
shows pocket lines/sticks, a carved surface patch (`_trans` = transparent, `_mesh`/`_dots` styles), polar
contacts as the object `<obj>_pol_conts` (named `polar_contacts` when the argument is a selection rather than an
object name), nb_spheres for waters, and zooms. `preset.ligand_cartoon` shows a
cartoon with side chains near the ligand. They apply to the whole object: undo with `hide everything` +
`delete prot_pol_conts`. Use them for a fast overview, then refine with explicit commands.

## 5. Pocket surface and buried area
```pml
set surface_carve_selection, lig, prot
set surface_carve_cutoff, 8, prot
show surface, prot and polymer
set transparency, 0.3, prot
set surface_color, grey80, prot
```
```python
cmd.flag("ignore", "lig", "clear")
cmd.set("dot_solvent", 1)
bound = cmd.get_area("lig")
cmd.create("lig_alone", "lig")
cmd.flag("ignore", "lig_alone", "clear")
free = cmd.get_area("lig_alone")
cmd.delete("lig_alone")
result = {"ligand_sasa_free": round(free, 1), "ligand_sasa_bound": round(bound, 1),
          "buried_fraction": round(1 - bound / free, 3) if free else None}
```
`get_area` of a selection is computed in the context of its whole object (the protein shades the ligand), so
the free value needs an isolated copy. `flag ignore ... clear` is required: hetero atoms are otherwise
excluded from area/surface calculations.

## 6. Protein-protein interface
```pml
select ifaceA, byres ((prot and chain A and polymer) within 4 of (prot and chain B and polymer))
select ifaceB, byres ((prot and chain B and polymer) within 4 of (prot and chain A and polymer))
show sticks, (ifaceA or ifaceB) and not name N+C+O
color marine, prot and chain A
color orange, prot and chain B
distance iface_hb, ifaceA, ifaceB, 3.5, mode=2
```
Interface residues per chain via `selection_info("ifaceA")`. Interface area: `get_area` of each chain alone
vs in complex (same pattern as above with `create`).

## Pitfalls
- `organic` matches buffers and crystallisation additives; always filter by `resn` or check `hetero_residues`.
- Covalent ligands are still `organic`, but `byres`/`bymolecule` on a bonded ligand can pull in the attached
  residue or the whole chain; check the atom count with `selection_info`.
- Alternate conformations: `alt A+""` to keep one; symmetry-related ligands need `symexp`.
- `preset.ligand_sites` changes global settings (`two_sided_lighting`) and the whole object's display.
- `zoom lig, 5` after `clip slab` may re-open the clipping; do `clip slab` last.

## Verify
- `selection_info("pocket")` -> residues/chains; `selection_info("lig")` -> atoms, elements, `center`.
- `scene` -> measurement objects (`hbonds`, `prot_pol_conts`); `scene(detail="full")` -> `reps_atom_counts`
  for sticks/surface.
- `layout(by="items", items=["lig", "pocket_sc", "prot and polymer and not pocket"])` -> the ligand should be
  near the centre with a decent `share_of_frame`, not occluded (`occlusion=True` reports `occluded_fraction`).
- `render()` -> `clipped_edges` empty, `palette` contains the ligand carbon colour.

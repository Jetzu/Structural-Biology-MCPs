---
name: symmetry-and-assemblies
title: Crystal symmetry and biological assemblies
app: pymol
description: Biological assemblies (set assembly + mmCIF, fetch type=pdb1, states to chains), crystal cell (get_symmetry/set_symmetry), symmetry mates with symexp within N A of a selection, mate naming, crystal-contact selection, unit cell display (show cell, cell_color), colouring/grouping mates, clean-up
tags: symmetry, symexp, assembly, biological assembly, pdb1, unit cell, cell, crystal contacts, set_symmetry, get_symmetry, mates, split_states, all_states
---
When to use: "show the biological tetramer", "is this interface a crystal contact", "which symmetry mates touch
the ligand", "draw the unit cell". Example object `prot` (crystal structure), ligand selection `lig`, mate prefix `sym`.
Biological assembly = the functional oligomer built from the asymmetric unit (ASU) with the depositors' operators.
Symmetry mates = every copy of the ASU that the space group places near it (crystal packing).

## Biological assembly
```pml
set assembly, 1
fetch 1stp, prot, type=cif, async=0
set assembly, ""
```
- `set assembly, <id>` is read at load time, so set it BEFORE `fetch`/`load`; it applies to mmCIF/bcif only
  (verified: `type=pdb` ignores it). Copies of one chain come in as STATES: 1stp (streptavidin, 1 chain in the ASU)
  loads as 4 states, chain A only. An unknown id prints `No such assembly: '2'` and loads the plain ASU (1 state,
  no error) - check `states` in `scene`. `set assembly, ""` restores the default (`0` is read as the id "0" and
  also falls back to the ASU).
- Legacy route: `fetch 1stp, prot, type=pdb1, async=0` (RCSB `.pdb1` file, MODEL records -> states; a local file
  loads with `load x.pdb1, prot`). Not offered for entries too large for PDB format - use the mmCIF route.
  Entries whose assembly is the ASU (1aar) load as 1 state either way.
- `set all_states, 1` shows every state at once. For one object with distinct chain ids (interfaces, `util.cbc`,
  saving one PDB) flatten the states:
```pml
split_states prot, prefix=asu_
alter asu_0002, chain="B"
alter asu_0003, chain="C"
alter asu_0004, chain="D"
create tetramer, asu_*
delete asu_*
```
Verified: `tetramer` has chains A-D and 4x the PER-STATE atom count (1stp: 4 x 1001 = 4004). `count_atoms prot` on
the multi-state assembly object says 1039: its 38 zero-occupancy mmCIF atoms get no coordinates in any assembly state,
and `split_states`/`create` carry only atoms with coordinates - count with `cmd.count_atoms("prot", state=1)`.
Default `split_states` prefix is `<object>_`.

## Crystal symmetry and mates
```pml
fetch 1ubq, prot, async=0
get_symmetry prot
symexp sym, prot, prot, 4
symexp near, prot, lig, 6
```
- `get_symmetry` prints a, b, c, alpha, beta, gamma and the space group (CRYST1 / mmCIF cell). `python` form:
  `result = cmd.get_symmetry("prot")` -> 7-item list, or `None` for objects without a cell (models, NMR).
- `symexp prefix, object, selection, cutoff` builds every symmetry copy of the WHOLE object that has at least one
  atom within `cutoff` A of `selection` (1ubq, 4 A -> 14 mates of 660 atoms each; `resi 48`, 6 A -> 3 mates).
  Mates are ordinary objects that keep the cell. Names = prefix + 2-digit operator + three 2-character
  translations: `sym01000000` = operator 1, (0,0,0); `sym0300-1-1` = operator 3, (0,-1,-1); the identity
  operator `00` only appears with a non-zero translation (`sym000000-1`). Address them with the pattern `sym*`
  (the `-` in a name is fine in selections). `segi=1` writes a 4-character operator/translation code into segi
  (`D000`, `B0A0`) for later `iterate`.
- No cell -> `ExecutiveSymExp-Error: No symmetry loaded!` and nothing is created. Supply one with
  `set_symmetry prot, 50.84, 42.77, 28.95, 90, 90, 90, P 21 21 21` (space group with spaces is fine on the
  command line), then `symexp` again. `create` copies and `save x.pdb` keep the cell (CRYST1).
- Crystal contacts (ASU residues touching any mate) and trimming the mates to the contact zone:
```pml
select xtal, (byres (prot within 4 of sym*)) and polymer
remove sym* and not (byres (sym* within 5 of prot))
```
Trimming 1ubq's 14 mates at 5 A: 9240 -> 918 atoms, all 14 objects survive. A mate that `remove` empties completely
is deleted automatically (PyMOL 3.1 keeps no 0-atom objects: `remove sym0300-1-1` drops it from the object list, a
2 A trim leaves 2 of 14 mates) - count the survivors with `python`: `result = cmd.get_object_list("sym*")`.

## Unit cell
```pml
show cell, prot
set cell_color, grey50
zoom prot, 20
hide cell, prot
```
- `cell` is a representation (`show`/`hide cell`) drawn from the object's own cell; `cell_color` colours the edges.
  `set cell_centered, 1` shifts the box by half a cell so it is centred on the origin instead of spanning 0..1
  (verified by render); leave it at 0 for the conventional cell.
- `zoom`/`orient` use atom extents only: pad with a buffer or the cell corners leave the frame - check
  `clipped_edges` in `render()`.

## Colour, group, tidy
```pml
hide everything, sym*
show cartoon, sym*
color grey70, sym*
set cartoon_transparency, 0.6, sym*
util.color_objs("sym*")
group mates, sym*
```
- `color`/`set ..., sym*` apply per object (verified: `cartoon_transparency` 0.6 on each mate, global unchanged).
  `util.color_objs("sym*")` gives each mate its own colour - Python-call syntax only (`util.color_objs sym*` is a
  SyntaxError).
- `group mates, sym*` tidies the object panel; `disable mates` hides them all (members still report
  `enabled: true`, see cgo-and-pseudoatoms). `delete mates` deletes the group AND every member; `delete sym*`
  does the same without a group.
- After an assembly job: `delete asu_*`, `set assembly, ""`, `hide cell`.

## Pitfalls
- `byres (prot within 4 of sym*) and name CA` is parsed as `byres ((...) and name CA)` - 90 atoms instead of
  47 CA for 1ubq. Bracket the expander: `(byres (...)) and name CA` (selection-cheat-sheet).
- Every mate is a full copy including waters: on big structures use a small `selection`/cutoff, `remove solvent`
  first, trim as above, and see performance-and-large-systems.
- `set assembly` and `type=pdb1` give one chain id repeated across states; interface tools
  (protein-protein-interface) and `util.cbc` need the flatten recipe above.
- Maps apply crystal symmetry on their own (`map_auto_expand_sym`, maps-and-density) - no `symexp` for meshes.
  Symmetry-related ligand copies in a binding site: `symexp near, prot, lig, 6` (ligand-binding-site).

## Verify
- `scene` -> per object `states` (4 for the 1stp assembly), `chains`, `atoms`; `reps_enabled_mask` lists `cell`
  after `show cell`; mates appear as objects named `sym...`.
- `object_info("sym01000000")` -> `atoms` equals the parent before trimming; `setting_overrides` shows
  `cartoon_transparency`.
- `python`: `result = cmd.get_symmetry("prot")` (cell + space group); `result = len(cmd.get_object_list("sym*"))`.
- `selection_info("xtal")` / `residue_table("xtal")` -> crystal-contact residues per chain.
- `layout(by="object")` -> each mate's share of the frame and its 2D contact with `prot`; `render()` before and
  after `show cell` + `compare_renders()` -> `changed_fraction` > 0 (thin edges: ~3% at 300 px for 1ubq).

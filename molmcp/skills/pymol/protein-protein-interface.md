---
name: protein-protein-interface
title: Protein-protein interfaces
app: pymol
description: Interface residues between two chains or objects (within/byres), buried surface area from get_area with dot_solvent on isolated copies, per-residue buried area, polar contacts and salt bridges across the interface (distance mode=2, find_pairs), interface colouring, open-book figure, exporting residue lists
tags: interface, protein-protein, buried surface area, bsa, sasa, get_area, polar contacts, salt bridge, open book, within, byres, export
---
When to use: "which residues form the A/B interface", "how large is the buried surface", "show the hydrogen
bonds across the interface", "colour the epitope/paratope", "export the interface residues". Example object
`cplx` with chains A and B (`scene` -> chains). Related: `ligand-binding-site` (pockets, ligand SASA),
`surfaces-and-electrostatics` (surface/SASA basics), `labels-and-measurements` (dashes), `selection-cheat-sheet`.

## 1. Interface residues
```pml
select ifaceA, byres ((cplx and chain A and polymer) within 4 of (cplx and chain B and polymer))
select ifaceB, byres ((cplx and chain B and polymer) within 4 of (cplx and chain A and polymer))
select iface_sc, (ifaceA or ifaceB) and sidechain
```
- 4 A between heavy atoms is the usual definition; 5 A is generous, 3.5 A keeps only polar-contact residues.
- Two objects (docked pose, superposed partner): `select ifaceA, byres ((objA and polymer) within 4 of (objB and polymer))`.
- One chain against everything else (antibody, trimer): `... within 4 of (cplx and polymer and not chain A)`.
- List them with `selection_info("ifaceA")` or `residue_table("ifaceA")`; `within` is static - re-run after moving atoms.

## 2. Buried surface area (BSA)
`get_area` needs ONE object and shades the selection by everything else in that object, so measure isolated copies:
```python
cmd.set("dot_solvent", 1); cmd.set("dot_density", 3)
cmd.create("chA", "cplx and chain A and polymer")
cmd.create("chB", "cplx and chain B and polymer")
cmd.create("pairAB", "cplx and chain A+B and polymer")
aA, aB, aAB = cmd.get_area("chA"), cmd.get_area("chB"), cmd.get_area("pairAB")
result = {"sasa_A": round(aA, 1), "sasa_B": round(aB, 1), "sasa_AB": round(aAB, 1),
          "bsa_total": round(aA + aB - aAB, 1), "bsa_per_side": round((aA + aB - aAB) / 2, 1),
          "buried_on_A": round(aA - cmd.get_area("pairAB and chain A"), 1),
          "buried_on_B": round(aB - cmd.get_area("pairAB and chain B"), 1)}
```
- `dot_solvent 1` = solvent-accessible area (1.4 A probe, the BSA convention); 0 gives the molecular surface.
  `dot_density` 2 (default) to 4; 3 is a good report value (a few seconds: ~2-6 s for 12-24k atoms, under 2 s
  at density 2, 10-20 s at 4).
- Two objects: `create pairAB, objA or objB` first - a selection across objects raises "Selection must be
  within a single object". For a chain pair inside a bigger complex always measure `pairAB`, never
  `cplx and chain A+B`: the other chains shade the pair.
- `polymer` drops waters and ligands (hetero atoms carry the `ignore` flag anyway; `flag ignore, lig, clear` to
  include a ligand in the interface, see `ligand-binding-site`). Measure without hydrogens (`h_add` raises areas
  by ~1%). Rough scale: biological interfaces bury 1200-2000 A^2 in total (600-1000 per side), crystal contacts
  mostly below ~800 A^2. `measure(kind="sasa", selection1="chA")` is the tool form of one `get_area` call.

## 3. Per-residue buried area and colouring
`load_b=1` writes per-atom areas into B-factors - do it on the copies, then map the difference onto `cplx`:
```python
cmd.get_area("chA", load_b=1); cmd.get_area("pairAB and chain A", load_b=1)
free, bound = {}, {}
cmd.iterate("chA", "free[(resi, resn)] = free.get((resi, resn), 0) + b", space={"free": free})
cmd.iterate("pairAB and chain A", "bound[(resi, resn)] = bound.get((resi, resn), 0) + b", space={"bound": bound})
buried = {k: round(free[k] - bound.get(k, 0), 1) for k in free}
cmd.alter("cplx and chain A and polymer", "b = buried.get((resi, resn), 0.0)", space={"buried": buried})
result = sorted(((k[1] + k[0], v) for k, v in buried.items() if v > 5), key=lambda kv: -kv[1])
```
```pml
spectrum b, white_red, cplx and chain A and polymer, minimum=0, maximum=80
show surface, cplx and chain A and polymer
```
This overwrites the B-factors of chain A in `cplx` (`create cplx_orig, cplx` first if they matter). Repeat
with B for the other side. Hot-spot candidates: residues burying more than ~40 A^2.

## 4. Contacts across the interface
```pml
distance iface_hb, ifaceA, ifaceB, 3.5, mode=2
hide labels, iface_hb
set dash_color, yellow, iface_hb
distance salt_AB, ifaceA and resn ARG+LYS and name NZ+NE+NH1+NH2, ifaceB and resn ASP+GLU and name OD1+OD2+OE1+OE2, 4.0, mode=0
distance salt_BA, ifaceB and resn ARG+LYS and name NZ+NE+NH1+NH2, ifaceA and resn ASP+GLU and name OD1+OD2+OE1+OE2, 4.0, mode=0
select hydrophobicA, byres ((ifaceA and sidechain and elem C) within 4 of (ifaceB and sidechain and elem C))
```
- `mode=2` = polar contacts between N/O atoms (hydrogens not needed). `distance` prints and returns the MEAN
  distance, not a count; count via `python`:
  `result = len(cmd.find_pairs("ifaceA and elem N+O", "ifaceB and elem N+O", cutoff=3.5))` (all N/O pairs
  within 3.5 A, a superset of the drawn dashes; add `mode=1, angle=55` for a donor/acceptor geometry check
  close to what `mode=2` draws), or with the
  `contacts` tool: `contacts(selection1="cplx and chain A", selection2="cplx and chain B", polar_only=True)`
  lists residue pairs with their closest distance (`cutoff=4.0` without `polar_only` for all contacts).
- Pi stacking / cation-pi across the interface: `distance pipi, ifaceA, ifaceB, mode=6` and `mode=7`.
- Water bridges: `select iface_wat, (solvent within 3.5 of ifaceA) and (solvent within 3.5 of ifaceB)`, then
  `distance wat_hb, iface_wat, ifaceA or ifaceB, 3.5, mode=2`. An empty `salt_AB` is normal; `delete` it.

## 5. Figure
```pml
hide everything
show cartoon, cplx and polymer
color grey80, cplx and chain A
color grey60, cplx and chain B
color marine, ifaceA
color orange, ifaceB
show sticks, (ifaceA or ifaceB) and sidechain
set cartoon_side_chain_helper, 1
show surface, cplx and chain B and polymer
set transparency, 0.35, cplx
set surface_color, grey90, cplx
set surface_color, orange, ifaceB
set dash_radius, 0.08
orient ifaceA or ifaceB
```
`set surface_color, colour, selection` paints only that patch (atom-level beats object-level). `orient` on the
interface puts the interface plane roughly in the screen plane (partners front/back); `turn y, 90` = side view.

Open-book view (both interface patches face the viewer; works on copies, `cplx` stays untouched):
```python
import numpy as np
cmd.orient("ifaceA or ifaceB")
cmd.create("chA", "cplx and chain A and polymer"); cmd.create("chB", "cplx and chain B and polymer")
cmd.select("ifaceA2", "byres (chA within 4 of chB)"); cmd.select("ifaceB2", "byres (chB within 4 of chA)")
R = np.array(cmd.get_view()[:9]).reshape(3, 3).T                    # model -> camera; larger z = nearer the camera
zA, zB = (R.dot(np.array(cmd.centerofmass(o)))[2] for o in ("chA", "chB"))
front = "chA" if zA > zB else "chB"
cmd.rotate("y", 180, front, origin=cmd.centerofmass(front))          # flip in place about camera y (without origin it pivots about the view centre)
cmd.translate([-20, 0, 0], "chA"); cmd.translate([20, 0, 0], "chB")  # camera x; ~half the width of a partner
cmd.disable("cplx"); cmd.zoom("chA or chB", 2)
result = {"flipped": front}
```
Then style `chA`/`chB` as above using `ifaceA2`/`ifaceB2`. Scale the translation to the partner size
(`measure(kind="extent", selection1="chA")`); delete interface dashes, they are meaningless in an open book.

## 6. Export residue lists
```pml
iterate ifaceA and name CA, print(chain, resi, resn)
```
The lines arrive in the `run` result. Files via `python`:
```python
import csv
rows = []
cmd.iterate("(ifaceA or ifaceB) and name CA", "rows.append((chain, resi, resn, round(b, 1)))", space={"rows": rows})
with open(cmd.exp_path("~/interface_residues.csv"), "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["chain", "resi", "resn", "b_or_buried_area"]); w.writerows(rows)
result = {"rows": len(rows)}
```
- `save_file(path="~/interface.pdb", selection="ifaceA or ifaceB")` for the coordinates, `.fasta` for the patch
  sequence (gap-less, not an alignment), `save_file(path="~/interface.pse")` to keep selections and dashes.

## Pitfalls
- `within` counts backbone atoms too; for side-chain-mediated interfaces use `sidechain` on both sides.
- Do not name copies `b`, `q`, `x`, `y`, `z` or selection keywords (`all`, `polymer`, ...): PyMOL silently
  appends `_` (`b` -> `b_`) and later selections miss them; `chA`/`chB` are safe.
- Symmetry mates are not in the file: for a biological interface `set assembly, 1` before loading/fetching an
  mmCIF; for crystal contacts `symexp`.
- `dot_solvent 1` lingers and changes the `dots` representation: `set dot_solvent, 0` when done.
- `distance mode=2` works across two objects, `get_area` does not - merge with `create` first.

## Verify
- `selection_info("ifaceA")` / `("ifaceB")` -> residues per chain; `scene` -> `iface_hb` (measurement), selections.
- `residue_table("ifaceA")` -> `reps_shown` has sticks, `color` marine, `b_mean` = buried area after step 3.
- `layout(by="items", items=["ifaceA", "ifaceB", "cplx and not (ifaceA or ifaceB)"], occlusion=True)` -> both
  interface items visible with a low `occluded_fraction` (open book: `ifaceA2`, `ifaceB2`).
- `render()` -> `palette` contains marine/orange, no `clipped_edges`; `compare_renders()` after the open-book
  move shows a large changed fraction.

---
name: symmetry-and-assemblies
title: Symmetry and biological assemblies
app: chimerax
description: Build biological assemblies from mmCIF with sym (full copies vs. graphical clones), apply user-specified or map-derived symmetry (Cn/Dn/T/O/I/helical/shift), build crystallographic unit cells and find crystal contacts, colour symmetry mates, and remove everything again
tags: symmetry, sym, assembly, biological unit, biomt, oligomer, capsid, unit cell, crystal contacts, clones, copies
---
Use for "show the biological assembly", "make the tetramer", "build the capsid", "show the crystal
packing / unit cell", "which residues make crystal contacts", "apply C3 symmetry", "colour each
subunit", "remove the symmetry copies". Syntax verified in ChimeraX 1.11.1 (headless run).

## 1. Copies or clones – decide first
- **Copies** (`copies true`, default when ≤12 copies): full atomic models `#2.1 … #2.N` grouped
  under `#2 "<name> assembly 1"`, `#1` hidden. Needed for measurements, hbonds/contacts, matchmaker,
  saving, and different colours/styles per copy.
- **Clones** (`copies false`, default when >12 copies, e.g. capsids): one model drawn N times
  (`positions`). Memory-cheap, but no atoms of their own: `color #2.1 blue` colours 0 atoms, all
  instances share the source's appearance, and `scene`/`model_info` do not list them (see §7).
- Archive coordinates instead of `sym`: `open 1abc from rcsb_bio maxAssemblies 1`
  (sessions-and-export) – gives real chains, no deposited asymmetric unit.

## 2. Assemblies from mmCIF
```
sym #1                                          # log table: id | description | "4 copies of chain A"
sym #1 assembly 1                               # build it (≤12 → copies #2.1-#2.N; >12 → clones)
sym #1 assembly 1 copies true                   # force full copies (capsid for analysis: 60 models)
sym #1 assembly 1 copies false                  # force clones: #2 is ONE model with N positions
sym #1 assembly 1 copies false newModel false   # clones on #1 itself, nothing new in the model list
sym #1 assembly 1 surfaceOnly true resolution 6 # per-chain Gaussian surfaces #2.1, #2.2 … each with N positions
view #2; cofr #2                                # recentre on the assembly
```
`newModel true` (default for mmCIF) deletes chains outside the assembly from the new model;
`newModel false` only hides them on `#1`. `surfaceOnly` still shows the copy's own atoms/cartoon at
the identity position – `hide #2 cartoons; hide #2 atoms` for surfaces alone. Assemblies are read
from mmCIF only; for PDB-format files use `sym #1 biomt` (REMARK 350) – "has no biological unit
info" means the file carries none.

## 3. User-specified symmetry
```
sym #1 C3 axis z center #1 copies true          # cyclic; center = bounding-box centre of #1
sym #1 d7 axis z center 0,0,0 coordinateSystem #1       # dihedral; axis/center read in #1's frame
sym #1 i,222 center #1                          # icosahedral (orientations 222, 2n5, n25, 2n3, …r)
sym #1 t center #1                              # tetrahedral (t,z3 for EMAN): 12 → copies in #2
sym #1 o center #1                              # octahedral: 24 → clones on #1
sym #1 h,43.5,21,6,-2 axis z center #1          # helical: rise Å, twist °, n copies, offset
sym #1 shift,3,26.7 axis x                      # translational: n copies, distance (or x,y,z vector)
sym #1 c2*h,42,21,9,-4 axis z center #1         # product of groups
sym #1 C4 axis #1/A:10,60@CA                    # axis through two atoms (one spec matching 2 atoms)
define axis #1/A:23-34 name h1; sym #1 C3 axis #1.1 center #1.1   # axis model as axis/centre
sym #1 symmetry #2 copies true                  # symmetry stored on map #2 (measure symmetry / volume #2 symmetry C3)
sym #1 C6 axis z center #1 contact 4 range 60   # keep copies touching (<4 Å) / centred within 60 Å
```
Defaults `axis z`, `center 0,0,0`, scene frame; ≤12 copies → new model `#2` with copies, more →
clones on `#1`. Find axis/centre with `measure center #1`, `measure inertia #1` or `define axis`
(labels-keys-and-measurements); detect from density with `measure symmetry #2` (maps-and-cryoem).
`addMmcifAssembly true` stores the operators so `save x.cif #1` lists it as a new assembly.

## 4. Unit cell and crystal packing
```
unitcell info #1                                # space group, cell lengths/angles, operator counts
unitcell #1 outline true                        # cell copies: #2 "unit cell" with #2.1-#2.N; box = #3
unitcell #1 cells 3,1,1 offset -1,0,0           # 3 cells along a, original in the middle
unitcell #1 origin 0.5,0,0                      # re-pack copies into a cell shifted ½ along a (box NOT moved)
unitcell outline #1 close; unitcell outline #1 origin 0.5,0,0   # redraw the box at the new origin
unitcell delete #1; unitcell outline #1 close   # remove copies; remove the box (delete leaves it)
```
Needs cell + space group in the file (CRYST1/REMARK 290 or `_cell`/`_symmetry`); predicted and EM
models have none (`unitcell info` prints only the header, `unitcell` makes nothing, `crystalcontacts`
errors "No unit cell parameters"). `ncs false` skips MTRIX copies, `pack false` keeps raw operator
positions. Every `outline true` / `unitcell outline` call adds another box model; `unitcell outline
#1 close` removes one per call.

## 5. Crystal contacts
```
delete solvent                                  # waters count as contacts; irreversible → reopen the file later
crystalcontacts #1 distance 3.5                 # log: atoms per contacting symmetry mate (SMTRY op + cell)
crystalcontacts #1 distance 3.5 residueInfo true buriedAreas true   # residue pairs + per-residue buried SASA
crystalcontacts #1 distance 3.5 schematic true copies false         # balls + red cylinders only (own MarkerSet model)
crystalcontacts #1 distance 3.5 rainbow false   # mates keep the original colouring
contacts #1 restrict #2.1 distanceOnly 3.5 reveal true   # atom pairs to one mate (hbonds-contacts-clashes)
crystalcontacts delete #1                       # removes #2 "<name> crystal contacts" (#2.N = "<name> i j k sym n") + schematic
```
Rerunning replaces the previous mates. `intraBiounit false` drops contacts inside the BIOMT unit.
`crystalcontacts delete` leaves the `contacts` pseudobonds – `contacts delete` removes them.

## 6. Colour symmetry mates (copies only)
```
rainbow #2 structures                           # one colour per copy; `palette paired-12` etc.
color #2.1 cornflowerblue; color #2.2 salmon; color #2.3 gold
color #2 bychain                                # chain identity (same chain → same colour in every copy)
color #2.2 & protein gold target c; style #2.2 ball          # highlight one copy
color #1 red; color #1/A:10-20 blue             # clones: colour the source – every instance follows
```
Keep big assemblies light: `hide #2 atoms; cartoon #2` or `surface #2 resolution 8`
(surfaces-and-electrostatics); lighting/silhouettes in publication-rendering.

## 7. Verify
- `scene` → group `#2` with children `#2.1…` (`atoms` each), `#1` `display: false`; `log` shows
  "Made N copies" / "Made N graphical clones". Clones are invisible to `scene` – count them:
```python
result = {"#" + m.id_string: len(m.positions) for m in session.models.list()
          if hasattr(m, "positions") and len(m.positions) > 1}
```
- `render` → coverage and bounding box grow; `layout(by="chain")` lists `#2.1/A`, `#2.2/A` … with
  their on-screen share (`by="model"` keeps only parentless structures, so it skips a group's `#2.N`
  children; `by="items", items=["#2.1", "#2.2"]` also works); `compare_renders` before/after.
- `measure`, `contacts`, `residue_table("#2.2")`, `align` work only on copies (`copies true`).
- `unitcell info`: "Space group symmetries" = copies per cell; `crystalcontacts` table rows = mates.

## 8. Clean up
```
sym clear #1                                    # drop clones (extra positions) from #1 (or #2)
close #2; show #1 models                        # remove copies/assembly model, unhide the original
unitcell delete #1; unitcell outline #1 close; crystalcontacts delete #1
combine #2.1-4 close true name tetramer modelId 3   # one model, chains renamed A,B,C,D → save tetramer.cif #3
save assembly.cif #2                            # one file, copies as model numbers 1..N (NMR-style; chain IDs unchanged)
```

## Pitfalls
- `sym` with copies/newModel hides `#1`: later views of `#1` look empty until `show #1 models`.
- `sym clear` never removes copies, `close` never removes clones – use both when unsure.
- Assemblies with different operator sets per chain: `newModel false` errors ("requires new model");
  the default `newModel true` with `copies false` makes one atomic model per operator set (`#2.1`
  "<name> 1" with N positions, `#2.2` …) – `sym clear #2` drops the clones, `close #2` the models.
- `contact`/`range` apply to user-specified symmetry only; with `assembly` they are ignored.
- `measure symmetry` finds nothing on a monomer map ("No symmetry found") – `sym #1 symmetry #2`
  then errors; assign with `volume #2 symmetry C3 center #1` instead.
- `unitcell delete` leaves the outline model (its `outline true|false` keyword is accepted but
  ignored in 1.11.1); `unitcell outline #1 close` (or `close #3`) removes it.
- Ligands/ions count as crystal contacts; delete what should be excluded before `crystalcontacts`.

---
name: hbonds-contacts-clashes
title: Hydrogen bonds, contacts, clashes and interfaces
app: chimerax
description: Find and display H-bonds (hbonds), steric clashes and contacts (clashes/contacts), chain–chain interfaces (interfaces); restrict to ligand–protein pairs, reveal atoms, label distances, log/save lists, and remove the pseudobonds
tags: hbonds, clashes, contacts, interfaces, interactions, pseudobonds, binding site, salt bridges
---
Use for "show hydrogen bonds between ligand and protein", "any clashes?", "which residues contact
chain B", "interface residues". Syntax verified against the ChimeraX 1.11 docs.

## 1. Hydrogen bonds
```
hbonds #1                                                # all H-bonds involving #1 → pseudobond model "hydrogen bonds"
hbonds ligand restrict protein reveal true showDist true # ligand↔protein only; show atoms + distance labels
hbonds /A restrict /B reveal true                        # between two chains
hbonds :NAD restrict cross log true                      # NAD to everything else, list in the log
hbonds #1 saltOnly true name "salt bridges" color magenta radius 0.12
hbonds sidechain restrict both reveal true               # side chain – side chain only
hbonds #1 relax false                                    # strict criteria (default relaxes by 0.4 Å / 20°)
hbonds #1 interModel false intraMol false                # only between molecules within a model
hbonds #1 saveFile ~/hbonds.txt namingStyle command      # write a list; `log true` prints it
hbonds #1 select true                                    # select the H-bonding atoms
~hbonds; hbonds delete name "salt bridges"               # remove pseudobonds
```
Options: `restrict cross|both|any|spec`, `intraRes`, `intraMol`, `interModel`, `interSubmodel`,
`distSlop`, `angleSlop`, `twoColors`, `dashes N`, `color`, `radius`, `name`, `retainCurrent`,
`updateGroup`, `coordsets true` (every trajectory frame). Add hydrogens first for directional
accuracy: `addh #1 hbond true`.

## 2. Clashes and contacts (same options, different cutoffs)
```
clashes #1 reveal true showDist true                 # overlap ≥ 0.6 Å (hbondAllowance 0.4), medium orchid
contacts ligand restrict protein reveal true         # overlap ≥ −0.4 Å: all direct contacts, forest green
clashes sel restrict cross                           # between the selection and the rest
clashes #1 overlapCutoff 0.8 hbondAllowance 0.4 log true saveFile ~/clashes.txt
contacts #1 distanceOnly 4 restrict ligand           # centre-to-centre ≤ 4 Å instead of overlap
clashes #1 ignoreHiddenModels true summary true
clashes #1 setAttrs true                             # atom attribute `overlap` (largest per atom)
clashes #2 continuous true                           # re-check while #2 is moved; ~clashes stops it
~clashes; ~contacts; contacts delete name mycontacts
```
`resSeparation N` ignores pairs close in sequence; `bondSeparation 4` (default) ignores 1-4 pairs.

## 3. Interfaces (buried SASA per chain pair)
```
interfaces #1 & protein                               # table in the log + chain network diagram (GUI)
interfaces #1 areaCutoff 300 interfaceResidueAreaCutoff 15
interfaces select /A contacting /B bothSides true     # select interface residues of both chains
measure buriedarea (/A & protein) withAtoms2 (/B & protein) listResidues true
```

## 4. Make the picture readable
```
hide #1 atoms; cartoon #1; show ligand | (ligand :< 5) atoms; style ligand ball
color byhetero; cartoon #1 suppressBackboneDisplay false      # backbone atoms visible with the cartoon
hbonds ligand restrict protein reveal true showDist true
label height 0.7; color hbonds goldenrod; size hbonds pseudobondRadius 0.08; style hbonds dashes 4
view ligand :< 6; cofr ligand
```
H-bond distance labels are 3D labels: `label hbonds pseudobonds` adds them later;
`label delete pseudobonds` removes them; `label … size 96` for crisp text in big images.

## 5. Read the results
- `run` `output`: "N hydrogen bonds found", "N contacts", and with `log true` donor/acceptor/distance lines.
- `scene` → the structure gains `pseudobond_groups` (`hydrogen bonds`, `clashes`, `contacts`) with counts.
- `selection_info("hbondatoms")` → atoms/residues involved (per chain, residue ranges).
```python
from chimerax.atomic import AtomicStructure
s = [m for m in session.models.list(type=AtomicStructure) if m.id_string == "1"][0]
pbg = s.pbg_map.get("hydrogen bonds")
pairs = []
if pbg:
    for pb in pbg.pseudobonds:
        a, b = pb.atoms
        fmt = lambda x: "/%s:%s%d@%s" % (x.residue.chain_id, x.residue.name, x.residue.number, x.name)
        pairs.append((fmt(a), fmt(b), round(float(pb.length), 2)))
result = sorted(pairs, key=lambda p: p[2])
```

## 6. Verify
- `render` → `palette` contains the pseudobond colour (deep sky blue H-bonds, medium orchid
  clashes, forest green contacts, gold distances); `compare_renders` before/after shows the dashes.
- `layout by="items", items=["ligand", "protein & ligand :< 5"]` → both visible, low `occluded_fraction`.

## Pitfalls
- Pseudobonds are drawn only when both end atoms are displayed → `reveal true` or `show`.
- Without hydrogens the donors are inferred from atom types; `addh` first for precise geometry.
- "Between A and B" = `hbonds A restrict B`; `restrict cross` = A to anything not in A.
- Waters count as partners unless excluded: `restrict protein & ~solvent` or `delete solvent`.
- `interfaces` and `measure buriedarea` include ligands/ions/solvent unless you add `& protein`.
- Re-running `hbonds` replaces the previous "hydrogen bonds" model; use `name` to keep several sets.

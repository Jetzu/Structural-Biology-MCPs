---
name: interfaces-and-buried-area
title: Protein interfaces and buried surface area
app: chimerax
description: Chain–chain interfaces: interfaces (buried SASA per chain pair, interface residue selection), measure buriedarea (numbers, per-residue list, select/colour), a per-residue buried-area attribute for gradient colouring, H-bonds/contacts across the interface, face-on and open-book figures, exporting residue lists (info residues saveFile, .defattr, residue_table)
tags: interface, protein-protein, buried area, bsa, sasa, interfaces, measure buriedarea, epitope, paratope, open book, export, residue list
---
Use for "which chains interact", "which residues form the A/B interface", "how large is the buried
surface", "colour the epitope/paratope", "open-book view", "export the interface residues". Example:
model `#1` with chains A and B (`scene` → chains; numbers below are 1aar diubiquitin). Related skills:
`hbonds-contacts-clashes` (all hbonds/contacts options), `surfaces-and-electrostatics` (surfaces, SASA),
`selection-and-zones` (distance zones), `representations-and-colouring` (`color byattribute`),
`labels-keys-and-measurements` (labels, keys), `sessions-and-export` (assemblies). Verified on ChimeraX 1.11.

## 1. Which chains touch? (`interfaces`)
```
interfaces #1 & protein                          # 1aar: "1 buried areas: B A 749" (Å² per side, largest first); 1igy antibody: "3 buried areas: D C 1811, B A 1774, B D 1430"
interfaces #1 & protein areaCutoff 150           # also list small interfaces (default 300 Å²)
interfaces #1 & protein interfaceResidueAreaCutoff 10 probeRadius 1.4     # residue threshold (default 15 Å²), probe (1.4 Å)
ui tool hide "Chain Contacts"                    # close the network diagram the GUI opens (GUI only: headless → "Need a GUI to show or hide tools")
```
Chain labels in the message drop the common `#1/` prefix. Without `& protein` every chain counts:
`interfaces #1` on an antibody adds glycan "chains" (`D F 642, B E 625`). Headless/`--nogui` logs
"unable to show graph without GUI" but still prints the table line. Explode, residue plots and
"Lay Out to Match Structure" are context-menu-only in the diagram; use section 6 instead.

## 2. Interface residues
```
interfaces select /A contacting /B bothSides true                 # residues burying ≥ 15 Å² on both sides → selection
interfaces select /B contacting ~/B & protein                     # one chain against everything else (paratope of H chain)
interfaces select #1/B contacting #1/A | #1/C | #1/D bothSides true interfaceResidueAreaCutoff 10
measure buriedarea (/A & protein) withAtoms2 (/B & protein) listResidues true cutoffArea 10 select true
name frozen ifaceAB sel; select clear                             # keep the residue set as target `ifaceAB`
```
`interfaces select` only looks at chain pairs that bury ≥ `areaCutoff` (300 Å²): a small interface
gives "0 contacting residues" — lower `areaCutoff`, do not conclude "no interface". `measure buriedarea`
lists every residue above `cutoffArea` (default 1 Å²; 10 is a sensible figure threshold, ≥ 40 Å² =
hot-spot candidate). Distance-based alternative (`select /A & (/B :< 4)`): see `selection-and-zones`.

## 3. Buried surface area numbers
```
measure buriedarea (/A & protein) withAtoms2 (/B & protein)
```
Output: `Buried area between /A & protein and /B & protein = 749.45` then
`area /A & protein = 4723.1, area /B & protein = 4736.9, area both = 7961`. The value is
½(sasa1 + sasa2 − sasa12) = area per side; "total buried" in papers is twice that. Scale: biological
interfaces ≈ 600–1000 Å² per side, crystal contacts mostly < 400. Rules: the two sets must be disjoint
(`measure buriedarea #1 withAtoms2 /B` → "Two sets of atoms must be disjoint"); only specified atoms
exist for the probe, so `& protein` drops waters/ligands/glycans — to count a ligand, add it to one side
(`(/A | :HEM) & ~solvent`). Crystal packing: `crystalcontacts #1 distance 7 buriedAreas true` (needs cell
data in the file; the per-residue buried SASA only uses residues within `distance`, so give ≥ 6.6 Å — the
3 Å contact default understates it; contacting copies land under a new `#N … crystal contacts` model,
`crystalcontacts delete #1` removes them). Biological assembly first: `open 1abc from rcsb_bio` (`sessions-and-export`).

## 4. Per-residue buried area as an attribute (gradient colouring, attribute tests)
Commands give lists or one flat colour (`measure buriedarea … color orange`). For a gradient, store the
per-residue values as a residue attribute with the `python` tool:
```python
from chimerax.atomic import Residue, buried_area
from chimerax.core.commands import atomspec
ev = lambda spec: atomspec.AtomSpecArg.parse(spec, session)[0].evaluate(session).atoms
a1, a2 = ev("#1/A & protein"), ev("#1/B & protein")
ba, s1, s2, s12 = buried_area(a1, a2, 1.4); n1 = len(s1)          # per-atom SAS: alone (s1, s2) and together (s12)
Residue.register_attr(session, "buried", "molmcp", attr_type=float)
for r in ev("#1").unique_residues: r.buried = 0.0
for atoms, per_atom in ((a1, s1 - s12[:n1]), (a2, s2 - s12[n1:])):
    res, vals = atoms.residue_sums(per_atom)
    for r, v in zip(res, vals): r.buried = float(v)
top = [(round(float(r.buried), 1), "/%s:%s%d" % (r.chain_id, r.name, r.number)) for r in ev("#1").unique_residues if r.buried > 5]
result = {"buried_per_side": round(float(ba), 1), "top": sorted(top, reverse=True)[:15]}
```
```
color byattribute r:buried #1 & protein palette white:orangered range 0,60     # atoms, cartoons and surfaces
select ::buried>20                                                           # own line: "::buried>20;" reads the value as "20;" and errors
info selection level residue attribute buried; select clear
key white:0 orangered:60 pos 0.70,0.08 size 0.25,0.04                        # colour key = a top-level model (#2 here); ~key removes it
```
`measure sasa /A & protein` sets `area` (SAS of chain A alone) instead; the next `measure sasa` overwrites it.

## 5. Contacts across the interface
```
hbonds /A restrict /B reveal true showDist true log true           # "8 hydrogen bonds found" + donor/acceptor table
hbonds /A restrict /B saltOnly true name "salt bridges" color magenta
contacts /A restrict /B reveal true log true                       # van der Waals contacts ("51 contacts")
hbonds (ifaceAB & /A) restrict (ifaceAB & /B) reveal true color gold radius 0.08   # only within the patch
~hbonds; ~contacts
```
Waters bridge the chains unless excluded: `restrict /B & ~solvent`. Structured alternative without
pseudobonds: `contacts(spec1="/A", spec2="/B", cutoff=4.0)` → residue pairs with `min_distance`,
`residues1`, `residues2`; `polar_only=True` ≈ H-bonds.

## 6. Figure recipe
```
hide #1 atoms; cartoon #1; color #1/A gray target ac; color #1/B lightgray target ac
show ifaceAB atoms; style ifaceAB stick
color ifaceAB & /A cornflowerblue target ac; color ifaceAB & /B orange target ac; color ifaceAB & ~C byhetero
surface #1/B & protein; transparency #1/B 60 target s; color ifaceAB & /B orange target s   # patch on B's surface
label ifaceAB & /A residues text "{0.name}{0.number}" height 0.7 bgColor white color black
view ifaceAB; cofr ifaceAB; lighting soft; graphics silhouettes true
```
Colour surfaces through atom specs + `target s`: the SES gets the next free sub-model id (`#1.3` when
hbonds and contacts pseudobond groups exist, `#1.4` with a salt-bridge group too), so a guessed `#1.1` is wrong — check `scene`.
Face-on view (camera on B's side looking at A's patch; `python` tool, then hide or fade B):
```python
from chimerax.core.commands import atomspec, run
from chimerax.geometry import orthonormal_frame, normalize_vector
ev = lambda spec: atomspec.AtomSpecArg.parse(spec, session)[0].evaluate(session).atoms
cA, cB = (ev("ifaceAB & /%s" % c).scene_coords.mean(axis=0) for c in "AB")
z = normalize_vector(cB - cA)                     # camera z; the camera looks along -z, i.e. from B toward A
session.main_view.camera.position = orthonormal_frame(z, origin=0.5 * (cA + cB) + 80 * z)
run(session, "view ifaceAB")                      # refits without rotating
```
Open book (both patches facing the viewer) — do it on a copy, atom moves cannot be undone:
```
~key; ~hbonds; combine #1 modelId 2 name openbook; hide #1 models   # modelId must be free (the colour key is #2); copy keeps colours, display state, attributes, pseudobonds
turn y 180 atoms #2/B center #2/B                                # flip B about the screen y axis
move x 25 atoms #2/B; move x -25 atoms #2/A; view #2             # pull apart (≈ half a partner width each)
close #2; show #1 models                                         # back to the complex
```
Frozen names are not copied: on `#2` use explicit residues or rerun `measure buriedarea … select true` on `#2` before
moving. Do not `split #1 chains` for this: it deletes the original atoms, so frozen names vanish (`ifaceAB` → "invalid atom
specifier") and selections and surfaces go with them.

## 7. Export residue lists
```
info residues ifaceAB                                              # "residue id /A:8 name LEU index 7" lines in output
info residues ifaceAB saveFile ~/interface_residues.txt
info residues ::buried>20 attribute buried saveFile ~/buried.txt     # after section 4
save ~/buried.defattr attrName r:buried models #1                   # reload later with `open ~/buried.defattr`
select ifaceAB; save ~/interface.pdb models #1 selectedOnly true; select clear
```
`residue_table(spec="ifaceAB")` → rows with model, chain, number, name, ss, b_mean, atoms_shown,
ribbon_rgb, atom_rgb — identity, display and colour, not areas; pair it with the `info residues …
attribute` text or the python `result` for numbers. `info residues … attribute area` silently skips
residues that lack the attribute (chain B after `measure sasa /A`).

## 8. Verify
- `run` → `output` holds the numbers ("N buried areas: …", "Buried area between … = …", "N contacting residues"); parse them.
- `selection_info("ifaceAB")` → residues per chain with ranges; 0 atoms = bad spec or `areaCutoff` too high.
- `residue_table("ifaceAB")` → `atoms_shown > 0`, `atom_rgb` [100,149,237] (cornflowerblue) / [255,165,0] (orange).
- `measure(kind="sasa", spec1="/A & protein")` repeats `measure sasa`; per side = (A + B − AB)/2 with
  `spec1="(/A | /B) & protein"` for AB.
- `render` → `palette` contains the patch colours, no `clipped_edges`; `layout(by="items",
  items=["ifaceAB & /A", "ifaceAB & /B", "#1 & ~ifaceAB"], occlusion=True)` → both patches visible,
  low `occluded_fraction` (open book: specs on `#2`); `compare_renders` before/after the flip → large change.

## Pitfalls
- `interfaces` and `measure buriedarea` never exclude solvent, ions, ligands or glycans: always `& protein`.
- `cutoffArea` (measure) means "greater than", `interfaceResidueAreaCutoff` (interfaces) "at least": lists can differ at the threshold.
- An attribute test needs a space before `;`: `select ::buried>20; …` fails ("'>' not supported between … 'float' and 'str'") — own line.
- Hydrogens change SAS by a few %; compare structures consistently (`delete H` or `addh` on all).
- `turn/move … atoms` edits coordinates; surfaces follow, H-bond pseudobonds become meaningless.
- Changed VDW radii (`size atomRadius`) change SASA: `size atomRadius default` before measuring.

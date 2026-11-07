---
name: selection-and-zones
title: Selection and zone tools
app: chimerax
description: Make, modify and inspect selections (select, add/subtract/intersect, up/down, clear, ~select), zone selections by distance, named targets (name), the residue zone display (zone), surface and volume zones, and using `sel` in other commands
tags: select, selection, zone, name, sel, binding site, neighbours, pocket
---
A selection (green outline) is a set of items reusable as `sel` in any command. Specs alone do not
need a selection — select when the user will act on it in the GUI, when a command wants `sel`, or
to freeze a set with `name frozen`. Syntax verified against the ChimeraX 1.11 docs.

## 1. Select
```
select ligand                               # replace the selection
select #1/A:10-50 | :HEM
select ligand :< 5 & protein                # residues within 5 Å of ligand (zone spec)
select zone ligand 5 protein residues true  # same with the zone subcommand; `extend true` adds ligand
select zone #1.2 8                          # works with non-atomic models (surfaces, maps) too
select sel residues true                    # promote partial residues to whole residues
select #1 sequence "C..C"                   # residues matching a sequence pattern / regex
select pbonds minimumLength 3.5             # pseudobonds by length
select add :arg,lys; select subtract solvent; select intersect /A
select up; select down                      # widen / narrow along the cascade (atoms → residues → chains → model)
select clear; ~select; ~select ligand       # clear all / deselect a part
select ~sel                                 # invert; `select ~sel & ##selected` inverts within selected models
```

## 2. Use the selection
```
color sel orange; style sel ball; show sel atoms; hide sel cartoons; label sel residues
view sel; cofr sel
surface sel; measure sasa sel; hbonds sel reveal true
delete sel                                  # irreversible (no undo for atoms): confirm with the user first
save ~/part.pdb #1 selectedOnly true
info selection level residue                # list in the log; `attribute bfactor` etc.
name frozen pocket sel                      # keep the current contents as target `pocket`
```
`selection_info()` (default spec `sel`) returns atoms/residues per chain, residue ranges, names and
the centre; `scene` → `selection` gives counts and chains.

## 3. Named targets
```
name tm1 /A:34-64                           # synonym, expanded when used
name frozen core sel                        # fixed set evaluated now
name list; name list builtins true; name delete tm1; name delete all
```

## 4. Zones
Spec form (any command): `ref :< d` residues, `ref @< d` atoms, `ref /< d` chains, `ref #< d`
models; `>` means farther than. Combine with `&` / `~`:
```
show (ligand :< 5) & protein atoms
color (#2 @< 4) & #1 hot pink target a      # atoms of #1 near #2
select #1 & (#2 :> 15)                      # residues of #1 far from #2
```
Residue zone display (atoms + labels + map density near one residue):
```
zone :LIG residueDistance 5 labelDistance 4 surfaceDistance 8
zone :LIG label false ribbons true
zone clear
```
Surfaces and maps:
```
surface zone #1.1 nearAtoms ligand distance 6; surface unzone #1.1
volume zone #2 nearAtoms ligand range 3; volume unzone #2
```

## 5. Typical binding-site routine
```
select ligand :< 5 & protein; select sel residues true
name frozen site sel
hide #1 atoms; cartoon #1; show ligand | site atoms; style ligand ball; color site & C gray target a
label site residues height 0.8; view site; cofr ligand
hbonds ligand restrict site reveal true showDist true
select clear
```

## 6. Verify
- `selection_info("sel")` or `selection_info("ligand :< 5 & protein")` → `atoms`, `residues`,
  `by_structure["#1"][…].residue_ranges`; zero atoms = wrong spec.
- `scene` → `selection.atoms/residues/chains`; `events` reports "selection changed" when the user
  clicks in the window.
- `render` shows the green outline (`graphics selection color lime width 1` tunes it); clear the
  selection before saving figures.

## Pitfalls
- Selection ≠ specification: a spec evaluates every time; `sel` changes when the user clicks.
- `select zone … residues true` selects whole residues; the spec form `:<` already does.
- `select up`/`down` depend on the last selection; after `select clear` there is no cascade.
- `delete sel` cannot be undone; prefer `hide sel atoms`.
- Built-in names (`ligand`, `protein`, …) cannot be redefined with `name`.
- The green outline is part of `render`'s pixels (appears in `palette`); `layout` disables it.

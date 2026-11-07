---
name: atom-spec-cheat-sheet
title: Atom specification cheat sheet
app: chimerax
description: ChimeraX target specification: #model /chain :residue @atom hierarchy, lists and ranges, wildcards, built-in classes (protein, ligand, solvent, helix…), attribute tests (@@bfactor>40), zones (:<5) and & | ~ combinations
tags: atomspec, selection, specification, syntax, zone, attributes
---
Every command takes a spec; a wrong spec silently matches nothing. Check with
`selection_info("spec")` (atoms/residues per chain, residue ranges, names, centre) before relying on it.

## Hierarchy  `#model /chain :residue @atom`
| symbol | level | examples |
|---|---|---|
| `#` | model (hierarchical ids) | `#1`, `#1.3`, `#1-3`, `#2.1-3,5`, `#*.1` (sub-model 1 of all) |
| `/` | chain ID | `/A`, `/A,C`, `/B-D,F` (ranges are alphabetical) |
| `:` | residue number or name | `:51`, `:10-20,45`, `:start-40`, `:lys,arg`, `:HEM` |
| `@` | atom name | `@CA`, `@n,ca,c,o`, `@S*` |

- Descending symbols narrow: `#1/A:10-20@CA`. Returning to a higher level resets:
  `/A/B:12-20@CA` = all of chain A plus the CA atoms of B:12-20.
- No space next to a hyphen in ranges; `start`/`end`/`*` may replace a range limit.
- `#!1` = the parent model without its sub-models. A leading `=` excludes implicit bonds.
- Residue names made of digits only: `::name="276"`. Wildcards `*`, `?`, `[ab]` in names.
- Case: chain IDs are case-insensitive unless a model mixes upper and lower case; residue and atom
  names are case-insensitive.

## Built-in classes (cannot be redefined)
- Categories (mutually exclusive): `main`, `ligand`, `ions`, `solvent` (heuristic; verify).
- Polymer parts: `protein`, `nucleic`, `backbone`/`mainchain`, `min-backbone`, `sidechain` (+CA),
  `sideonly`, `ribose`.
- Secondary structure: `helix`, `strand`, `coil`.
- Element symbols (`C`, `Fe`), atom types (`Car`, `N3+`), functional groups (`amide`, `disulfide`,
  `aromatic-ring`, `carboxylate`), `template-mismatch` (probably missing atoms).
- `sel` (current selection), `sel-residues`, `pbonds`, `pbondatoms`, `hbonds` (H-bond pseudobonds),
  `hbondatoms`, `last-opened`, `all`. `name list builtins true` prints the complete list.

## Attribute tests  `@@atom`, `::residue`, `//chain`, `##model`
Operators `=  !=  ==  !==  >  <  >=  <=`; `^` before the name = attribute not assigned.
```
@@bfactor>40 & @CA            ::num_atoms>=10            ::ss_type=1        (1 helix, 2 strand, 0 coil)
@@display   ~@@display        //identity="#1/A"          ##name="2gbp map 5"
@@occupancy<1                 ::name="276"               ##selected
@@idatm_type=Car              ::^chi3                    ::pae_domain=2
```
Attributes also come from `setattr`, `.defattr` files, `measure sasa` (`area`), `measure mapvalues`
(`mapvalue`), `alphafold match` (`c_alpha_distance`, `missing_structure`), `clashes setAttrs true`.

## Zones  `reference  operator  distance`  (operator = level symbol + `<` or `>`)
```
ligand :< 5            residues with any atom within 5 Å of ligand
#1:GTP @< 3.8          atoms within 3.8 Å of GTP in model 1
#2 & #1 @< 5           atoms of model 2 within 5 Å of model 1
:LIG :> 10             residues farther than 10 Å (complement of :< 10)
/A /< 8                chains with any atom within 8 Å of chain A
```
`select zone`, `surface zone`, `volume zone`, `zone` are the command forms (skill: selection-and-zones).

## Combinations
`&` and, `|` or, `~` not; `&` binds tighter than `|`; parentheses allowed (keep a space between a
parenthesis and anything that is not an operator).
```
/A & protein                      protein part of chain A
/A & ~ :HEM                       chain A without HEM
(ligand | ions) @< 4.8            atoms near ligand or ions
(ions @< 4) & ~ions               neighbours of ions, excluding the ions
:cys@sg & ~disulfide              free cysteine sulfurs
sidechain & ligand :< 4           side chains (incl. CA) of residues near ligand
helix & :arg,lys                  basic residues in helices
#1:asp,glu & (#2 :< 10)           acidic residues of #1 within 10 Å of #2
@ca & #1/B,E#2/A,D                CA atoms of chains B,E of #1 and A,D of #2
```

## User-defined targets
```
name tm1 /A:34-64                 # evaluate-later synonym (expands to the string)
name frozen pocket sel            # evaluate-now: fixes the current contents
name list; name delete tm1
```
Names start with a letter; use them like any spec: `color tm1 medium blue`.

## Model numbers you will meet
- Molecular surfaces of `#1` are `#1.1`, `#1.2`, …; a surface enclosing several models is top-level.
- Pseudobond groups (hydrogen bonds, clashes, distances, missing structure) are sub-models.
- Maps are top-level (`#2`), their isosurface is `#2.1`; `molmap`/`volume zone newMap` create new ones.
- 2D labels, colour keys, scale bars, axes/planes are their own models — `scene` lists everything.

## Pitfalls
- `:10-20` applies to every chain unless preceded by `/A`; `#1:10-20` to every chain of model 1.
- Blank spec = all, but some commands need a non-blank spec (`label`, `info distmat`, `measure buriedarea`).
- `ligand`/`solvent`/`ions` are rules, not annotations: a covalently attached glycan is `ligand`,
  a 10-copy buffer molecule may be `solvent`. `selection_info("ligand")` shows the residue names.
- A spec that parses but matches nothing yields "no atoms specified" in `error` or an empty `changes`.
- Specs containing `#`, `:` or spaces inside attribute strings must be quoted: `::name="CA"`.

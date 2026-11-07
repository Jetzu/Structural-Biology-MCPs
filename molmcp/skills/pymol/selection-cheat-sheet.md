---
name: selection-cheat-sheet
title: Selection language cheat sheet
app: pymol
description: PyMOL selection syntax - property selectors, macros, logic, proximity (within/around/expand), byres/bychain, ss, b-factor, flags, named selections and how to check them
tags: selection, syntax, atoms, residues, chains, within, byres
---
Every `run`/`python` command takes selections. Check a non-trivial one with `selection_info(expr)` before
acting on it (atom/residue counts per chain, residue names, extent). Example object: `prot`.

## Named selections
```pml
select lig, prot and organic
select pocket, byres (prot and polymer within 5 of lig)
indicate pocket
delete pocket
```
Named selections are static atom sets (evaluated once) and appear in `scene` under `selections`.
Names must not contain spaces; avoid keywords (`all`, `visible`, `sele`, object names). `%prot` refers to the
object explicitly when a selection has the same name. `?name` = "name if it exists, else nothing".

## Property selectors (keyword value; `+` lists, `-` ranges, `*`/`?` wildcards)
| selector | examples |
|---|---|
| object / model | `prot`, `%prot`, `model prot` |
| `chain` | `chain A`, `chain A+B`, `chain ""` (blank chain) |
| `segi` | `segi ""`, `segi A*` |
| `resi` | `resi 25`, `resi 25-30+45`, `resi 52A` (insertion code), `resi \-3` (negative) |
| `resn` | `resn HOH`, `resn ASP+GLU`, `resn A*` |
| `name` | `name CA`, `name N+CA+C+O`, `name C*` |
| `elem` | `elem C`, `elem N+O`, `elem ZN` |
| `alt` | `alt A+""` (altloc A or none) |
| `b`, `q`, `partial_charge`, `formal_charge` | `b > 40`, `q < 1`, `formal_charge > 0` |
| `ss` | `ss H` (helix), `ss S` (strand), `ss L` (loop), `ss H+S` |
| `id`, `index`, `rank` | `id 1-100`, `index 1-100` |
| `x`, `y`, `z` | `x < 10` (coordinates in Angstrom) |
| `state` | `state 1` |
| `rep` | `rep cartoon`, `rep sticks` (atoms shown in that rep) |
| `color` | `color red` |
| `flag` | `flag 25` (ignore flag), `flag 0` |
| `pepseq` | `pepseq PQIT` (contiguous sequence motif) |
| `text_type`, `numeric_type` | force-field types if assigned |

## Class keywords
`polymer` `polymer.protein` `polymer.nucleic` `organic` (small molecules) `inorganic` (ions) `solvent`
(water) `metals` `hetatm` `backbone` `sidechain` `hydro`/`hydrogens` `donors` `acceptors` `guide` (CA/P)
`bonded` `visible` `enabled` `present` (has coordinates in the state) `protected` `masked` `fixed`.
`organic` includes buffer molecules (GOL, SO4, PEG...): exclude with `and not resn GOL+SO4+EDO+PEG`.

## Logic
`and`/`&`, `or`/`|`, `not`/`!`, parentheses. Precedence is not obvious - always bracket mixed expressions:
`(chain A and resi 25) or (chain B and resi 30)`. `first sel` / `last sel` pick one atom.

## Macros (`/object/segi/chain/resi/name`)
```pml
select m1, /prot//A/25/CA
select m2, prot//A/25-30/CA
select m3, A/25/CA
```
With a leading `/` fields are read object, segi, chain, resi, name (any may be empty). Without a leading `/`
fields are read from the right: `name`, `resi/name`, `chain/resi/name`, ... - so `prot/A/25/CA` is NOT
object/chain/resi/name (it matches nothing). Use the leading-slash form or `prot and chain A and resi 25 and name CA`.

## Proximity
| expression | meaning |
|---|---|
| `s1 within 4 of s2` | atoms of s1 within 4 A of any atom of s2 (s1 may include s2) |
| `s1 around 4` | atoms within 4 A of s1, excluding s1 |
| `s1 expand 4` | s1 plus atoms within 4 A |
| `s1 near_to 4 of s2` | like within but excludes s2 atoms |
| `s1 beyond 8 of s2` | atoms of s1 farther than 8 A from s2 |
| `s1 gap 1` | atoms whose vdW surfaces are >= 1 A from s1 |
| `neighbor s1` | atoms bonded to s1 (not s1 itself) |
| `s1 extend 2` | s1 plus atoms up to 2 bonds away |
| `s1 like s2` | atoms of s1 with the same resi/name as atoms of s2 (compare chains/objects) |
Expanders: `byres`, `bychain`, `bymolecule`/`bymol`, `byobject`, `bysegi`, `byfragment`, `byca` (the CA of
the residues). `byres (... within ...)` is the standard "complete residues near X" idiom.
```pml
select interfaceA, byres ((prot and chain A and polymer) within 4 of (prot and chain B and polymer))
select waters_near, solvent within 3.5 of lig
select sidechains_near, (byres (prot and polymer within 4.5 of lig)) and sidechain
select ca_near, byca (prot within 6 of lig)
```

## Pitfalls
- `resi` values are strings (insertion codes): `resi 25-30` works, arithmetic does not.
- Hydrogens are usually absent in crystal structures: `hydro` is empty; `h_add sel` adds them.
- `solvent` = waters only; detergents/ions are `organic`/`inorganic`.
- A selection made with `within` does not update when atoms move or objects load; re-run `select`.
- Deleting an object silently empties selections that referred to it.
- Compare chains inside one object with `like`; `align` needs two objects (see alignment skill).
- Count atoms vs residues: `selection_info` reports both; in Python `cmd.count_atoms("sel")` and
  `len(set((chain, resi) for ...))` via `iterate`.

## Verify
- `selection_info("byres (prot within 5 of lig)")` -> `residues`, residue names/ranges per chain, `center`.
- `python`: `result = cmd.count_atoms("pocket")` or
  `stored.r = []; cmd.iterate("pocket and name CA", "stored.r.append((chain, resn, resi))"); result = stored.r`.
- `scene` -> `selections` lists names with atom counts; `indicate sel` highlights it in the GUI for the user.

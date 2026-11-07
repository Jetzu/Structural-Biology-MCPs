---
name: structure-alignment
title: Structure alignment and superposition
app: pymol
description: align / super / cealign / fit / pair_fit / rms_cur / extra_fit - choosing the method, reading RMSD and atom counts, alignment objects, by-chain and multi-structure superposition, reporting results
tags: alignment, superposition, rmsd, align, super, cealign, extra_fit, comparison
---
Example: mobile object `mob` superposed on target `ref` (both loaded as separate objects). Alignment
commands move the whole mobile OBJECT (all its atoms), so mobile and target must be different objects.

## Which command
| command | use when | matching |
|---|---|---|
| `align mob, ref` | same protein / >30% identity | sequence alignment, then iterative outlier rejection |
| `super mob, ref` | low identity, same fold | structure-based (sequence-independent) |
| `cealign ref, mob` | remote homologs, different sizes - NOTE target first | CE algorithm, CA only by default |
| `fit mob, ref` | identical atom names/numbering (e.g. mutant vs WT) | by identifiers, no alignment step |
| `pair_fit a, b, c, d` | explicit atom pairs | one-to-one |
| `rms_cur mob, ref` | RMSD WITHOUT moving (after a fit, or docking poses) | identifiers (`matchmaker`) |
| `extra_fit sel, ref, super` | many objects onto one | per object |

## Basic sequences
```pml
align mob and name CA, ref and name CA, object=aln_mob_ref
super mob, ref, object=sup
cealign ref, mob
align mob and name CA, ref and name CA, cycles=0
```
- `name CA` restricts to backbone CA (typical reporting); omit for all-atom.
- `cycles=0` disables outlier rejection -> RMSD over ALL matched atoms (larger, honest number). Default
  `cycles=5, cutoff=2.0` removes outliers -> the "core" RMSD. Report which one you quote.
- `object=name` creates an alignment object (shown in the sequence viewer; `set seq_view, 1`); export it with
  `save aln.aln, aln_mob_ref` (ClustalW) or `save aln.fasta, aln_mob_ref`. `disable aln_mob_ref` hides the
  dashed lines it draws.
- RMSD only, no movement: add `transform=0` (align/super/cealign).
- Restrict to a region: `align mob and chain A and resi 10-120, ref and chain A`.
- `cealign` prints `RMSD x over N residues`; `super` is usually better than `align` below ~30% identity.

## Reading the numbers (use `python`)
```python
r = cmd.align("mob and name CA", "ref and name CA", object="aln_mob_ref")
s = cmd.super("mob", "ref", transform=0)
c = cmd.cealign("ref", "mob", transform=0)
result = {
    "align": {"rmsd_refined": round(r[0], 3), "atoms_refined": r[1], "cycles": r[2],
              "rmsd_initial": round(r[3], 3), "atoms_initial": r[4], "score": r[5], "residues_aligned": r[6]},
    "super_rmsd": round(s[0], 3), "super_atoms": s[1],
    "cealign": {"rmsd": round(c["RMSD"], 3), "aligned_residues": c["alignment_length"]},
    "rms_cur_ca": round(cmd.rms_cur("mob and name CA", "ref and name CA", matchmaker=4), 3),
}
```
`align`/`super` return a 7-tuple: (RMSD after refinement, atoms after refinement, refinement cycles, RMSD before
refinement, atoms before refinement, alignment score, residues aligned). `cealign` returns a dict.
`rms_cur`/`fit` match atoms by identifiers (`matchmaker=0` or `1`: segi/chain/resn/resi/name/alt must agree;
`2` = by atom `ID`, `3` = by `rank`, `4` = by `index`, i.e. the same atom order). For the same protein with
different chain IDs use `matchmaker=4`. For different sequences get the no-move RMSD from
`align ..., cycles=0, transform=0` instead.

## By chain (chains of ONE object cannot be aligned to each other directly)
```python
chains = [c for c in cmd.get_chains("prot") if cmd.count_atoms("prot and chain %s and polymer" % c) > 0]
for c in chains:
    cmd.create("ch_" + c, "prot and chain %s and polymer" % c)
ref = "ch_" + chains[0]
result = {}
for c in chains[1:]:
    r = cmd.align("ch_%s and name CA" % c, ref + " and name CA", cycles=0, transform=0)
    result[c] = {"rmsd_ca": round(r[0], 2), "atoms": r[1]}
cmd.delete("ch_*")
```
`split_chains prot` does the same split permanently (objects `prot_A`, `prot_B`, ...). Multi-state objects
(NMR, trajectories): `intra_fit prot and name CA, 1` fits all states onto state 1 and returns per-state RMSDs;
`split_states prot` makes one object per state.

## Many structures onto one
```pml
extra_fit name CA, ref, super
```
Aligns every object containing CA atoms (except `ref`) onto `ref`; `method=align|super|cealign`. `alignto ref`
is the same but iterates over ALL objects (including maps and ramps, which error) - prefer `extra_fit` with a
selection. After superposition colour by object (`util.cbc`-style: `color marine, ref; color orange, mob`),
`set cartoon_transparency, 0.5, ref`, `zoom ref` and render.

## Pitfalls
- Argument order differs: `align MOBILE, TARGET` but `cealign TARGET, MOBILE`.
- `align` on `all` vs `all` of the same object errors ("mobile selection must derive from one object only").
- Maps/meshes/ramps stay put when a molecule is moved: recompute or load maps after alignment.
- Undo a superposition: `matrix_reset mob` (resets the object's TTT matrix) - works if nothing else was applied.
- Ligands and waters are moved with the object (good); an `align` on protein atoms only is standard.
- Very different sizes: `super` may align few atoms with a tiny RMSD - always report `atoms`/`residues_aligned`.

## Verify
- `object_info("mob")` -> `extent`/`center` now overlap `ref`'s.
- `layout(by="object")` -> both objects visible with overlapping bboxes and `contacts_2d` between them.
- `render()` before and after, then `compare_renders()` -> `changed_fraction` > 0 proves the object moved.
- `scene` -> the alignment object appears with type `alignment`.

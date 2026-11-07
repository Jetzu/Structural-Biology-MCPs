---
name: mutagenesis
title: Point mutations with the mutagenesis wizard (scripted)
app: pymol
description: Mutate residues with the mutagenesis wizard from commands or Python, choose rotamers, check clashes, save the result
tags: mutagenesis, wizard, rotamer, point mutation, modelling
---
When to use: "mutate residue 45 to alanine", "make the F508del/W → A variant", "model a substitution and check clashes".
PyMOL's mutagenesis is a wizard; it works headless through the Python API (`python` tool), not through plain commands.

1. One mutation (three-letter residue names, upper case):
   ```python
   from pymol import cmd
   cmd.wizard("mutagenesis")
   cmd.do("refresh_wizard")
   w = cmd.get_wizard()
   w.set_mode("ALA")                      # target residue type, e.g. ALA, PHE, ARG, GLY
   w.do_select("/1ubq//A/48/")            # the residue to mutate: /object//chain/resi/
   w.apply()                              # applies the first (most probable) rotamer
   cmd.set_wizard()                       # leave the wizard
   result = {"mutated": "1ubq A/48 -> ALA"}
   ```
2. Rotamer choice: after `do_select`, `w.bump_scores` lists the clash score per rotamer (lower is better) and
   `cmd.frame(n)` selects rotamer n before `w.apply()`:
   ```python
   scores = list(w.bump_scores) if hasattr(w, "bump_scores") else []
   best = scores.index(min(scores)) + 1 if scores else 1
   cmd.frame(best); w.apply()
   result = {"rotamers": len(scores), "chosen": best, "bump_scores": [round(s, 2) for s in scores]}
   ```
3. Several mutations: loop over `(chain, resi, newtype)` and repeat steps 1–2 for each; keep the wizard open between
   residues (`w.set_mode`, `w.do_select`, `w.apply`) and call `cmd.set_wizard()` once at the end.
4. Check the result: `contacts(selection1="1ubq and resi 48", selection2="1ubq and not resi 48", cutoff=2.2)` lists
   close contacts (clashes) after mutation; `measure(kind="count", ...)` confirms the atom count changed.
   Hydrogens: the wizard adds the side chain without hydrogens unless the structure has them; `h_add 1ubq and resi 48`
   completes them, `remove hydro` strips all.
5. Save: `save_file(path="~/1ubq_K48A.pdb", selection="1ubq")`; keep the original with `create wt, 1ubq` *before*
   mutating if the user wants both.
6. Report: residue before/after, rotamer used and its bump score, and any contacts below 2.5 Å.
Pitfalls: `w.set_mode` wants the three-letter code in upper case; selections must resolve to exactly one residue
(use `/obj//chain/resi/`); the wizard needs a loaded structure with complete backbone atoms (N, CA, C) for that residue.

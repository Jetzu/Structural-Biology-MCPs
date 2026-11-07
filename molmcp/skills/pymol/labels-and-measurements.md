---
name: labels-and-measurements
title: Labels and measurements
app: pymol
description: Atom/residue labels with Python expressions, one-letter codes, label styling (size, font, outline, position, background, connector), distance/angle/dihedral objects and modes, get_distance etc., dash styling, pseudoatom text labels
tags: labels, distance, angle, dihedral, measurement, dashes, annotation
---
Example object `prot`, ligand selection `lig`, pocket selection `pocket`.

## Labels
```pml
label prot and name CA and resi 25+50, "%s%s" % (resn, resi)
label pocket and name CA, "%s-%s%s" % (chain, resn, resi)
label lig and name C1, resn
label prot and resi 25 and name CA, "%.1f" % b
label prot and name CA and resi 25+50
```
- Expression namespace: `name resi resn resv chain segi model alt q b type index rank ID ss vdw elec_radius elem
  geom flags color cartoon valence formal_charge partial_charge numeric_type text_type label stereo`. Strings must
  be quoted; use `%` formatting. An empty
  expression (last line) clears the labels. Labels are per atom - label ONE atom per residue (`name CA`, or
  `name P` for nucleotides, `name C1` for a ligand) or the text piles up.
- One-letter residue codes (not available as `one_letter` in the label namespace):
```python
from pymol.exporting import _resn_to_aa as one_letter
cmd.alter("pocket and name CA", "label = one_letter.get(resn, resn) + resi", space={"one_letter": one_letter})
cmd.show("labels", "pocket and name CA")
result = cmd.count_atoms("pocket and name CA")
```
- Free text anywhere: `pseudoatom note, pos=[10, 10, 10], label="active site"` (then `set label_size, 24, note`);
  `pseudoatom lig_center, lig` creates a point at the centre of a selection (`label lig_center, "ligand"`).

Styling (global, per object, or per selection with `set name, value, sel`):
```pml
set label_size, 20
set label_size, -0.8, lig
set label_color, black
set label_outline_color, white
set label_font_id, 7
set label_position, [0, 0, 3]
set label_bg_color, grey90
set label_bg_transparency, 0.3
set label_connector, 1
set float_labels, 1
set label_shadow_mode, 0
```
- `label_size` in points, or negative = Angstrom (scales with zoom; good for figures). Fonts 5-15 are vector
  fonts (ray-traceable), 7 = sans bold, 15 includes greek. `label_outline_color` adds a halo.
- `label_position [x, y, z]`: values within -1..1 only align the text on the atom; values beyond that are
  offsets of (|value| - 1) A in camera space (z = 3 brings labels 2 A in front of sticks). `label_bg_*` draws a box, `label_connector 1` a leader line to the atom.
- `float_labels 1` draws labels on top of everything (OpenGL only); `label_shadow_mode 0` = no shadows in ray.
- `hide labels, sel` / `show labels, sel` toggle without deleting the text. `set label_digits, 2` for floats.

## Measurements (each creates an object of type `measurement`)
```pml
distance d_ca, prot and chain A and resi 25 and name CA, prot and chain B and resi 25 and name CA
distance hb, lig, pocket, 3.5, mode=2
distance pipi, lig, pocket, mode=6
distance centroids, lig, pocket and chain A, mode=4
angle a1, /prot//A/25/N, /prot//A/25/CA, /prot//A/25/C
dihedral psi25, /prot//A/25/N, /prot//A/25/CA, /prot//A/25/C, /prot//A/26/N
```
- `distance name, sel1, sel2, cutoff, mode`: mode 0 (default) = all atom pairs within `cutoff` (always pass
  the cutoff explicitly), 1 = bonded pairs only (bond lengths), 2 = polar contacts only (N/O donors-acceptors,
  the h-bond figure standard; hydrogens not required), 3 = like 0 but skips atoms within `distance_exclusion` bonds,
  4 = distance between the centroids of the two selections, 5 = pi-pi and pi-cation, 6 = pi-pi only,
  7 = pi-cation only, 8 = like 3 with cutoff as a fraction of vdW sums. `label=0` suppresses the number.
- Single numbers without objects, via `python`:
```python
result = {
    "d": cmd.get_distance("/prot//A/25/CA", "/prot//B/25/CA"),
    "angle": cmd.get_angle("/prot//A/25/N", "/prot//A/25/CA", "/prot//A/25/C"),
    "dihedral": cmd.get_dihedral("/prot//A/25/N", "/prot//A/25/CA", "/prot//A/25/C", "/prot//A/26/N"),
    "polar_pairs": len(cmd.find_pairs("lig and elem N+O", "pocket and elem N+O", cutoff=3.5)),
}
```
- `set_dihedral a1, a2, a3, a4, 120` rotates a torsion (edits coordinates). `phi_psi sel` prints
  backbone angles (`cmd.get_phipsi(sel)` returns a dict).

Dash styling (global or per measurement object):
```pml
set dash_width, 3
set dash_gap, 0.3
set dash_length, 0.3
set dash_radius, 0.08
set dash_round_ends, 0
set dash_color, yellow, hb
color yellow, hb
set label_distance_digits, 2
set label_size, 14, hb
hide labels, hb
show labels, hb
```
`dash_radius` > 0 sets the ray-traced thickness (else from `dash_width`); `dash_gap 0` draws solid lines.
Delete a measurement with `delete hb`. The interactive `wizard measurement` is for mouse clicking by the user;
the agent should use `distance`/`get_distance`.

## Pitfalls
- Labels on every atom of a residue overlap: restrict to one atom name.
- `label` expressions run per atom - formatting errors appear as a Python traceback in the `run` result.
- Default label colour is "front" (auto contrast); on a white background set `label_color, black` explicitly
  for ray tracing.
- Measurement objects reference atoms: deleting/reloading the molecule empties them.
- `distance` mode 2 with `cutoff` omitted uses the `h_bond_cutoff_center`/`_edge` settings (3.6/3.2 A).

## Verify
- `scene` -> objects of type `measurement` (`d_ca`, `hb`, ...); `python`: `result = cmd.get_distance(...)` for
  the value to report; to read label texts back:
  `stored.l = []; cmd.iterate("pocket and name CA", "stored.l.append(label)"); result = stored.l`.
- `render(width=1200, height=900)` + `compare_renders()` before/after labelling: the changed region should be
  near the labelled atoms (labels are small; use a large render).
- `layout(by="items", items=["lig", "pocket"])` to see where annotated groups sit in the frame before adding labels.

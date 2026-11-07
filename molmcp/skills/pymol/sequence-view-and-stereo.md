---
name: sequence-view-and-stereo
title: Sequence viewer, secondary structure and stereo
app: pymol
description: seq_view settings (format, labels, location, colours, alignment display), sequence extraction and motif selection, secondary-structure assignment (dss, alter ss, rebuild) and phi/psi, stereo 3D viewing modes and stereo figure pairs, R/S stereochemistry (assign_stereo, needs RDKit)
tags: seq_view, sequence, secondary structure, dss, phi psi, stereo, chirality, stereochemistry
---
Example object `prot`.

## Sequence viewer
```pml
set seq_view, 1
set seq_view_format, 0
set seq_view_label_mode, 1
set seq_view_location, 0
set seq_view_label_color, black
set seq_view_label_spacing, 5
set seq_view_overlay, 0
set seq_view_gap_mode, 1
set seq_view_color, grey50
```
- `seq_view 1/0` shows/hides the sequence bar (GUI only; harmless headless). `seq_view_format`: 0 one-letter
  codes, 1 three-letter residue names, 2 atoms, 3 chains, 4 states. `seq_view_label_mode`: 0 object names,
  1 names + residue numbers for the first object, 2 for all objects, 3 nothing. `seq_view_location` 0 top /
  1 bottom. `seq_view_gap_mode 1` shows gaps for alignment objects. `seq_view_color` overrides the atom colours
  used for the letters (`-1` = atom colours). `seq_view_overlay 1` draws it over the 3D view.
- Alignment objects (`align ..., object=aln`) appear as aligned rows in the viewer (`set seq_view, 1` after
  aligning). Clicking residues in the bar creates the `sele` selection - tell the user, do not click.
- Turn it off before movie export (`mpng` disables it with a warning) and for large systems (slow).

## Sequence data and motifs
```pml
save prot.fasta, prot
select motif, prot and pepseq GIGG
select start_res, prot and chain A and resi 1-10
```
```python
fasta = cmd.get_fastastr("prot")
stored.seq = []
cmd.iterate("prot and chain A and polymer and name CA", "stored.seq.append((int(resi), resn, ss))")
ss_string = "".join((s or "L") for _, _, s in stored.seq)
result = {"fasta": fasta, "n_res": len(stored.seq), "ss": ss_string,
          "helix_res": [r for r, _, s in stored.seq if s == "H"]}
```
`pepseq XYZ` selects contiguous residues matching a one-letter motif (`?` not supported; exact letters).
Residue numbering vs index: `resi` is the author number (gaps allowed); `rank`/`index` are positional.

## Secondary structure
```pml
dss prot
alter prot and chain A and resi 87-90, ss='H'
alter prot and chain A and resi 10-12, ss='L'
rebuild
select helices, prot and ss H
select strands, prot and ss S
```
- PDB/mmCIF files bring HELIX/SHEET records; `dss` re-assigns from geometry/h-bonds (PyMOL's own algorithm,
  stricter than DSSP). Fix individual residues with `alter ... ss='H'|'S'|'L'` and `rebuild` so cartoons update.
- Fractions: `scene(detail="full")` -> `secondary_structure_atoms` per object and chain.
- Backbone torsions: `phi_psi prot and chain A and resi 25-30` prints them; in `python`
  `result = cmd.get_phipsi("prot and chain A and resi 25-30")` returns `{(model, index): (phi, psi)}`.
  Set one: `set_dihedral /prot//A/25/N, /prot//A/25/CA, /prot//A/25/C, /prot//A/26/N, 120` (moves atoms).
- `cartoon automatic` follows `ss`; `cartoon_trace_atoms 1` traces CA-only models; `set cartoon_gap_cutoff, 10`
  dashes across chain breaks.

## Stereo viewing
```pml
stereo crosseye
stereo walleye
stereo sidebyside
stereo anaglyph
stereo off
set stereo_angle, 2.1
set stereo_shift, 2.0
```
- Modes: `on` (hardware quadbuffer if available, else crosseye), `crosseye`, `walleye`, `sidebyside`,
  `anaglyph` (red/cyan), `quadbuffer` (errors without hardware support), `openvr`. `stereo_angle` (2.1) and
  `stereo_shift` (2.0) tune the eye separation; `stereo_mode` reports the active mode number (2 crosseye,
  3 walleye, 5 sidebyside, 10 anaglyph).
- In the GUI a stereo mode splits the viewport into two views and `png`/`ray` write the pair as one image
  (GUI behaviour; a headless `png` stays mono - verified). For a stereo-pair figure that works everywhere
  render two images yourself: `png left.png, width=1200, height=900, ray=1`, then `turn y, 3`,
  `png right.png, width=1200, height=900, ray=1`, then `turn y, -3` to restore; place left/right side by side
  (walleye) or swapped (crosseye) with an image tool. `set orthoscopic, 1` keeps both halves at the same scale.

## Stereochemistry (R/S)
```pml
assign_stereo prot and organic
label prot and organic and not hydro, stereo
```
- `assign_stereo sel, state, method` sets the per-atom `stereo` property (R/S) using RDKit or a Schrodinger
  installation. PyMOL 3.1.5 on this machine has neither (`Error: need SCHRODINGER or rdkit`), so this is not
  verifiable here: install `rdkit` into PyMOL's Python (`/Applications/PyMOL.app/Contents/bin/pip install rdkit`)
  or report that chirality assignment is unavailable. Labelling `stereo` without assignment shows empty strings.
- Geometry checks that always work: `get_dihedral` for improper torsions, `clean lig` (incentive MMFF
  minimisation of a ligand, keeps chirality), `h_add` before `clean`, `set_dihedral` to fix torsions,
  `cmd.get_chains`, `iterate ... (name, formal_charge)` for charges.

## Pitfalls
- `seq_view_format` etc. are global settings; they travel with saved sessions.
- `alter ... ss=` only changes the flag; `rebuild` (or any `show cartoon`) refreshes the cartoon.
- `dss` ignores residues without backbone O/N (CA-only models stay loops - use `cartoon_trace_atoms`).
- `stereo` modes affect `render`/`layout` output (two views in one image) - run `stereo off` before analysing
  renders with the tools.
- `get_fastastr` writes `?`/`X` for unknown residues; nucleic acids come out as one-letter bases.

## Verify
- `settings(names=["seq_view", "seq_view_format", "seq_view_label_mode", "stereo", "stereo_mode"])`; `scene` ->
  `settings.seq_view` and `settings.stereo`.
- `python` `result = cmd.count_atoms("prot and ss H")` before/after `dss`/`alter` to show the change.
- `render()` with a stereo mode active in the GUI: `analysis.bbox.width_frac` roughly doubles / two blobs in the
  ASCII map; `compare_renders()` after `stereo off` shows a large `changed_fraction`.

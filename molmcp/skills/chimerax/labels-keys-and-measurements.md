---
name: labels-keys-and-measurements
title: Labels, 2D annotations, colour keys and measurements
app: chimerax
description: 3D labels (atoms/residues/models, attribute text, height, colour, background), 2D titles and arrows (2dlabels), colour keys (key), scale bars, and measuring distances, angles, torsions and axis/plane/centroid objects
tags: label, 2dlabels, key, scalebar, distance, angle, torsion, measurement, annotation, axis
---
Use for "label the residues", "add a title", "colour key for the B-factor colouring", "distance
between …", "angle between the helices". Syntax verified against the ChimeraX 1.11 docs.

## 1. 3D labels (follow the atoms)
`label spec [atoms|residues|models|bonds|pseudobonds] [text …|attribute …] [height h] [color c] …`
```
label ligand residues                             # "HEM 601" style (default level for atom specs: residues)
label :LIG atoms                                  # atom names
label #1/A:50-60 residues text "{0.name}{0.number}" height 1.2 color black
label @CA & :tyr atoms attribute bfactor          # value of an attribute
label #1 models                                   # model name next to the model
label sel residues bgColor white color black height 1 offset 0,1,0
label all residues onTop false                    # do not draw through other objects
label height 1.5                                  # blank spec: change all existing labels
label delete; ~label ligand atoms; label delete residues
label defaultHeight 0.8                           # preference for new labels
label missing #1 10                               # "N residues" on missing-segment pseudobonds (models with ≤10 chains)
```
Height is in Å (`height fixed` keeps screen size; `size 48` sets texture quality / pixel size).
Labels disappear with their hidden atom; residue labels sit at the centroid (`position primary atom`).

## 2. 2D labels and arrows (screen fractions 0–1, lower-left corner)
```
2dlabels text "Hemoglobin α subunit" xpos 0.04 ypos 0.92 size 28 color black bold true
2dlabels text 'K⁺ channel' xpos 0.04 ypos 0.86 size 20      # unicode escapes
2dlabels text "Fig. 1" bgColor white margin 6 outline 1 font Helvetica
2dlabels #3 text "new text" color red xpos 0.5 ypos 0.5           # change by model id
2dlabels #3 visibility false frames 30                            # fade out (movies)
2dlabels arrow start 0.55,0.30 end 0.70,0.45 color red weight 1.5 headStyle pointer
2dlabels delete #3; 2dlabels delete all; ~2dlabels
2dlabels listfonts
```
2D labels are models (`scene` lists them), appear in `render` and movies, not in `layout` ID passes.

## 3. Colour keys and scale bars
```
key blue:min white: red:max pos 0.70,0.08 size 0.25,0.05         # colour:label pairs
key bluered :20 :50 :80 pos 0.05,0.05 size 0.3,0.04 fontSize 18 labelColor black   # palette + labels
key alphafold :0 :50 :70 :90 :100                                 # label count = palette colours
key ^piyg-5 :-2 :-1 :0 :1 :2 numericLabelSpacing proportional ticks true
key lipophilicity :-20 :0 :20 colorTreatment distinct border false
key delete                                                        # (~key) only one key at a time
scalebar 20 xpos 0.1 ypos 0.08 thickness 8 color black; 2dlabels text "20 Å" xpos 0.1 ypos 0.11 size 16
scalebar off
```
Use `camera ortho` with a scale bar (constant scale at every depth). A vertical bar (height > width)
puts labels on the right; `labelSide left/top` changes that.

## 4. Distances, angles, torsions
```
distance #1/A:50@CA #1/A:80@CA                  # Å in the log + monitor pseudobond with label
distance :LIG@N1 :ser@OG                         # each spec must give exactly one atom
distance style color gold radius 0.1 dashes 9 decimalPlaces 2 symbol true
distance delete; ~distance #1/A:50@CA #1/A:80@CA; distance save ~/distances.txt
angle #1/A:50@N #1/A:50@CA #1/A:50@C             # three atoms → degrees (four atoms → dihedral)
torsion /A:11@N,CA,C:12@N                        # ψ of residue 11; `torsion … 120` sets it (rotates the small side)
info distmat #1:LIG@C1,C2,C3                     # pairwise distance matrix
```

## 5. Geometric objects (define) and centres
```
define axis #1/A:10-30 color red radius 0.3 name helix1     # best-fit axis (rod model)
define axis #1 perHelix true                                # one axis per helix ("helix axes" group)
define plane #1/A:1-120 color yellow thickness 0.2
define centroid ligand name ligcen radius 1 color magenta   # marker at the centroid
distance #4 #5; angle #4 #5                                 # object–object (axis/plane model ids)
distance #4 #1/A:50@CA                                      # centroid marker to an atom
measure center #1 mark true; measure inertia #1/A showEllipsoid true
view zalign #4                                              # look down an axis
```
Objects are models (sub-models of the structure unless `id #N`); `close #4` removes them.

## 6. Verify
- `run` → `output` carries the number ("Distance … 12.345 Å", "Angle … 95.2°"); parse it.
- `scene` → extra models: `distances` pseudobond group, 2D label models, the key, axis/plane/
  centroid models; `render` → label colours in `palette`; `compare_renders` shows new text.
- Labels too small or huge: the ASCII map of `render` shows text as thin streaks; adjust `height`.
- `label listfonts` / `2dlabels listfonts` when a font name is rejected.

## Pitfalls
- `label` with a non-blank spec adds labels; with a blank spec it edits the existing ones.
- Residue labels default to the centroid; add `offset` or `bgColor` for legibility; `size 96`
  gives crisp text in large saved images.
- 2D label positions are window fractions: they shift if the saved image has another aspect
  ratio than the window (set `windowsize` first).
- Only one `key` and one `scalebar` exist; repeating the command updates them.
- `distance` labels follow `distance style` (`decimalPlaces`); H-bond labels follow `label`.

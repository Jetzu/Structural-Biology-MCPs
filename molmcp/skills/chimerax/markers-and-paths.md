---
name: markers-and-paths
title: Markers, links and marker paths
app: chimerax
description: Place, link, edit and delete markers (marker command), organise marker sets, measure marker paths/distances, label markers, save/open .cmm marker files, and use markers to annotate density maps (centres of mass, blob centres, map values; GUI mouse modes for local maxima)
tags: marker, markers, link, path, cmm, marker set, segment, trace, annotation, map, blob, measure length
---
Use for "put a marker at …", "trace a path through the density", "how long is the filament", "mark
the centre of each blob", "save the markers", "annotate the map". Syntax verified against the
ChimeraX 1.11 docs and a headless 1.11.1 run. Markers are atoms, links are bonds: every atom
command (`color`, `size`, `label`, `distance`, `select`, `hide`, `info`, `getcrd`) works on them.
A marker set is a model of type `MarkerSet`; marker *n* is residue *n*: `#2:3` (full spec `#2/M:3@M`,
residue name `mark`). `mark` is accepted as an abbreviation of `marker`.

## 1. Place markers and links
`marker model position point [radius r] [color c] [coordinateSystem #N]`
```
marker #2 position 16.06,-9.17,116.5 color yellow radius 1   # new set #2 (or add to existing #2); x,y,z = scene coords
marker #2 position 10,0,0                                     # defaults: radius 0.5 Å, yellow; numbered 1,2,3… in order
marker #2 position #1/A:50@CA color red                       # point-spec may be an atom spec: one atom → its position
marker #2 position #1:LIG radius 2                            # several atoms / a model → centre of their BOUNDING BOX, not the centroid
measure center #1:LIG mark true radius 2                      # mass-weighted centre of atoms as a marker (new set, see section 6)
marker #2 position 20,20,20 coordinateSystem #3               # x,y,z in model #3's own coordinates
marker link #2:1,2 color green radius 0.3                     # link two markers (existing residues of one set)
marker link #2:2,3; marker link #2:3,4                        # chain links → a path
select #2:4,5; marker link sel                                # link the two selected markers
marker segment #3 position 0,0,5 toPosition 0,20,5 color cyan radius 0.5 label "20 Å" labelHeight 2 labelColor black
```
`marker segment` makes two markers + a link + an optional 3D label (height in Å, `labelColor default`
= black/white by background). To trace a path: place markers in order, then link consecutive pairs.
Mouse placement (GUI only): `mousemode rightMode "mark maximum"` (also `"mark surface"`,
`"mark center"`, `"mark plane"`, `"link markers"`, `"move markers"`, `"resize markers"`,
`"delete markers"`); `mousemode` alone lists assignments. Headless sessions cannot use these.

## 2. Change, style, organise, delete
```
marker change #2:3 position 2.0,-29.1,121 color blue radius 2   # move/recolour one marker (and its links)
marker change #2 color orange links false                        # markers only;  `markers false` → links only
marker change #2:1-3 radius 0.4 links false
size #2 atomRadius 0.9; size #2 stickRadius 0.3                  # atom/bond commands work too
color #2:1 red; color #2 gold; rename #2 "filament trace"        # name is stored in the .cmm file
hide #2 models; show #2 models; hide #2:5; show #2 atoms         # a MarkerSet is a normal model
marker delete #2:3                                               # marker + its links (residue numbers are NOT renumbered)
marker delete #2 linksOnly true                                  # keep markers, drop every link
select #2:1; marker delete sel; close #2                         # delete selected / remove the whole set
```

## 3. Measure paths and distances
```
measure length #2                       # "Total length of N bonds = …": sum of all link lengths = path length
measure length #2:1-10                  # only links whose both ends are in the spec
distance #2:1 #2:7                      # straight-line Å + monitor pseudobond; `distance #2:1 #1/A:50@CA` to an atom
info distmat #2                         # all pairwise marker distances to the log
getcrd #2                               # x y z of every marker;  `info atoms #2 attribute radius`
measure center #2                       # "Center of mass of N atoms = (x, y, z)";  `measure inertia #2 showEllipsoid false` for axes/extent
angle #2:1 #2:2 #2:3                    # bend angle along a path (four markers → dihedral)
```
Straight-line vs path: `distance` ignores links; `measure length` sums them. Measurement syntax for
angles/torsions/axes lives in `labels-keys-and-measurements`.

## 4. Label markers
```
label #2 atoms text "{0.residue.number}" height 1.5 color black       # number every marker
label #2:1 atoms text "N-terminus"; label #2:7 atoms text "tip" bgColor white
label #2 atoms attribute mapvalue                                     # after measure mapvalues (section 6)
label #2 residues text "site {0.number}"                              # residue-level labels also work (1 residue = 1 marker)
~label #2; ~label #2:1 atoms; label delete                            # remove (set / one marker / all labels)
```
Labels are submodels (`#2.1 ObjectLabels`); they are kept in sessions but **not** in .cmm files.

## 5. Save and open marker files (.cmm, XML)
```
save ~/markers.cmm models #2                 # one set → <marker_set name="…"> with id, x,y,z, r,g,b, radius, links
save ~/markers.cmm                           # every MarkerSet in the session → <marker_sets> wrapper
save ~/markers.cmm format markers models #2,3
open ~/markers.cmm                           # one set → new MarkerSet (lowest free id, name from the file)
open ~/markers.cmm                           # several sets → grouping model #N with #N.1, #N.2 … MarkerSets
save ~/scene.cxs                             # sessions keep markers, links, labels and measurements
save ~/markers.defattr attrName mapvalue models #2      # export a marker attribute (reopen with open)
```
Reads Chimera (legacy) .cmm files too. Coordinates are written in scene coordinates at save time; if
the set was placed with `coordinateSystem #3` and #3 is later moved, re-save. Model ids are not
stored: name sets with `rename` before saving so you can tell them apart (`info models`).

## 6. Annotate density maps with markers
Open/contour maps as in `maps-and-cryoem`; a map surface is `#1.1` when the map is `#1`.
```
measure center #1 mark true radius 2 color magenta modelId 7 name mapcen   # marker at the map's centre of mass
measure center #1 level 0.02 mark true          # only density above the level counts
marker connected #1 radius 1 color lime          # a marker at the centre of every connected surface piece (blob)
marker connected #1.1 markers #7                 # add them to an existing set instead of a new "centers …" set
surface dust #1 size 5; marker connected #1      # dusted-away blobs are ignored → mark only large blobs
measure blob #1.1 triangleNumber 10              # volume/area/size of one blob (triangle number from the log)
measure mapvalues #1 atoms #2 attribute mapvalue # density at each marker → attribute; min/max/mean in the log
info atoms #2 attribute mapvalue; color byattribute mapvalue #2 palette grayscale
marker fromMesh #1.1 edgeRadius 0.1              # markers+links copying a mesh (sticks that render unlike lines)
marker #5 position #1 color white                # centre of the bounding box of the map's contour surface (not its centre of mass)
cofr #2:3; view #2:3                             # rotate about / zoom to a marker
```
Typical cryo-ET workflow: contour, `surface dust`, `marker connected`, inspect with `measure blob`,
`measure length`/`distance` between the blob centres, `save blobs.cmm`. Headless note: maps opened from
files have their contour surface computed (checked in 1.11.1 `--nogui`), but maps computed in the session
(`molmap`, `volume`/`vop` operations) may have no triangles until a frame is drawn: `marker connected`
then fails with "Array argument has non-numeric values", `measure blob` with a `NoneType` error and
`marker fromMesh` silently makes an empty set. Run this (`python` tool) before those commands:
```python
from chimerax.map import Volume
for v in session.models.list(type=Volume): v.update_drawings()
result = {v.id_string: [len(s.vertices) if s.vertices is not None else 0 for s in v.surfaces] for v in session.models.list(type=Volume)}
```
A 0 in `result` means that map still has no surface (contour it with `volume #N level L`, rerun this).

## 7. Verify
- `run` `output`: "Total length of N bonds = …", "Distance between … : 10.541Å", "Found N connected
  surface pieces", "Wrote 1 marker sets containing 4 markers", "Opened 1 marker sets containing …".
- `scene` lists each set as type `MarkerSet` with atom count = marker count; a grouping model after
  opening a multi-set file has `MarkerSet` children. `model_info("#2")` → type, atom/residue counts, bounds.
- `measure("distance", "#2:1", "#2:3")`, `measure("center", "#2")`, `measure("count", "#2")` work
  because markers are atoms (each distance spec must match exactly one marker).
- `residue_table("#2")` → one row per marker (name `mark`, chain `M`); `selection_info` after `select #2:1`.
- `render`/`layout by="model"` → the set's colour in `palette`, its screen share; `compare_renders`
  before/after `marker change` or `marker delete` proves the edit; `getcrd #2` for exact positions.

## Pitfalls
- `marker #2 …` adds to an existing set #2 or creates it; deleting markers leaves gaps in numbering (the
  next marker gets the highest number + 1).
- `marker segment` needs the keywords `position … toPosition …`; the bare `x,y,z to x,y,z` form shown in
  the docs' example is rejected ("Expected a keyword").
- A spec used as a point (`position #1:LIG`) is a bounding-box centre; for a centre of mass use
  `measure center … mark true`.
- `marker link` needs both markers in the same set; links to atoms are not possible (use `distance`).
- Each `distance` endpoint must be a single marker (`#2:3`, not `#2`).
- Segment labels and `label` text are lost in .cmm (save a `.cxs` session as well); colour/radius survive.
- Default radius 0.5 Å is invisible next to a map: use `radius 2-5` for cryo-ET scale, `size #2 atomRadius r` later.
- `coordinateSystem` affects only the input x,y,z; markers do not follow the reference model afterwards.
- `marker connected` skips pieces hidden by `surface dust`/`surface zone`/`volume zone` — intended, but
  check "Found N connected surface pieces" against what you expect.
- `mousemode "mark …"` modes need the GUI and the Marker Placement tool's current set; from the MCP use
  `marker … position` with coordinates from `measure center`, `getcrd` or `measure mapvalues`.

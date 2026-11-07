---
name: cgo-and-pseudoatoms
title: Drawing helpers - pseudoatoms, CGO shapes, ramps
app: pymol
description: Pseudoatoms (centroids, free-floating points and text, distances to points, callouts), CGO objects built in Python (arrows, cylinders, spheres, lines, transparency, states), proximity colour ramps and their legend bar, grouping/hiding/removing helpers, ray-tracing them in figures
tags: pseudoatom, cgo, arrow, cylinder, sphere, ramp, centroid, annotation, callout, helpers
---
Use when a figure needs geometry that is not an atom: a point at a centroid, a distance to a point, an arrow for
a movement/axis, a sphere or cylinder marking a region, text floating in space, or colour by distance to something.
Label styling and `distance` modes: `labels-and-measurements`; `ramp_new` on maps: `surfaces-and-electrostatics` /
`maps-and-density`; ray settings: `publication-rendering`. PyMOL 3.1.5. Names: `prot` (protein), `lig` (ligand).

## 1. Pseudoatoms (fake atoms in their own object)
```pml
pseudoatom cen_lig, lig
pseudoatom cen_domA, prot and chain A and resi 1-120
pseudoatom note, pos=[12.5, 3.0, -8.2], label="active site", color=red
pseudoatom blob, prot and resi 1-60, mode=extent
pseudoatom marks, prot and resi 10, name=PS1, resi=1
pseudoatom marks, prot and resi 90, name=PS2, resi=2
show spheres, cen_lig or marks or blob
set sphere_scale, 0.4, cen_lig
set sphere_transparency, 0.6, blob
color magenta, cen_lig
label cen_lig, "ligand centroid"
```
- Position = arithmetic mean of the selection's atoms, or `pos=[x, y, z]`. `mode` sets the atom's vdw radius:
  `rms` (default; RMS distance of the atoms from the centre), `extent` (max distance - `show spheres` gives a
  translucent ball enclosing the selection), `unit` (0.5 A); or pass `vdw=1.2` explicitly.
- Repeating `pseudoatom obj, ...` with different `name=`/`resi=` adds points to the same object; address them as
  `marks and name PS2`. Always use a NEW object name: `pseudoatom prot, ...` inserts the fake atom into the protein.
- Pseudoatoms are HETATM `PSD` in chain `P`, segi `PSDO` (excluded by `polymer`, matched by `hetatm`), saved in
  `.pse` and by `save x.pdb, note`. `origin`, `center`, `x`, `y`, `z`, `all` are reserved names: PyMOL appends
  an underscore (`origin_`) and warns.
- Mass-weighted centre: `centerofmass lig` prints it; in Python `cmd.pseudoatom("com", pos=cmd.centerofmass("lig"))`.
- Multi-state objects: `state=N` samples state N and stores the point in state N of the pseudoatom object;
  the default `state=0` samples the CURRENT state and stores into that state number (frame 3 -> state 3,
  states 1-2 empty); `state=-1` samples every state at once (one point per state) - `pseudoatom traj_cen, prot,
  state=-1` gives a per-state centroid trail in one call.

Distances/labels to pseudoatoms work like with any atom (dash and label styling: `labels-and-measurements`):
```pml
distance d_lig_zn, cen_lig, prot and resn ZN
distance d_domains, cen_domA, cen_domB
set label_size, 24, note
set label_connector, 1, note
callout tag1, "Catalytic Asp", prot and resi 25 and name CG, [0.5, 0.7]
```
- `distance name, selA, selB, mode=4` measures centroid-to-centroid WITHOUT creating pseudoatoms; use pseudoatoms
  when the point must be visible, reused, or placed at `pos=`.
- `callout name, text, anchor, screen` = screen-stabilised text with a leader line; `screen` is `[-1..1, -1..1]`
  (lower-left to upper-right) or `auto`; omit the anchor selection for text without an arrow. Callouts are
  label-bearing pseudoatom objects (type `molecule`): style them with `label_*` settings on `tag1`.

## 2. CGO objects (shapes from Python, `python` tool)
A CGO is a flat list of floats: primitive constant followed by its numbers (`from pymol import cgo`); load it with
`cmd.load_cgo(list, name, state)`. Colours are 0-1 floats (`cmd.get_color_tuple("marine")` converts a name).
- `cgo.SPHERE, x, y, z, radius`
- `cgo.CYLINDER, x1, y1, z1, x2, y2, z2, radius, r1, g1, b1, r2, g2, b2` (colour per end)
- `cgo.CONE, x1, y1, z1, x2, y2, z2, radius1, radius2, r1, g1, b1, r2, g2, b2, cap1, cap2` (radius2 = 0 -> tip)
- `cgo.COLOR, r, g, b` applies to following SPHERE/VERTEX; `cgo.ALPHA, a` (0 transparent .. 1) likewise
- `cgo.BEGIN, cgo.LINES, cgo.VERTEX, x, y, z, ..., cgo.END` (also `LINE_STRIP`, `TRIANGLES`); an optional
  `cgo.LINEWIDTH, w` before BEGIN pins the width (see the line-width note below)
```python
from pymol import cgo
def arrow(name, start, end, radius=0.3, color=(0.9, 0.2, 0.2), head=1.5, state=1):
    """Shaft (cylinder) + head (cone) from start to end; coordinates in Angstrom, colour 0-1 floats."""
    d = [e - s for s, e in zip(start, end)]
    L = sum(c * c for c in d) ** 0.5
    head = min(head, 0.5 * L)
    base = [e - c / L * head for e, c in zip(end, d)]          # where the cone starts
    r, g, b = color
    obj = [cgo.CYLINDER, *start, *base, radius, r, g, b, r, g, b,
           cgo.CONE, *base, *end, radius * 2.2, 0.0, r, g, b, r, g, b, 1.0, 0.0]
    cmd.load_cgo(obj, name, state)
    return L
p1 = cmd.centerofmass("prot and resi 1-5")
p2 = cmd.centerofmass("prot and resi 15-20")
result = {"length": round(arrow("vec", p1, p2), 2), "type": cmd.get_type("vec")}
```
```python
from pymol import cgo
p1 = cmd.centerofmass("lig"); p2 = cmd.centerofmass("prot and resi 1")
obj = [cgo.COLOR, *cmd.get_color_tuple("marine"), cgo.SPHERE, *p1, 1.5,
       cgo.ALPHA, 0.5, cgo.COLOR, 1.0, 0.8, 0.0, cgo.CYLINDER, *p1, *p2, 0.4, 1.0, 0.8, 0.0, 1.0, 0.8, 0.0,
       cgo.BEGIN, cgo.LINES, cgo.COLOR, 0.0, 0.0, 0.0, cgo.VERTEX, *p1, cgo.VERTEX, 0.0, 0.0, 0.0, cgo.END]
cmd.load_cgo(obj, "shapes", 1)
result = {"extent": cmd.get_extent("shapes"), "states": cmd.count_states("shapes")}
```
Then style with commands (per object):
```pml
set cgo_transparency, 0.5, shapes
set cgo_line_width, 4, shapes
set cgo_line_radius, 0.1, shapes
hide cgo, shapes
show cgo, shapes
zoom vec, 5
```
- `load_cgo` to an EXISTING name with the default state APPENDS a new state (the old shape stays). Pass `state=1`
  to overwrite, or `delete name` first. Use states 1, 2, ... deliberately for a shape that changes per frame.
- `color green, shapes` only affects primitives that have NO `COLOR` entry (a list without any COLOR op is drawn
  in the object colour, default white); once colours are in the list, rebuild and reload with `state=1`.
- LINES ray-trace as tubes whose thickness follows a `cgo.LINEWIDTH` op in the list (it overrides the setting) or
  else the `cgo_line_width` setting (width 1 can vanish in `ray` - use >= 3); a positive `cgo_line_radius`
  (Angstrom, per object, no rebuild needed) gives a size-stable tube; for a guaranteed bar use a CYLINDER.
  Spheres, cylinders and cones ray-trace with full shading; `ALPHA` and `cgo_transparency` both work in `ray`.
- Text in 3D: `from pymol.vfont import plain; t = []; cgo.cyl_text(t, plain, [x, y, z], "text", 0.2, color=[0, 0, 0]);
  cmd.load_cgo(t, "txt")` - fixed orientation; a labelled pseudoatom (camera-facing, font settings) is usually better.
- PyMOL 3.x also has `pymol.cgobuilder` (keyword arguments only - the first positional slot is internal):
  `from pymol.cgobuilder import CGOBuilder, Sphere, Cylinder, Cone, Point, Color; b = CGOBuilder();
  b.add(Sphere(center=Point(x, y, z), radius=1.5, color=Color(1, 0, 0))); b.load("built")` (`add` returns a token,
  not the builder, so no chaining; `Cylinder(point1=, point2=, radius=, color1=, color2=)`, `Cone(tip=, base_center=,
  radius=, color=)`). Same result as the flat list, more verbose.

## 3. Proximity ramps (colour by distance to an object)
```pml
create lig_obj, lig
ramp_new prox, lig_obj, [0, 4, 8], [red, white, blue]
color prox, prot
set surface_color, prox, prot
ramp_update prox, range=[0, 3, 6], color=[blue, white, red]
disable prox
```
- The ramp target must be an OBJECT (make one with `create`; a pseudoatom object works too), not a selection
  (`ligsel not found`). Range in Angstrom; colours as names, `[r, g, b]` lists or a palette name (`rainbow`,
  `afmhot`, `grayscale`, `hot`, `ocean`, `traditional`) with a two-value range. RGB lists must be ALL floats
  (`[1.0, 0.0, 0.0]`): an integer anywhere (`[1, 0, 0]`, `[1.0, 0, 0]`) crashes PyMOL 3.1.5 outright.
- The colour is dynamic (atoms get a negative colour index, -10 for the first ramp, -11 for the next): moving
  the target re-colours. `color grey80, prot` reverts.
- An ENABLED ramp draws its colour-bar legend across the bottom of the viewport, also in ray-traced PNGs:
  `disable prox` removes the bar and keeps the atom colours. `alignto` loops over EVERY object and raises
  `Invalid selection name` on the first ramp, CGO or measurement it meets - align the molecules with `align`.

## 4. Organise, hide, remove
```pml
group helpers, cen_lig note vec shapes prox
disable helpers
enable helpers
hide labels, note
remove marks and name PS2
delete vec
delete cen_*
delete helpers
```
- `delete helpers` deletes the group AND every member; `delete cen_*` = wildcard; `remove` strips single pseudoatoms
  from an object; `disable` keeps it for later. A measurement keeps drawing its dashes and label after the
  pseudoatom it was measured to is deleted (the coordinates are stored in the measurement) - delete it too.

## 5. In figures
- Arrows for a protein-sized scene: shaft radius 0.2-0.4 A, cone ~2.2x shaft, head 1.5-2.5 A; `set ray_shadow, 0`
  stops arrows shadowing the cartoon; a translucent "domain blob" = `mode=extent` pseudoatom sphere or CGO sphere.
- Use helper colours absent from the structure palette (`red`/`black` on grey) so `render`/`compare_renders`
  isolate them; keep the ramp bar disabled unless a legend is wanted. Helpers are saved in `.pse`, ray-trace with
  `png ..., ray=1`, and stay in world coordinates when the protein is reloaded or moved by `align` - recompute.

## Verify
- `scene` -> objects of `type` `molecule` (pseudoatom objects: 1-n atoms), `cgo`, `ramp`, `measurement`, `group`,
  each with `extent`/`center`/`size` (a ramp reports a dummy +-0.5 box) - a CGO in the wrong place shows up
  immediately; `object_info("vec")` for one object. Members of a DISABLED group still report `enabled: true`
  (PyMOL keeps their own flag) - check the group's entry.
- `layout(by="object")` lists `cgo` objects as items (ramps are not drawable): is the arrow on screen, occluded?
  `layout(by="items", items=["vec", "lig"])` for arrow-vs-ligand placement.
- `render(width=1200, height=900)` + `compare_renders()` before/after loading: the changed region sits at the
  shape and `palette` lists the helper colour.
- `measure(kind="center", selection1="lig")` gives a centre for `pos=`; `measure(kind="distance",
  selection1="cen_lig", selection2="cen_domA")` reports a centroid distance without a dash object; `python`:
  `result = {"cen": cmd.get_coords("cen_lig").tolist(), "ext": cmd.get_extent("vec"), "states": cmd.count_states("vec")}`.

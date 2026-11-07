---
name: maps-and-density
title: Maps and electron density
app: pymol
description: Load or fetch maps (ccp4/mrc/dx/xplor, PDBe 2fofc/fofc), isomesh/isosurface/isodot with carve, sigma levels, difference-map green/red meshes, isolevel, map_double/map_trim, volume rendering, colouring by map values, map statistics
tags: map, density, isomesh, isosurface, carve, 2fofc, fofc, volume, cryo-em, ccp4
---
Example: molecule `prot`, ligand selection `lig`, map objects `map2fofc` / `mapfofc`.

## Load or fetch
```pml
fetch 6lu7, prot, async=0
fetch 6lu7, map2fofc, type=2fofc, async=0
fetch 6lu7, mapfofc, type=fofc, async=0
select lig, prot and organic
```
- `type=2fofc`/`fofc` downloads PDBe maps (only for entries with deposited structure factors; old entries
  such as 1hpv fail with "unable to load"). `set fetch_path, /dir` chooses where files go.
- Local files: `load map.ccp4, mapname` (also `.mrc`, `.map`, `.dx`, `.xplor`, `.brix`, `.omap`; `load x.mtz`
  needs the mtz loader of the incentive build - not verified here). Maps are objects of type `map`.
- `normalize_ccp4_maps` (default on) scales CCP4/MRC maps so levels are in sigma units. Set
  `set normalize_ccp4_maps, 0` BEFORE loading to keep absolute values (cryo-EM maps with known thresholds).
- Synthetic density from a model (figures, low-res look): `map_new sim, gaussian, 0.5, prot, 4` then isomesh it.

## Contour
```pml
isomesh mesh_lig, map2fofc, 1.0, lig, carve=1.8
isomesh fofc_pos, mapfofc, 3.0, lig, carve=2.0
isomesh fofc_neg, mapfofc, -3.0, lig, carve=2.0
color marine, mesh_lig
color green, fofc_pos
color red, fofc_neg
set mesh_width, 0.6
isolevel mesh_lig, 0.8
```
- `isomesh name, map, level, selection, buffer, state, carve`: `selection` + `carve=r` keeps density within
  r A of the atoms (1.6-2.0 for ligands); without `carve` the mesh covers the whole box (`buffer` pads it).
- `isosurface name, map, level, selection, buffer, state, carve` = solid surface (same arguments);
  `set transparency, 0.5, name` for see-through; `isodot` = dots.
- Convention: 2Fo-Fc at 1.0 sigma (blue/marine), Fo-Fc at +3.0 (green) and -3.0 (red). `isolevel name, level`
  changes a contour in place (fast way to tune). Use the same level for all figures of one paper.
- Mesh colour: `color x, meshname` (or `set mesh_color, x, meshname`); `mesh_width` (1.0 default) is in pixels
  for OpenGL; `set mesh_radius, 0.02` sets a ray-traced tube radius.
- Auto-recarve when the camera/selection moves: `set mesh_carve_selection, lig, mesh_lig` +
  `set mesh_carve_cutoff, 2, mesh_lig` (object-level settings).
- Symmetry mates of the map are used automatically (`map_auto_expand_sym` on); the message "not all symmetry
  expanded points covered by map" is harmless.
- Whole-protein density at low level: `isomesh mesh_all, map2fofc, 1.0, prot, carve=2.0` (slow for big maps).

## Map operations
```pml
map_double map2fofc
map_trim map2fofc, lig, 5
```
- `map_double` doubles the grid resolution (smoother mesh, 8x memory); `map_trim map, sel, buffer` crops the
  map around a selection (smaller sessions). Save a cropped map with `save lig_map.ccp4, map2fofc`.
- Volume rendering (cryo-EM style): `volume vol, map2fofc` then
  `volume_color vol, 0.5 blue 0.05 1.0 blue 0.2 2.0 yellow 0.4` (level colour alpha triplets), or a named ramp:
  `volume_ramp_new ramp1, 0.5 blue 0.1 1.5 red 0.3` + `volume vol, map2fofc, ramp1`. Volumes do not ray trace
  unless `set ray_volume, 1`.
- Colour a surface by map value: `ramp_new rmp, map2fofc, [0, 1, 2], [blue, white, red]` then
  `set surface_color, rmp, prot` (same trick as electrostatics). `slice_new sl, map2fofc` draws a 2D slice.

## Map statistics (sigma, min/max) via `python`
```python
import numpy as np
f = cmd.get_volume_field("map2fofc")
result = {"shape": list(f.shape), "mean": float(f.mean()), "sigma": float(f.std()),
          "min": float(f.min()), "max": float(f.max()), "extent": cmd.get_extent("map2fofc")}
```
After normalisation `mean` ~ 0 and `sigma` ~ 1, so contour levels are sigma. For un-normalised cryo-EM maps
choose the level from this (e.g. `mean + 3*sigma`) and pass it to `isosurface`.

## Pitfalls
- Maps do not move with `align`: align the model to the map's structure, not the other way round, or load the
  map after superposing the reference and then align others onto it.
- Meshes exist in map space; after `fetch ..., type=2fofc` the map matches the deposited model coordinates only.
- A mesh with no visible density: level too high (check `sigma`), wrong map, or `carve` too tight. Try
  `isolevel name, 0.5` to see whether anything appears.
- Big maps with `isomesh` over `all` are slow; contour around a selection.
- Re-running `isomesh`/`isosurface` with an existing name overwrites that object in place (verified: still one
  state), so re-contouring is safe; for a level change alone `isolevel` is faster.

## Verify
- `scene` -> objects of type `map`, `mesh`, `surface`, `volume`, `slice`, `ramp`; `object_info("mesh_lig")`
  shows `mesh_color`/`mesh_width` overrides.
- `layout(by="object")` -> the mesh item's `share_of_frame` and bbox (it should sit on the ligand's bbox).
- `render()` -> `palette` contains the mesh colour (marine/green/red); `compare_renders()` after `isolevel`
  shows a changed region.

---
name: electron-density-validation
title: Electron density inspection and model validation
app: pymol
description: Judge whether a ligand, water, loop or side chain is supported by its X-ray maps - fetch 2mFo-DFc/mFo-DFc, carved meshes at defensible sigma levels, difference-density colouring, level sweeps, residue-by-residue checks, sigma vs absolute units, map_info/set_isolevel tools, occupancy/B-factor adjuncts
tags: density, validation, 2fofc, fofc, difference map, ligand, sigma, isomesh, isolevel, map_info
---
When to use: "is this ligand/water/loop really there?", "show me the density for X", difference-density figures,
checking a deposited model before building on it. Loading, map algebra, volume rendering and map statistics
from `get_volume_field` are in `maps-and-density`; picking the ligand and pocket is in `ligand-binding-site`.
Example: `prot` = 6lu7 (SARS-CoV-2 Mpro), `lig` = its peptidic N3 inhibitor, which is chain C (not `organic`).

## 1. Get the maps and check what you have
```pml
set fetch_path, /path/to/a/writable/dir
fetch 6lu7, prot, async=0
fetch 6lu7, map2fofc, type=2fofc, async=0
fetch 6lu7, mapfofc, type=fofc, async=0
select lig, prot and chain C
select pocket, byres (prot and polymer within 4.5 of lig)
```
- `type=2fofc` / `fofc` download PDBe's 2mFo-DFc and mFo-DFc CCP4 maps (`.../pdbe/coordinates/files/<code>.ccp4`
  and `<code>_diff.ccp4`); X-ray entries with deposited structure factors only. Without a name the objects are
  called `6lu7_2fofc` / `6lu7_fofc`. Cryo-EM: `fetch emd-NNNN` loads the EMDB map (absolute levels, section 5).
- Call the `map_info()` tool: for every map `min/max/mean/sd` and `extent`, for every mesh/surface its `level`.
  With the default normalisation mean = 0 and sd = 1, so every level you pass is in sigma. `min`/`max` are the
  limits of PyMOL's automatic histogram range, clamped to mean +- 5 sd, so `max` 5.0 (and `min` -5.0 on mFo-DFc)
  is normal and does not mean the map is clipped (6lu7 mFo-DFc really spans -11.1..5.8; the load log prints the
  true range). The map `extent` usually sits at the cell origin, far from the model
  (6lu7: map x 0..76 A, model x -51..0): density still appears on the atoms because `map_auto_expand_sym`
  applies the crystal symmetry while contouring. Do not try to move the map or the model to "fix" this.

## 2. Inspection view
```pml
hide everything
show sticks, lig
show sticks, pocket and not name N+C+O
show cartoon, prot and polymer
set cartoon_transparency, 0.75
util.cbaw prot and polymer
util.cbag lig
isomesh d2fo, map2fofc, 1.0, lig, carve=1.8
isomesh dfo, mapfofc, 3.0, lig, carve=2.0
set mesh_negative_visible, 1, dfo
set mesh_negative_color, red, dfo
color marine, d2fo
color green, dfo
set mesh_width, 1.2
bg_color white
orient lig
zoom lig, 3
clip slab, 20
```
- One difference object is enough: `mesh_negative_visible` draws the -level contour of the same object in
  `mesh_negative_color`, and `isolevel dfo, 2.5` moves both contours. Use two objects (`isomesh dfo_neg,
  mapfofc, -3.0, lig, carve=2.0`) only when positive and negative must be toggled separately.
- `hide everything` hides mesh objects too; after clearing a scene run `show mesh, d2fo` (and `dfo`).
- Carve 1.6-1.8 A for ligands and side chains, 2.0 for difference density (blobs sit beside the atoms); without
  `carve` the whole map box is drawn. Re-running `isomesh` with the same name re-contours in place.
- "Is the pose right?" needs the pocket too: `isomesh d2fo, map2fofc, 1.0, lig or pocket, carve=1.8`.

## 3. Read it: what good and bad look like
- Good: the 1 sigma 2mFo-DFc mesh wraps every ligand atom as one continuous tube (ring holes visible below
  ~2 A resolution) and no difference peak beyond +-3 sigma lies within 2 A of the ligand.
- Missing 2mFo-DFc density for part of the ligand that is still missing at 0.7 sigma: that part is disordered or
  wrongly modelled (6lu7: the N3 core is enclosed at 1 sigma, its benzyl ester is bare and sits in -3 sigma density).
- Green (+) blob with no atom = unmodelled atom, water or alternate conformation; red (-) over atoms = atoms in
  the wrong place or occupancy too high; a green/red pair = the atoms should shift towards the green.
- Waters: `select w, (prot and resn HOH) within 4 of lig` (6lu7 has none that close to N3), `isomesh dw, map2fofc,
  1.0, w, carve=1.4`; a water is credible only with 2mFo-DFc density and a partner within 3.3 A
  (`distance w_hb, w, prot and not resn HOH, 3.3, mode=2`).
- The level sweep is the test, not a single picture: `set_isolevel("d2fo", 0.7)`, `render()`,
  `set_isolevel("d2fo", 1.5)`, `render()`, `compare_renders()`. Density that survives 1.5 sigma is solid; density
  seen only at 0.7 sigma is marginal. Report mFo-DFc at +-3.0, look for weaker signal at +-2.5, never lower.
- Resolution matters: worse than ~3 A contour 2mFo-DFc at 0.8, expect side chains to merge, and say so.

## 4. Residue-by-residue sweep (loops, side chains, alternate conformations)
```python
sel = "prot and chain A and resi 140-145"
res = []
cmd.iterate(f"({sel}) and name CA", "res.append((chain, resi, resn))", space={"res": res})
for ch, ri, rn in res:
    cmd.isomesh(f"d_{ch}{ri}", "map2fofc", 1.0, f"prot and chain {ch} and resi {ri}", carve=1.6)
    cmd.color("marine", f"d_{ch}{ri}")
cmd.group("dens_res", "d_*")
result = [f"{ch}{ri}{rn}" for ch, ri, rn in res]
```
Then `disable d_*`, `enable d_A141`, `orient prot and chain A and resi 141`, `render()` one residue at a time. To
test a residue for emptiness: `render()` with its mesh enabled, `disable d_A141`, `render()`, `compare_renders()`;
a `changed_fraction` of ~0 means nothing was drawn, i.e. no density at 1 sigma. `layout` cannot do this job
(section 6). `delete dens_res` removes all of them afterwards.
Occupancy and B-factors are the model's own statement about the same density (list names must not be `q`/`b`):
```python
import statistics
_q, _b, _alt, _bp = [], [], set(), []
cmd.iterate("lig", "_q.append(q); _b.append(b); _alt.add(alt)", space={"_q": _q, "_b": _b, "_alt": _alt})
cmd.iterate("pocket", "_bp.append(b)", space={"_bp": _bp})
result = {"lig_occupancy_min": min(_q), "lig_B_mean": round(statistics.mean(_b), 1),
          "pocket_B_mean": round(statistics.mean(_bp), 1), "altlocs": sorted(_alt)}
```
Ligand B above ~1.5x the pocket B, or occupancy < 1 with no difference density, means partial occupancy or a
doubtful ligand. `residue_table(selection="lig or pocket")` gives per-residue B (`b_mean`) for the report.

## 5. Sigma vs absolute levels
- `normalize_ccp4_maps` (default on) rescales each CCP4/MRC map to mean 0, sd 1 at load time, so
  `isomesh ..., 1.0` is 1 sigma. That sigma is the rmsd of the grid PyMOL loaded (the PDBe box or your file),
  not of the whole unit cell, so levels can differ slightly from Coot/CCP4; keep one convention per project.
- Absolute units: `set normalize_ccp4_maps, 0` BEFORE `load`/`fetch`; levels are then the file's units (6lu7
  2mFo-DFc: sd 0.256 e/A^3, so 1 sigma = 0.256). Convert with `map_info()`: level_abs = mean + n * sd. Needed
  when a paper or EMDB entry quotes an absolute threshold (cryo-EM: contour at the recommended level).
- Both copies may coexist (toggle the setting between loads); `set_isolevel` changes the number, never the units.

## 6. Pitfalls
- `fetch ..., type=2fofc` fails ("unable to load") for entries without structure factors; offer `fetch emd-NNNN`
  or a local map (`load x.ccp4, map2fofc`) instead.
- Maps do not follow `align`/`super`: superpose other models onto the model that owns the map, never move it.
- `color ramp, lig` with a map ramp ignores map symmetry (atoms outside the map box read 0 and come out at the
  low end): do not use it as a "density fit" colouring for PDBe maps.
- `get_extent` of a mesh returns the carve box, not the drawn geometry, so an empty mesh has the same extent;
  judge emptiness with `render`/`compare_renders`, never with `get_extent`.
- `layout` fails while any mesh object is enabled: its ID pass colours each item through a selection, which PyMOL
  rejects for non-molecular objects (`Invalid selection name`). `disable` the meshes before calling `layout` and
  judge meshes with `render`/`compare_renders`.
- PyMOL computes no RSCC/RSR/RSRZ/EDIA; for numbers cite the wwPDB validation report or Coot/phenix and present
  PyMOL output as visual inspection.
- Meshes are computed at the first draw, so the first `render()` after many `isomesh` calls is slower.

## 7. Verify with the tools
- `map_info()` -> both maps listed, `sd` ~ 1 (or your absolute sd), each mesh with the intended `level`.
- `scene` -> `d2fo`/`dfo` of type `mesh`, enabled; `settings(names=["mesh_negative_visible", "mesh_negative_color"],
  object="dfo")` -> `1` and `red` (`object_info` lists only `mesh_color`/`mesh_width`/`transparency` overrides for
  meshes, not the negative-contour settings).
- `render()` -> `palette` names a marine-like blue, green and red, `clipped_edges` is empty and the `bbox` covers the
  ligand region; do not call `layout` while the meshes are enabled (section 6).
- `compare_renders()` after each `set_isolevel` -> the changed region is where the mesh is; identical renders mean
  the mesh is not displayed (`show mesh, d2fo`).

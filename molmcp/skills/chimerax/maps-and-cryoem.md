---
name: maps-and-cryoem
title: Maps and cryo-EM
app: chimerax
description: Open density maps (files, EMDB, EDS), set contour level/style/step/colour, zone a map around atoms, fit models into maps (fitmap, global search), simulate maps (molmap), filter/resample/subtract maps, and report map statistics and correlations
tags: cryo-em, map, volume, fitmap, molmap, emdb, density, mapstats, correlation
---
Use for "open the EM map", "contour at 3σ", "fit the model into the density", "show density only
around the ligand", "what level / resolution". Syntax verified against the ChimeraX 1.11 docs.

## 1. Open and inspect
```
open ~/maps/emd_3087.map                   # .mrc .map .ccp4 .cmap .brix .dsn6 .situs .hdf .dx …
open emdb:3087                             # or: open 3087 from emdb (depositor-recommended level)
open 3087 from emdb_fits                   # map plus the fitted PDB model(s)
open 1abc from eds                         # 2Fo-Fc map for a PDB entry (edsdiff = Fo-Fc)
volume settings #2                         # all display settings to the log
measure mapstats #2                        # min, max, mean, SD, RMS
info #2                                    # size, voxel size, value range, levels
```
`scene` → a Volume model shows `grid_size`, `voxel_size`, `origin`, `isosurfaces` (level, colour,
mesh); numbers come from `measure mapstats`. Maps above 256 Mvoxels open as a single plane; large maps get `step 2` automatically.

## 2. Display
```
volume #2 level 0.05                          # absolute contour level (surface style)
volume #2 sdLevel 3                           # 3 SD above the mean; `rmsLevel 1.5` = 1.5 × RMS
volume #2 encloseVolume 50000                 # level that encloses 50 000 Å³
volume #2 style mesh                          # surface | mesh | image (image = solid rendering)
volume #2 step 1                              # full resolution (large maps default to 2)
volume #2 color #4682b4 transparency 0.5      # transparency is a 0–1 fraction here
volume #2 level 0.03 color cornflowerblue level 0.08 color gold      # two contours
volume #2 region all; volume #2 region 20,20,20,80,80,80             # crop by grid indices
volume #2 planes z,40; volume #2 orthoplanes xyz positionPlanes 50,50,50
volume #2 showOutlineBox true; volume #2 hide; volume #2 show; vol all hide
volume #2 surfaceSmoothing true smoothingIterations 2; volume #2 squareMesh true
surface dust #2 size 8                        # hide small blobs; surface undust #2
```

## 3. Zone the map around atoms
```
volume zone #2 nearAtoms #1 range 3             # show density within 3 Å of the model
volume zone #2 nearAtoms ligand range 2.5
volume unzone #2                                # back to the full map
volume zone #2 nearAtoms #1/A range 3 newMap true minimalBounds true   # masked copy as a new map
zone :LIG                                       # residue zone: atoms within 5 Å + map within 8 Å (surfaceDistance)
```

## 4. Fit atoms or maps into a map
```
fitmap #1 inMap #2                              # local rigid-body optimisation from the current position
fitmap #1/A inMap #2 moveWholeMolecules false   # move only chain A
fitmap #1 inMap #2 resolution 5 metric correlation      # simulate a 5 Å map from #1, map-in-map fit
fitmap #3 inMap #2 metric cam                   # map-in-map, correlation about the mean
fitmap #1 inMap #2 search 100 placement sr radius 30    # global search: 100 random starts → Fit List
fitmap #1 inMap #2 resolution 6 search 50 listFits true logFits ~/fits.csv
fitmap #1,3 inMap #2 sequence 10 resolution 6   # sequential fitting of several models
fitmap #1 inMap #2 symmetric true resolution 6  # use the map's symmetry (volume symmetry / measure symmetry)
```
Log output: correlation, average map value, steps, shift, rotation. Place the model roughly first
(`move`, `turn … models #1`, `view position #1 sameAsModels #3`); re-run `fitmap` to converge.
```
measure correlation #3 inMap #2                 # map–map correlation (about zero and about the mean)
measure mapvalues #2 atoms #1 attribute mapvalue; color byattribute mapvalue #1 palette grayscale
measure symmetry #2; volume #2 symmetry C3 axis z center #2      # detect / assign symmetry
```

## 5. Simulated and derived maps
```
molmap #1 5                                     # 5 Å Gaussian map from atoms (new model)
molmap #1 8 gridSpacing 1 symmetry C3 axis z center #1
volume gaussian #2 sDev 1.5                     # smooth; `invert true` sharpens; `bfactor B` alternative
volume resample #3 onGrid #2                    # put map #3 on #2's grid (needed to save a fitted map)
volume subtract #2 #3 minRms true               # difference map
volume add #2,3 onGrid #2; volume copy #2
```

## 6. Save
```
save ~/zone.mrc #4                              # the models spec may follow the file name
save ~/map.mrc #2 region all step 1 valueType float32
save ~/fitted.cif #1 relModel #2                # atoms relative to the map's original frame
save ~/session.cxs includeMaps true             # embed map data in the session
```
Map files store no rotation: after fitting a map, `volume resample` it onto the reference grid and
save the result; after fitting atoms, save the atoms with `relModel`.

## 7. Verify
- `scene`/`model_info("#2")` → `isosurfaces[0].level`, `display`; SD/RMS via `measure mapstats` or the snippet below.
- `fitmap` `output` → correlation / average map value before vs after; `changes` reports the move.
- `render` → map colour in `palette`; `layout by="model"` lists the map surface and the atomic
  model; `occlusion=true` → how much of the model is covered by density.
```python
import numpy as np
from chimerax.map import Volume
v = [m for m in session.models.list(type=Volume) if m.id_string == "2"][0]
a = v.full_matrix()                         # full-resolution numpy array (z, y, x)
result = {"levels": [float(s.level) for s in v.surfaces], "mean": float(a.mean()), "sd": float(a.std()),
          "min": float(a.min()), "max": float(a.max()), "size": list(v.data.size), "step": list(v.data.step)}
```

## Pitfalls
- `volume … transparency` is 0–1; the `transparency` command (percent) also works on map surfaces.
- Levels change meaning after `volume gaussian`/`resample`/`subtract`; re-set with `sdLevel`.
- `fitmap` uses the currently displayed region of the reference map (cropping restricts the fit).
- Global `search` moves whole models and ignores `moveWholeMolecules false`.
- Downloads are cached in `~/Downloads/ChimeraX/EMDB`; `ignoreCache true` re-fetches.
- A map and a model from different sources overlap only if their origins agree — otherwise `fitmap`.

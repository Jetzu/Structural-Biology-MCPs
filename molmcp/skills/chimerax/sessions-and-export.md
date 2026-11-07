---
name: sessions-and-export
title: Opening, sessions and export
app: chimerax
description: Fetch structures, maps and predictions by identifier (PDB, PDBe, EMDB, AlphaFold, ESMFold, UniProt, PubChem), open local files and scripts, save/restore sessions (.cxs), export coordinates (pdb/mmCIF, selected or displayed only, relative to another model), 3D scenes (glb/stl/obj/x3d/vrml), images and maps
tags: open, fetch, session, save, export, pdb, mmcif, glb, stl, emdb, uniprot, close
---
Use for "open 1ABC", "load the map", "save the session", "export for Blender / 3D printing", "save
the aligned coordinates". Syntax verified against the ChimeraX 1.11 docs.

## 1. Fetch by identifier (`open source:id` or `open id from source`)
```
open 1abc                                    # RCSB PDB, mmCIF (default for 4-character ids)
open 1abc format pdb                         # PDB format instead (mmtf also possible)
open 1abc from pdbe; open 1abc from pdbj     # other wwPDB sites
open 1abc from rcsb_bio maxAssemblies 1      # biological assembly with real coordinates
open 1abc from redo                          # PDB-REDO re-refined coordinates
open 1abc from eds; open 1abc from edsdiff   # 2Fo-Fc / Fo-Fc density from PDBe
open emdb:3087; open 3087 from emdb          # EMDB map; `3087 from emdb_fits` adds fitted models
open P29474 from alphafold                   # AlphaFold DB model (= alphafold fetch P29474)
open P29474 from alphafold_pae structure #2  # its PAE matrix for model #2
open MGYP000542242899 from esmfold           # ESM Atlas model
open P29474 from uniprot                     # UniProt sequence in the Sequence Viewer (associates with open chains)
open 2244 from pubchem; open ATP from ccd    # small molecules: PubChem CID, PDB chemical component
open 1abc 2xyz 3def                          # several at once; `open 1abc ignoreCache true` re-downloads
open 1abc name "wild type" id #5             # choose name and model id
```
Downloads are cached in `~/Downloads/ChimeraX/`. No internet → the error appears in `error`.

## 2. Local files
```
open ~/data/model.pdb; open ~/data/model.cif; open ~/data/lig.sdf; open ~/data/lig.mol2
open ~/data/model_*.pdb                      # globbing
open ~/data/ensemble.pdb coordsets true      # multi-MODEL file as one trajectory model
open ~/md/traj.dcd structureModel #1         # trajectory coordinates onto an open topology
open ~/md/sys.psf coords ~/md/traj.dcd       # PSF topology + DCD
open ~/maps/map.mrc; open ~/maps/*.mrc vseries true
open ~/aln.fasta; open ~/aln.aln             # sequences / alignments (Sequence Viewer)
open ~/attrs.defattr                         # attribute assignments
open ~/script.cxc; open ~/script.py          # command script / Python script
runscript ~/script.py arg1 arg2
pwd; cd ~/project                            # relative paths resolve against pwd (on the ChimeraX machine)
```

## 3. Sessions
```
save ~/project/work.cxs                      # models, colours, labels, views, selections, named targets
save ~/project/work.cxs includeMaps true     # embed map data (otherwise file paths are stored)
save ~/project/work.cxs compress gzip        # smaller (default lz4)
open ~/project/work.cxs                      # replaces the current session (closes models)
open ~/project/work.cxs combine true         # merge into the current session
open ~/project/work.cxs resizeWindow false
close session                                # empty session; resets lighting, background, camera, clipping
```
Sessions are ChimeraX-only; a view named `session-start` is created on restore.

## 4. Coordinates
```
save ~/out/model.pdb #1                      # models spec may follow the file name
save ~/out/model.cif #1,2                    # mmCIF; several models in one file
save ~/out/site.pdb #1 selectedOnly true     # current selection only (select /A first for one chain)
save ~/out/shown.pdb #1 displayedOnly true   # displayed atoms only
save ~/out/aligned.pdb #2 relModel #1        # coordinates relative to model #1 (keeps the superposition)
save ~/out/traj.pdb #1 allCoordsets true     # all frames (multi-MODEL)
save ~/out/model.mol2 #1; save ~/out/model.pqr #1 pqr true
save ~/out/[NAME]_[ID].pdb                   # one file per model (name / id substitution)
save ~/out/attrs.defattr attrName bfactor models #1
save ~/out/aln.fasta alignment 1.A           # alignment from the Sequence Viewer
```
mmCIF extras: `bestGuess true` (sequence records for built/modified models), `computedSheets true`.

## 5. 3D scenes (what is displayed; clipping is ignored)
```
save ~/out/scene.glb                         # glTF binary: Blender, three.js, web; colours included
save ~/out/scene.glb #1.1 textureColors true # one surface with texture colours
save ~/out/scene.stl                         # 3D printing (no colours); .vrml / .wrl for colour printing
save ~/out/scene.obj; save ~/out/scene.x3d; save ~/out/scene.vtk
save ~/out/scene.glb size 10 center true     # scale the bounding box to 10 units at the origin
save ~/out/model.positions                   # model placements only (restore with open)
```
Shown representations are exported as triangles (cartoons, sticks, spheres, surfaces, map surfaces).

## 6. Images and maps
```
save ~/out/fig.png width 2400 height 1800 supersample 3 transparentBackground true
save ~/out/map.mrc #2; save ~/out/map%d.mrc models #2,3
save ~/out/zone.mrc #4 step 1 region all
```
Details: skills publication-rendering and maps-and-cryoem.

## 7. Housekeeping
```
close #2; close #1.1; close                  # models / sub-models / everything
rename #1 "apo form"; rename #2 id #1.2      # rename / renumber (grouping as sub-models)
split #1 chains; combine #1,2 modelId 5 name complex close false
delete solvent; delete H                     # atoms (irreversible)
```

## 8. Verify
- After `open`: `run` → `changes` lists added models; `scene` → ids, atom/residue/chain counts;
  `output` has the open summary (chains, missing residues, assemblies).
- After `save`: check the file from inside ChimeraX:
```python
import os
p = os.path.expanduser("~/out/model.pdb")
result = {"exists": os.path.exists(p), "bytes": os.path.getsize(p) if os.path.exists(p) else 0}
```
- Re-open a saved file as a new model and `rmsd #1@CA to #3@CA` to confirm `relModel` worked.

## Pitfalls
- `models` takes whole models: for one chain `select /A; save x.pdb #1 selectedOnly true`.
- `save` overwrites silently; paths (`~`, relative) resolve on the ChimeraX machine, not the client.
- `open session.cxs` closes the current models unless `combine true`.
- Coordinate files are written in scene coordinates: after `matchmaker`/`fitmap` the moved model is
  saved as moved (usually intended; `relModel` makes the frame explicit).
- Large maps in sessions: `includeMaps true` makes huge files; the default stores paths instead.

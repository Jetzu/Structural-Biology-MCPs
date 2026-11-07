---
name: surfaces-and-electrostatics
title: Surfaces, electrostatics and surface measurements
app: chimerax
description: Create molecular surfaces (SES or Gaussian, enclose, patches, zone, dust), colour them by Coulombic ESP, lipophilicity, map values or nearby atoms (color zone), and measure SASA, buried area, surface area and enclosed volume
tags: surface, coulombic, electrostatics, mlp, color zone, sasa, buriedarea, measure, interfaces
---
Use for "show the surface", "colour the surface by electrostatics", "which residues are buried",
"surface area of the pocket". Syntax verified against the ChimeraX 1.11 docs.

## 1. Create surfaces
```
surface #1                               # solvent-excluded surface (SES), one per biopolymer chain
surface #1 enclose #1                    # one envelope around the whole model
surface #1 include :HEM                  # include a het group in its chain's envelope
surface ligand                           # separate small surfaces for ligand residues
surface #1:10-30                         # show only those patches (within the chain's surface)
surface ligand @< 5 visiblePatches 1     # largest patch near the ligand only
surface #1 probeRadius 1.6 gridSpacing 0.4        # smoother / finer SES (defaults 1.4 / 0.5 Å)
surface #1 resolution 6 gridSpacing 1             # low-resolution Gaussian surface (no atom patches)
surface #1 color white transparency 40
surface style #1.1 mesh                   # solid | mesh | dot
surface hidePatches #1/B; ~surface #1/B; surface showPatches #1/B
surface close #1.1                        # delete the surface model (close #1.1 also works)
surface zone #1.1 nearAtoms ligand distance 6 maxComponents 1; surface unzone #1.1
surface dust #2 size 10                   # hide small blobs (maps); surface undust #2
surface cap false                         # no caps on clipped surfaces (default true)
```
Surfaces become sub-models (`#1.1`, `#1.2`, …; `scene` → `surfaces`). To change type or parameters
of an existing surface, `surface close` it first, otherwise old settings may persist.

## 2. Electrostatic potential (Coulombic, no input map needed)
```
coulombic #1                              # red −10 … white … blue +10 kcal/(mol·e), surfaces made as needed
coulombic protein surfaces #1.1           # charges from protein atoms only, colour an existing surface
coulombic #1 palette redblue range -8,8 offset 1.4
coulombic #1 hisScheme HIE                # HIS protonation when no hydrogens are present
coulombic #1 map true gspacing 1          # also open the ESP as a volume model (save / re-use)
```
Charges and hydrogens are assigned on an internal copy; non-standard residues trigger Antechamber
(slow). Remove solvent first: `delete solvent`. From an existing potential map (APBS .dx, .phi):
```
open pot.dx; color electrostatic #1.1 map #2 palette redblue range -10,10 offset 1.4
color sample #1.1 map #3 palette bluered range 0,1          # any map value on a surface
```

## 3. Lipophilicity
```
mlp #1                                    # dark cyan (hydrophilic) → white → dark goldenrod (lipophilic)
mlp #1 surfaces #1.1 palette lipophilicity range -20,20 transparency 30
```

## 4. Colour by nearby atoms and reset surface colours
```
color #1 bychain target a; color zone #1.1 near #1 distance 3        # surface takes atom colours
color zone #1.1 near ligand distance 4 farColor white sharpEdges true
color #1.1 fromatoms                      # per-atom patch colours (SES only)
color single #1.1                         # back to one colour (removes per-vertex colouring)
```
After `clip`, caps are coloured with `color zone` or `color electrostatic … offset 0`.

## 5. Measurements (numbers go to the log → read `output` of `run`)
```
measure sasa #1 & protein                                 # total SAS area; sets atom/residue attribute `area`
measure sasa #1/A & protein sum :phe,tyr,trp              # plus the contribution of a subset
measure buriedarea (/A & protein) withAtoms2 (/B & protein)        # ½(sasa1 + sasa2 − sasa12)
measure buriedarea ligand withAtoms2 protein listResidues true select true cutoffArea 5
measure area #1.1; measure volume #1.1                     # of an existing surface model
measure contactarea #1.1 withSurface #2.1 distance 3
measure convexity #1.1                                     # colours by convexity (cyan-gray-maroon)
interfaces #1 & protein                                    # buried area per chain pair (+ diagram in GUI)
```
Exclude solvent/ligand explicitly (`& protein`) — they are not excluded automatically. Restore
radii first if they were changed: `size atomRadius default`.

## 6. Verify
- `scene` → the model has `surfaces: [{id, name, display}]`; `model_info("#1")` lists them.
- `render` → `palette` should show red/white/blue (ESP) or cyan/white/goldenrod (MLP); an all-grey
  surface means the colouring failed — read `error`/`output` of the `run` result.
- `layout by="model"` lists the surface as its own item; `occlusion=true` → `occluded_fraction` of
  the ligand behind the surface (then `transparency` or `surface zone`).
- Per-residue areas after `measure sasa`:
```python
from chimerax.atomic import AtomicStructure
s = [m for m in session.models.list(type=AtomicStructure) if m.id_string == "1"][0]
rows = [(round(float(r.area), 1), r.chain_id, r.name, r.number) for r in s.residues if getattr(r, "area", None) is not None]
result = sorted(rows, reverse=True)[:20]
```

## Pitfalls
- `coulombic` colours each chain's surface by that chain's own charges; for the ESP of the whole
  complex on one surface give explicit atoms: `coulombic #1 & protein surfaces #1.1`.
- Gaussian surfaces (`resolution`) have no per-atom patches: `color zone` works, `fromatoms` and
  per-residue show/hide do not (`sharpBoundaries true` restores patches at a cost).
- `transparency` removes ambient-occlusion shading on that surface; `lighting soft` then looks flat.
- A `color #1 …` without `target a`/`c` overwrites the surface colouring; recolour atoms with targets.
- Very large assemblies: use `surface #1 resolution 8` instead of an SES.

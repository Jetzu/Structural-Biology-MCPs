---
name: ligands-docking-viewdock
title: Docked ligand poses and ViewDock
app: chimerax
description: Open docking results (DOCK/GOLD mol2, Vina pdbqt, Glide mae, multi-SDF) as pose submodels, read/rank/filter them by score, count H-bonds and clashes per pose, dockprep a receptor (hydrogens, charges), drive the ViewDock table and save chosen poses
tags: docking, viewdock, poses, mol2, pdbqt, sdf, maestro, dockprep, addh, addcharge, hbonds, clashes, ranking
---
Use for "load my docking results", "which pose scores best / has most H-bonds", "show only the top 5 poses",
"prepare the receptor for docking", "save pose 3 together with the receptor". Verified on ChimeraX 1.11.1 with the
bundled example `share/docs/user/formats/dock4.mol2`. For pocket figures see `ligand-binding-site`, for the full
hbonds/clashes option list `hbonds-contacts-clashes`, for sessions/export `sessions-and-export`.

## 1. Open the receptor first, then the poses
```
open receptor.pdb                      # #1 (open it first so poses become #2.x); its own ligand/waters: delete #1 & solvent
open poses.mol2 showTool false         # DOCK 4-6 / GOLD / MOE mol2: one pose = one submodel #2.1 … #2.N, parent #2 = the file
open glide_out.maegz showTool false    # Glide Maestro (needs r_i_docking_score); poses #2.x, nested one level deeper if the file also holds the receptor
open poses.pdbqt showTool false        # AutoDock Vina; keys Score, RMSD l.b., RMSD u.b. (values are strings)
open poses.sdf                         # multi-SDF also becomes #2.1 … #2.N (named per molecule) but carries no scores (see §7); no showTool keyword here
```
`showTool true` (default) also pops up the ViewDock table in the GUI; `false` keeps the session quiet (the keyword only
exists for mol2/pdbqt/mae/swissdock). `info models` lists `#2.1 test_22 …`; the log says "Opened poses.mol2 containing
30 structures (…)". Descriptors come from mol2 comment lines `########## Key : value` (DOCK) or `> <Gold.xxx>` comments
(GOLD; stored without the `Gold.` prefix, plus `Name`) and live on each pose as the dict attribute `viewdock_data`.
DOCK/Vina/SwissDock poses also carry `rating` (0 unrated, 1 bad, 2 maybe, 3 good); GOLD and Glide poses get it only
once rated, so read it with `.get("rating", 0)`. Glide poses hold the dict as `viewdockx_data` until the ViewDock
table is started (which copies it to `viewdock_data`); the §2 snippet normalises this.
Pitfall: if `open x.pdbqt` fails with "Opener for format 'PDBT' is not installed" (an uninstalled toolshed bundle,
Vinardock, claims the `.pdbqt` suffix), name the built-in format: `open x.pdbqt format pdbqt showTool false` (poses
are then named `x.pdb`, parent `x.pdb group`). If that fails too, call the reader via the `python` tool:
```python
from chimerax.viewdock.pdbqt import open_pdbqt
models, status = open_pdbqt(session, "/path/poses.pdbqt", "poses.pdbqt", True, True)
session.models.add_group(models, name="poses.pdbqt")     # grouped as #N.1 … #N.k with viewdock_data
result = status
```

## 2. Read scores (no GUI needed)
`info models #2.1-5 attribute viewdock_data` lists only the key names; values need Python:
```python
for m in session.models.list():                       # Glide: the Maestro reader stores the dict as viewdockx_data
    if hasattr(m, "viewdockx_data") and not hasattr(m, "viewdock_data"):
        m.register_attr(session, "viewdock_data", "ViewDock"); m.viewdock_data = {"rating": 0, **m.viewdockx_data}
poses = [m for m in session.models.list() if hasattr(m, "viewdock_data")]
result = [(m.id_string, m.name, m.viewdock_data) for m in poses]
```
Typical score keys: DOCK `Energy score` / `Grid Score`, Vina `Score`, Glide `docking_score` (the `r_i_` type prefix
is dropped on reading), GOLD `PLP.Fitness` (the `Gold.` prefix is dropped).

## 3. Rank and filter poses
```
hide #2.1-9999 models; show #2.3 models      # one pose (hide the children, never the parent: `hide #2 models` blanks all)
show #2.1,3,5 models                          # submodels 1, 3 and 5 of #2 (comma list applies per level)
show #2.1-5 models                            # first five; most programs write poses in rank order
close #2.11-9999                              # keep the top 10; surviving ids are not renumbered
rename #2.3 "pose3 best"; view #2.3; cofr #2.3
```
Rank by any key and show the best N (float() because Vina/Glide values can be strings):
```python
from chimerax.core.commands import run, concise_model_spec
key, n = "Energy score", 5
poses = [m for m in session.models.list() if hasattr(m, "viewdock_data") and key in m.viewdock_data]
top = sorted(poses, key=lambda m: float(m.viewdock_data[key]))[:n]       # most negative first
run(session, "hide #2.1-9999 models; show " + concise_model_spec(session, top) + " models")
result = [(m.id_string, m.name, m.viewdock_data[key]) for m in top]
```
Rating a pose from code: `m.viewdock_data["rating"] = 3` (the GUI table and the saved mol2 pick it up).

## 4. H-bonds and clashes per pose (what the ViewDock HBonds/Clashes buttons run)
```
hbonds #2 restrict #1 & (main|ligand) reveal true log false      # every pose vs receptor → one global model "hydrogen bonds"
clashes #2 restrict #1 & (main|ligand) reveal true log false
hbonds #2.3 restrict #1 & (main|ligand) reveal true showDist true log true   # one pose; donor/acceptor table in the log
~hbonds; ~clashes                                                  # clear
```
Hidden poses are still evaluated; their dashes are only drawn while the pose is shown. Count per pose and store the
numbers as descriptors (identical to the GUI columns `H-Bonds` / `Clashes`):
```python
from chimerax.core.commands import run
rec, grp = "#1", "#2"
poses = [m for m in session.models.list() if hasattr(m, "viewdock_data") and m.id_string.startswith(grp[1:] + ".")]
hb = run(session, f"hbonds {grp} restrict {rec} & (main|ligand) reveal true log false")   # list of (donor, acceptor) atoms
cl = run(session, f"clashes {grp} restrict {rec} & (main|ligand) reveal true log false")  # {atom: {atom: overlap}}
nh = {m: 0 for m in poses}; nc = {m: 0 for m in poses}
for d, a in hb:
    for m in {d.structure, a.structure}:
        if m in nh: nh[m] += 1
for a1, partners in cl.items():
    for a2 in partners:
        for m in {a1.structure, a2.structure}:
            if m in nc: nc[m] += 1
for m in poses:
    m.viewdock_data["H-Bonds"] = nh[m]; m.viewdock_data["Clashes"] = nc[m] // 2
result = sorted(((m.id_string, nh[m], nc[m] // 2) for m in poses), key=lambda t: (-t[1], t[2]))
```
Quick structured alternative for one pose: `contacts(spec1="#2.3", spec2="#1", polar_only=True)`.

## 5. Dock prep (receptor) and hydrogens/charges on poses
```
dockprep #1 ah true ac false                           # delete solvent, non-complexed ions, altlocs; complete side chains; add H (seconds)
dockprep #1 delIons false ac true acMethod gasteiger   # keep free ions too (metals with coordination bonds survive anyway); ff14SB charges, Gasteiger for nonstandard
addh #2 hbond false                                     # Vina/pdbqt poses carry polar H only → add the rest before hbonds/clashes
addcharge #2.3 method gasteiger                         # charges on one pose (am1-bcc default = antechamber, minutes per ligand)
info atoms #2.3 attribute charge                        # check; GAFF types land in attribute gaff_type
```
Other `dockprep` options: `delSolvent`, `delAltLocs`, `completeSideChains Dunbrack|ala|gly|false`,
`standardizeResidues MSE,5BU,CSL,UMS`, `ahUseHisName false` (ignore HID/HIE/HIP names), `memorize save|use`.
The log ends with "N hydrogens added … Dock prep finished". `dockprep`/`addh` act on whole models.

## 6. Save chosen poses
```
save top3.mol2 models #2.1-3                 # one @MOLECULE per pose (combineModels false); see below to keep descriptors
save pose3.pdb models #2.3 relModel #1       # ligand coordinates in the receptor's frame (matters if either was moved)
setattr #2 residues name LIG                 # DOCK residue names > 4 chars become *** in PDB → rename first
save complex.pdb models #1|#2.3              # receptor + pose as a 2-MODEL file (`#1,2.3` would mean #1.3 and #2.3)
combine #1 #2.3 modelId 9 name complex; save complex.cif models #9    # single-model complex
save results.cxs                             # session keeps poses, viewdock_data and ratings
```
SDF cannot be written ("Can only open, not save, .sdf files") — use mol2/pdb. To store ratings, scores and the
H-bond/clash counts in the mol2 (what the ViewDock "Save" button does; re-opening restores them):
```python
for m in session.models.list():
    if hasattr(m, "viewdock_data"):
        m.mol2_comments = ["########## %s : %s" % kv for kv in m.viewdock_data.items()]
run(session, "save /path/rated.mol2 models #2.1-3")
```

## 7. The ViewDock table (GUI only)
Rows = poses, columns = ID, Rating + every descriptor; click a header to sort; choosing rows shows those poses and hides
the rest; HBonds / Clashes buttons add the §4 columns (they need a receptor model open); hotkeys g/m/b/u rate
chosen rows once "Hotkeys active" is ticked in the table's context menu; `mousemode rightMode "next docked"` steps
through poses with the right mouse button.
`ui tool show ViewDock` only opens a file dialog — to start the table for poses already open (e.g. SDF poses after
attaching scores from your own table) run:
```python
from chimerax.atomic import AtomicStructure
from chimerax.viewdock import open_viewdock_tool
AtomicStructure.register_attr(session, "viewdock_data", "ViewDock")
for m in session.models.list(type=AtomicStructure):
    if m.id_string.startswith("2.") and not hasattr(m, "viewdock_data"):
        m.viewdock_data = {"rating": 0, "Name": m.name}          # add e.g. "Score": -8.2 per pose
open_viewdock_tool(session, [m for m in session.models.list(type=AtomicStructure) if hasattr(m, "viewdock_data")])
```
Columns are built when the tool starts, so compute §4 counts first (or restart the tool afterwards).

## 8. Verify with the MCP tools
- `scene`: only the intended `#2.x` models are shown; after §4 a top-level `hydrogen bonds` / `clashes` model with a
  `pseudobonds` count is listed.
- `layout(by="items", items=["#2.3", "#1 & #2.3 :< 5"])`: pose visible, low `occluded_fraction`; `render` → ligand
  near centre; `compare_renders` of two poses confirms the switch happened.
- `residue_table(spec="#1 & #2.3 :< 4")` → pocket residues per pose; `measure` key ligand–residue distances.

## Pitfalls
- `hide #2 models` hides the parent (all poses vanish); `show #2.3 models` re-displays the parent as well.
- Model specs: `#1|#2.3` or `#1 #2.3` = receptor + pose; `#1,2.3` = `#1.3` + `#2.3`. Ranges: `#2.4-30`.
- `main` = everything that is not `ligand`/`ions`/`solvent`, so `restrict #1 & (main|ligand)` already skips receptor
  waters and ions, but the receptor's own ligands (nucleotide, cofactor) still count: `delete #1 & ligand` first.
- Maestro files without `r_i_docking_score`, and SDF files, open fine but get no ViewDock data (attach it per §7);
  Glide poses expose it as `viewdockx_data` until the table starts (§2 normalises).
- Vina descriptors are strings; GOLD keys lose the `Gold.` prefix (`PLP.Fitness`) and gain `Name`; `rating` is
  present for DOCK/Vina/SwissDock poses only, so use `.get("rating", 0)` elsewhere.
- `addcharge`/`dockprep ac true` need explicit hydrogens and fail on metal complexes or odd elements (Antechamber/GAFF).

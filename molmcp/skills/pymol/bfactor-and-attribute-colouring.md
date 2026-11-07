---
name: bfactor-and-attribute-colouring
title: Colouring by data: B-factor, occupancy, custom per-residue values, putty, ramps and legends
app: pymol
description: spectrum on b/q/custom atom properties, loading per-residue scores (conservation, SASA, ddG...) from a file into b with alter, cartoon putty tuning, discrete bins (ConSurf grades), ramp_new colour ramps with an on-screen legend, verified with residue_table
tags: b-factor, spectrum, putty, ramp, legend, conservation, consurf, alter, custom data, colouring
---
When to use: "colour by B-factor / flexibility / occupancy / conservation / my scores", "putty tube", "add a
colour bar". Spectrum and palette basics (`spectrum`, `preset.b_factor_putty`, `set_color`) are in
`representations-and-colouring`; the pLDDT palette is in `alphafold-plddt`; ramps on APBS or density maps are in
`surfaces-and-electrostatics` and `maps-and-density`. Example object `prot`. Verified on PyMOL 3.1.5.

## 1. Look at the data before choosing a range (`residue_table` gives `b_mean` per residue; stats via `python`)
```python
vals = []
cmd.iterate("prot and polymer and name CA", "vals.append(b)", space={"vals": vals})
result = {"n": len(vals), "min": min(vals), "max": max(vals), "mean": sum(vals) / len(vals)}
```
Pick `minimum`/`maximum` from this (mean +- 2 sd, or round numbers) and reuse them for the legend.

## 2. spectrum on b or q
```pml
spectrum b, blue_white_red, prot and polymer, minimum=10, maximum=50
spectrum q, yellow_white_blue, prot and polymer, minimum=0, maximum=1
spectrum b, blue_white_red, prot and polymer, byres=1
```
- Without `minimum`/`maximum` the range is the selection's min/max (the `run` output prints `Spectrum: range`).
  Fix it whenever two structures must share a scale or a legend is shown.
- Named palettes join two or three colours with `_` (`blue_white_red`, `red_yellow_green`, `rainbow_rev`; list in
  `help spectrum`). A space-separated list (`white red`, `grey90 marine`) accepts any colour, `set_color` names too.
- `byres=1` colours every atom of a residue (even atoms outside the selection) from the value of the residue's
  first selected atom, N for amino acids, not from an average (verified): select `name CA`
  (`spectrum b, rainbow, prot and polymer and name CA, byres=1`) so the CA value sets the colour, or write the
  value onto every atom of the residue (section 4).

## 3. Cartoon putty (tube thickness = B)
```pml
show cartoon, prot and polymer
cartoon putty, prot and polymer
set cartoon_flat_sheets, 0, prot
spectrum b, rainbow, prot and polymer, minimum=10, maximum=50
set cartoon_putty_scale_min, 0.6
set cartoon_putty_scale_max, 4
set cartoon_putty_scale_power, 1.5
set cartoon_putty_radius, 0.4
set cartoon_putty_transform, 0
rebuild
```
Defaults shown. `cartoon_putty_radius` = base tube radius, `scale_min`/`scale_max` clamp the thickness multiplier,
`scale_power` sharpens the contrast, `cartoon_putty_range` (2) = sd covered. `cartoon_putty_transform` 0 normalises to the
object's own B distribution (every structure looks alike); 3 (absolute non-linear) and 7 (absolute linear) use raw
values so two objects are comparable; 4 = normalised linear. The tube radius follows the CA (or P) B-factor,
but the mean/sd of the normalised modes (0-2, 4-6) are taken over every atom shown as cartoon (verified:
changing side-chain B alone changes the putty with transform 0, not with 3 or 7): write the value onto every
atom of the residue (section 4) or use an absolute transform. All-equal values give `Extrude-Warning: invalid
putty settings (division by zero)` with transform 0. After any `alter b=` run `rebuild` or the thickness stays
stale. `cartoon automatic, prot` reverts.

## 4. Custom per-residue values
Back the real B up first (incentive PyMOL: custom property; otherwise `create prot_orig, prot`):
```pml
alter prot, p.b_orig = b
alter prot and polymer, b = resv / 76.0
rebuild
spectrum b, white red, prot and polymer, minimum=0, maximum=1
```
Restore with `alter prot, b = p.b_orig` + `rebuild`. A dict set in `python` (`stored.scores = {...}`) works
straight from the command line: `alter prot and polymer, b = stored.scores.get(resi, -1.0)`.

From a file (two columns `resi value`, `#` comments; CSV: add `line = line.replace(",", " ")`), `python` tool:
```python
scores = {}
for line in open("/path/to/scores.tsv"):
    f = line.split()
    if len(f) >= 2 and not line.startswith("#"):
        scores[f[0]] = float(f[1])            # key = resi string ("48", "48A"); use (chain, resi) for multi-chain
cmd.alter("prot and chain A and polymer", "b = scores.get(resi, -1.0)", space={"scores": scores})
cmd.rebuild()
result = {"loaded": len(scores), "unmatched_residues": cmd.count_atoms("prot and chain A and name CA and b < 0")}
```
Then colour only matched residues and grey out the rest (the sentinel -1 must not enter the spectrum range):
```pml
spectrum b, blue_white_red, prot and chain A and polymer and b > -0.5, minimum=0, maximum=1
color grey70, prot and chain A and polymer and b < -0.5
```
To keep B intact (incentive PyMOL, verified on 3.1) put the data in a custom property and spectrum that:
```pml
alter prot and polymer, p.cons = stored.scores.get(resi, 0.0)
spectrum p.cons, red_yellow_green, prot and polymer, minimum=0, maximum=1
```
(`spectrum properties["cons"], ...` is the documented equivalent.) Values survive `save x.pse`; `save x.pdb` writes
the altered `b` column (fixed width: keep values within -99.99 to 999.99), a handy way to share the data.

## 5. Discrete bins (conservation grades, categories)
ConSurf's PDB download (grades written into the B-factor column) carries the grade 1 (variable) to
9 (conserved) in `b`; insufficient-data residues fall outside 1-9 (check with section 1). ConSurf palette:
```pml
set_color consurf1, [16, 200, 209]
set_color consurf2, [140, 255, 255]
set_color consurf3, [215, 255, 255]
set_color consurf4, [234, 255, 255]
set_color consurf5, [255, 255, 255]
set_color consurf6, [252, 237, 244]
set_color consurf7, [250, 201, 222]
set_color consurf8, [240, 125, 171]
set_color consurf9, [160, 37, 96]
set_color consurf_ins, [255, 255, 150]
color consurf_ins, prot and polymer
set cartoon_discrete_colors, 1
```
```python
for i in range(1, 10):
    cmd.color("consurf%d" % i, "prot and polymer and b > %g and b < %g" % (i - 0.5, i + 0.5))
```
Any thresholds work the same way (`color red, prot and b > 60`); `cartoon_discrete_colors 1` = sharp residue edges.

## 6. Colour ramps and the on-screen legend
`spectrum` draws no colour bar. A ramp object with map `none` is a pure legend: a bar with the range ends
printed along the bottom of the viewport, in OpenGL and in ray-traced output (verified):
```pml
ramp_new legend, none, [10, 30, 50], [blue, white, red]
ramp_update legend, range=[0, 0.5, 1]
```
Use the same `range` ends as `spectrum`'s `minimum`/`maximum`, one `range` value per colour, and the palette's
colours in order (`blue_white_red` -> `[blue, white, red]`; four slots `[0, 25, 50, 100]` with
`[blue, cyan, white, red]` also work; `ramp_update legend, color=[green, white, magenta]` recolours). The bar has
no title: name the quantity in the caption or add a `pseudoatom` label. Every enabled ramp draws its bar in the
same place (APBS/map and proximity ramps too), so two enabled ramps overprint each other's bar and labels
(verified): `disable` the colouring ramp (a disabled ramp keeps colouring its object, only the bar goes) so the
legend is the only enabled one. `disable legend` hides it, `enable legend` shows it again, `delete legend` removes it.

Ramps that colour by a value in space (map potential/density, or distance from an object) are applied through
rep colours or `color`, not `spectrum`:
```pml
create lig_obj, prot and organic
ramp_new prox, lig_obj, [0, 4, 8], [red, white, blue]
set surface_color, prox, prot
set cartoon_color, prox, prot
color prox, prot and polymer
```
The second argument must be an object (map or molecule), not a selection. `unset surface_color, prot` /
`unset cartoon_color, prot` and `color grey80, prot` return to plain atom colours.

## Pitfalls
- `spectrum` on `all` includes waters, ligands and sentinel values in the auto range: restrict to `polymer` and
  exclude sentinels. Rep colour overrides (`cartoon_color`, `surface_color`) hide what `spectrum` did: `unset` them.
  `alter` overwrites `b` for the whole session; back it up (section 4) before loading data.
- Ramp objects show up in `scene` as type `ramp`; `alignto target, all` fails on them (`Invalid selection name
  "legend"`) while `extra_fit` skips them: name the molecular objects explicitly.
- `set_color` names and spectrum colours are unnamed in `residue_table`: it reports `index_N` plus `rgb`.

## Verify
- `residue_table(selection="prot and chain A and polymer")`: `b_mean` is the value you loaded, `rgb` runs from the
  low colour to the high colour, `reps_shown` contains `cartoon`. Filter it to answer questions
  (`selection="prot and polymer and name CA and b > 0.8"`); `measure(kind="count", selection1=...)` for counts.
- `render()`: `palette` must span the ramp colours (blue/white/red families for `blue_white_red`); with the legend
  enabled the last rows of the ASCII map show the bar. `compare_renders()` before/after gives `changed_fraction` > 0.
- `scene(detail="full")`: `legend` listed as `ramp`; `settings(names=["cartoon_putty_transform",
  "cartoon_putty_scale_max", "cartoon_putty_scale_min", "cartoon_discrete_colors"])` for the putty/colour setup.

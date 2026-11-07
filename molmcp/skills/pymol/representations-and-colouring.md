---
name: representations-and-colouring
title: Representations and colouring
app: pymol
description: show/hide/as, cartoon styles and settings, sticks/spheres/lines/surface, colouring by name/hex/set_color, by element, chain, chainbow, spectrum (B-factor, count), B-factor putty
tags: representation, cartoon, sticks, surface, colour, spectrum, b-factor, chainbow, set_color
---
Use this to change how things look. Always run `scene` (or `object_info(name)`) first to see which
representations and colours are active, then batch the commands in one `run` call. Example object: `prot`,
ligand selection `lig` (`select lig, prot and organic`).

## Representations
Names: `lines sticks spheres cartoon ribbon surface mesh dots nb_spheres labels dashes nonbonded cell
ellipsoids volume slice`. `show rep, sel` adds, `hide rep, sel` removes, `as rep, sel` replaces every rep
of the selection, `hide everything` / `hide everything, sel` clears.
```pml
hide everything
show cartoon, prot and polymer
show sticks, lig
show spheres, prot and inorganic
show nb_spheres, prot and solvent within 4 of lig
show lines, byres (prot and polymer within 4 of lig)
show sticks, (byres (prot and polymer within 4 of lig)) and not name N+C+O
set cartoon_side_chain_helper, 1
```
`cartoon_side_chain_helper 1` hides backbone sticks/lines where cartoon is shown so side chains join the
cartoon cleanly. `set valence, 1` draws double bonds on sticks (`valence_mode 1` centres them).

Cartoon types (`cartoon type, sel`): `automatic loop rectangle oval tube arrow dumbbell putty skip dash cylinder`.
```pml
cartoon automatic, prot
cartoon tube, prot and chain B
cartoon putty, prot and chain A
cartoon skip, prot and resi 1-3
set cartoon_fancy_helices, 1
set cartoon_cylindrical_helices, 0, prot
set cartoon_flat_sheets, 1
set cartoon_smooth_loops, 1
set cartoon_transparency, 0.3, prot
set cartoon_highlight_color, grey70
set cartoon_discrete_colors, 1
set cartoon_ring_mode, 3
set cartoon_gap_cutoff, 10
```
- `cartoon_fancy_helices` = helices with dumbbell cross-section; `cartoon_cylindrical_helices 1` = solid
  cylinders (`cartoon_helix_radius`). `cartoon_loop_radius` (0.2), `cartoon_tube_radius` (0.5),
  `cartoon_oval_length`/`cartoon_rect_length` resize the strands/helices.
- `cartoon_discrete_colors 1` makes colour changes sharp at residue boundaries (figures with two-colour domains).
- `cartoon_gap_cutoff N` draws dashed loops across gaps of fewer than N residues (N=2 bridges one missing residue,
  N=6 up to five; default 0 = no dashes).
- Nucleic acids: `cartoon_ring_mode` 0-5 (3 = filled rings with edges), `cartoon_ladder_mode`,
  `cartoon_nucleic_acid_mode` (default 4).
- Sticks/spheres/lines: `set stick_radius, 0.25`, `set stick_ball, 1` + `stick_ball_ratio 1.5` (ball-and-stick),
  `set sphere_scale, 0.3, sel` (small spheres for ions), `set line_width, 2`, `set ribbon_width, 3`.
  Per-bond: `set_bond stick_radius, 0.35, lig`.
- Transparency per rep: `transparency` (surface), `cartoon_transparency`, `stick_transparency`,
  `sphere_transparency` - all 0 (opaque) to 1, settable per object/selection: `set transparency, 0.4, prot`.

## Colouring
Colour names: standard (`red marine forest orange yellow slate violet wheat salmon`...), greys `grey10`...`grey90`
(`grey50` mid), `0xRRGGBB` hex, or your own with `set_color` (0-1 floats or 0-255 ints, inferred).
```pml
set_color fig_blue, [0.12, 0.47, 0.71]
set_color fig_orange, [255, 127, 14]
color fig_blue, prot and chain A
color fig_orange, prot and chain B
color 0x3366cc, prot and resi 25-30
color grey80, prot and elem C
color atomic, prot and not elem C
util.cnc prot
util.cbaw lig
util.cbag prot and polymer
util.cbc prot
util.chainbow prot
util.cbss("prot", "red", "yellow", "green")
util.rainbow prot
```
- `util.cnc` = colour non-carbons by element (keeps carbon colour); `util.cba<x>` = carbons in colour x
  (`g`reen `c`yan `m`agenta `y`ellow `s`almon `w`hite `b`lue `o`range `p`urple `k` pink) + atomic others.
- `util.cbc` = one colour per chain; `util.chainbow` = rainbow N->C per chain; `util.rainbow` = rainbow over the
  whole selection; `util.cbss(sel, helix, sheet, loop)` = by secondary structure. (`util.ss` is NOT a colouring
  command: it is a deprecated alias of `dss` that re-assigns secondary structure and changes no colours.)
- Representation-specific colours override atom colours: `set cartoon_color, salmon, prot`,
  `set surface_color, white, prot`, `set stick_color, grey90, lig`, `set sphere_color`, `set mesh_color`,
  `set label_color`. Remove with `unset cartoon_color, prot`. `util.color_deep("green", "prot")` clears those
  overrides and colours atoms.

Spectrum (property gradients):
```pml
spectrum b, blue_white_red, prot and polymer, minimum=10, maximum=50
spectrum count, rainbow, prot and name CA
spectrum resi, rainbow, prot and chain A
spectrum q, blue_red, prot
spectrum b, blue_white_red, prot and polymer, byres=1
```
Expressions: `b` (B-factor/pLDDT), `q`, `count` (atom index, rainbow N->C), `resi`, `pc`, `properties["key"]`.
Palettes: `rainbow rainbow_rev blue_white_red red_white_blue blue_red green_white_magenta yellow_white_blue`
and any space-separated colour list (`spectrum b, red yellow white, prot`). Set `minimum`/`maximum`
explicitly so two structures share a scale (pLDDT: `spectrum b, red_yellow_green, prot, 50, 90`).

B-factor putty:
```pml
preset.b_factor_putty("prot")
set cartoon_putty_scale_min, 0.5
set cartoon_putty_scale_max, 4
set cartoon_putty_transform, 0
```
(`preset.b_factor_putty` = `cartoon putty` + `spectrum b` on CA/P atoms; transform 0 normalised, 3 absolute.)

## Pitfalls
- `color` sets atom colours; a cartoon still coloured by `cartoon_color` will not change - `unset` it.
- `spectrum` on `all` includes waters/ligands and skews the range: restrict to `polymer`.
- `util.*` and `preset.*` are Python calls: `util.cbc prot` works on the command line, with arguments beyond
  the selection use the call form `util.cbss("prot", "red", "yellow", "green")`.
- Hetero/organic atoms are excluded from surfaces by default (`flag ignore`), see the surfaces skill.
- `as cartoon` on a ligand shows nothing (no backbone); keep `show sticks, lig` after `as cartoon, prot`.

## Verify
- `scene(detail="full")` -> per object `reps_atom_counts`, per chain `reps_shown` and `top_colors` (named).
- `object_info("prot")` -> `setting_overrides` lists rep colours/transparency set at object level.
- `render()` -> `palette` names the dominant colours; `layout(by="chain")` shows each chain's share and position;
  `compare_renders()` confirms a recolour changed pixels (`changed_fraction` > 0).

---
name: styling-presets
title: Styling presets and figure-ready set recipes
app: pymol
description: preset.* commands (publication, pretty, technical, simple, ball_and_stick, b_factor_putty, ligand_* ) and curated set-command recipes for clean cartoons, sticks, surfaces, lighting profiles and a figure colour palette
tags: preset, style, figure, cartoon, settings, palette, lighting
---
Presets are Python functions: call them as `preset.name("object_or_selection")` in `run` (verified syntax;
`preset.publication(selection="prot", solv=True)` also works). They act on the given selection's object and
change its representations, colours and some object-level settings. Example object `prot`.

## preset.* catalogue
| call | result |
|---|---|
| `preset.simple("prot")` | ribbon coloured by chain, ligands (plus attached residues) as sticks, waters as nonbonded; `simple_no_solv` hides waters |
| `preset.ball_and_stick("prot")` | white sticks (bond-level `stick_radius` 0.14) + spheres at `sphere_scale` 0.25; atom colours are left as they are (`util.cnc` afterwards for element colours) |
| `preset.b_factor_putty("prot")` | cartoon putty scaled by B-factor + `spectrum b`, flat sheets off |
| `preset.technical("prot")` | chainbow ribbon + lines for all atoms, ligand sticks, every polar contact as dashes (`prot_pol_conts`) - analysis view |
| `preset.pretty("prot")` | cartoon coloured rainbow N->C (`spectrum count` on carbons), ligands as sticks with by-chain carbons, waters hidden; `pretty_solv` shows ligands and waters as licorice |
| `preset.publication("prot")` | `pretty` + smooth loops, grey50 highlight, fancy helices, flat sheets; `pub_solv` keeps waters |
| `preset.ligand_cartoon("prot")` | cartoon + side chains near ligands (`cartoon_side_chain_helper`) |
| `preset.ligand_sites("prot")` | pocket view: ribbon, pocket lines, carved surface patch, polar contacts (`prot_pol_conts`), waters; variants `_hq`, `_trans`, `_trans_hq`, `_mesh`, `_dots` |
| `preset.ligands("prot")` | `ligand_sites` without the surface patch: chainbow ribbon, lines for residues within 5 A of ligands, ligand sticks, polar contacts (`prot_pol_conts`), then zooms on the ligands |
| `preset.interface("prot")` | protein-protein interface: cartoon coloured by chain (non-carbons by element), residues within 4.5 A of another chain as sticks + nb_spheres |
| `preset.classified("prot")` | cartoon for `polymer`, sticks for `organic`, spheres for `inorganic`; changes no colours or settings |
| `preset.default("prot")` | PyMOL's load-time look (lines + nonbonded) |
Presets start with `hide everything` on the object, so apply them FIRST and refine after. They also reset the
global `two_sided_lighting` to 0, unset the object's `transparency`, `surface_quality`, `surface_type`,
`sphere_scale`, bond-level `stick_radius`/`stick_color` and `cartoon_*` overrides, and delete an existing
`<obj>_pol_conts`. `preset.publication` sets these object-level settings: `cartoon_smooth_loops 1`, `cartoon_highlight_color grey50`,
`cartoon_fancy_helices 1`, `cartoon_flat_sheets 1`, `cartoon_side_chain_helper 0`.

## Recipe A - clean cartoon figure (white background)
```pml
preset.publication("prot")
hide everything, prot and (solvent or inorganic)
bg_color white
set cartoon_fancy_helices, 1
set cartoon_flat_sheets, 1
set cartoon_smooth_loops, 1
set cartoon_discrete_colors, 1
set cartoon_highlight_color, grey60
set cartoon_loop_radius, 0.25
set cartoon_oval_length, 1.2
set cartoon_rect_length, 1.3
set cartoon_sampling, 20
set ray_trace_mode, 1
set ray_trace_gain, 0.01
set ray_shadow, 0
set depth_cue, 0
set specular, 0.15
set light_count, 2
```
Add `set cartoon_cylindrical_helices, 1, prot` for cylinder helices (domain overview), `cartoon tube, prot and
chain B` for a de-emphasised partner.

## Recipe B - ligand / sticks
```pml
set stick_radius, 0.22
set stick_ball, 1
set stick_ball_ratio, 1.6
set stick_h_scale, 0.8
set valence, 1
set valence_mode, 1
set sphere_scale, 0.25, prot and inorganic
util.cbaw prot and polymer
util.cbag prot and organic
set cartoon_transparency, 0.65, prot
set cartoon_side_chain_helper, 1
```
`set stick_quality, 20` and `set sphere_quality, 2` for ray-traced close-ups (only matters for OpenGL draw;
ray tracing is always smooth).

## Recipe C - surface overview
```pml
set surface_quality, 1
set surface_color, grey90, prot
set transparency, 0.0, prot
set two_sided_lighting, 1
set ambient_occlusion_mode, 1
set ambient_occlusion_scale, 20
set ray_shadow, 1
util.ray_shadows("medium")
```
`util.ray_shadows(mode)` with `none light medium heavy black matte soft occlusion` sets `ray_shadow`,
`light_count`, `ambient`/`direct`/`reflect`/`shininess` and the shadow-decay settings consistently. `occlusion` is
a 9-light soft-lighting profile only - it does NOT enable `ambient_occlusion_mode`; set that yourself (as above).

## Recipe D - flat "vector" look (black outlines, no shading)
```pml
set ray_trace_mode, 3
set ray_trace_gain, 0.03
set ray_trace_color, black
set ambient, 0.8
set direct, 0.2
set reflect, 0
set specular, 0
set ray_shadow, 0
set cartoon_discrete_colors, 1
```
Mode 3 quantises colours (poster/graphical-abstract style); mode 2 = black and white line art.

## Recipe E - figure palette (define once, reuse by name)
```pml
set_color fig_blue, [31, 119, 180]
set_color fig_orange, [255, 127, 14]
set_color fig_green, [44, 160, 44]
set_color fig_red, [214, 39, 40]
set_color fig_purple, [148, 103, 189]
set_color fig_grey, [127, 127, 127]
color fig_grey, prot and polymer
color fig_blue, prot and chain A and ss H
color fig_orange, prot and chain A and ss S
```
Colour-blind-safe pairs: `fig_blue`/`fig_orange`, `marine`/`yellow`; avoid red/green domain pairs.

## Interactive-performance settings (undo before export)
`util.performance(0)` = maximum quality (`antialias_shader 2`, `surface_quality 1`, `cartoon_sampling 14`),
`util.performance(33)` / `(66)` intermediate, `util.performance(100)` = fastest. `set defer_builds_mode, 3` for multi-state trajectories. These are OpenGL
settings and do not affect `ray` except `surface_quality`/`cartoon_sampling`.

## Pitfalls
- `set x, v` without a selection is global; `set x, v, prot` is object-level and overrides global (shows in
  `object_info` `setting_overrides`); `unset x, prot` removes it. Presets leave object-level settings behind.
- `preset.ligand_sites` sets global `two_sided_lighting` and draws a surface patch that slows big systems.
- `set_color` on an existing name recolours everything already using it (after `recolor`).
- Settings in a `.pse` travel with the session; a user's `~/.pymolrc` may override globals at startup.

## Verify
- `settings(names=["cartoon_fancy_helices", "ray_trace_mode", "stick_radius", "valence"])` and
  `settings(names=["cartoon_highlight_color", "cartoon_smooth_loops"], object="prot")` for object-level values.
- `scene(detail="full")` -> `reps_atom_counts` per object confirms what a preset turned on.
- `render(ray=True)` -> `palette` should list your palette names (`fig_blue`...) once applied; `compare_renders()`
  between recipes shows the visual delta.

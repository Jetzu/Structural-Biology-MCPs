---
name: representations-and-colouring
title: Representations and colouring
app: chimerax
description: Show/hide atoms, cartoons and surfaces with targets; cartoon/ribbon styles; atom styles and sizes; colour by chain, element, attribute/B-factor, rainbow; surface colouring; transparency per representation
tags: representation, cartoon, ribbon, style, color, rainbow, bfactor, transparency, show, hide
---
Use for "show X as sticks", "colour by chain", "rainbow the ribbon", "make the surface transparent",
"hide waters", "helix tubes", "thinner cartoons". Syntax verified against the ChimeraX 1.11 docs.

## 1. Know what is shown
`scene` → per model: `shown_atoms`, `shown_ribbon_residues`, `atom_styles_shown`, `surfaces`,
`categories`; `detail="full"` adds per-chain `atom_colors`/`ribbon_colors`. `model_info("#1")` for one.

## 2. Show / hide with targets
`show spec [level]` / `hide spec [level]`; levels: `atoms` (a), `bonds` (b), `pseudobonds` (p),
`cartoons`/`ribbons` (c), `surfaces` (s), `models` (m); or `target acs` (letters, any order).
Blank spec = everything; default level is `atoms` when the spec contains atoms.
```
hide #1 atoms; show #1 cartoons                 # cartoon only
show ligand | (ligand :< 5) atoms               # ligand plus residues within 5 Å
show :HEM target a; style :HEM stick
hide solvent; hide H                            # waters, hydrogens (H = element spec)
show #1/A surfaces; hide #1/B surfaces          # per-chain surface patches
hide #!1 models                                 # whole model, keeps sub-model settings (#! = parent only)
cartoon #1; cartoon hide #1/B:1-20              # same as show/hide cartoons; ~cartoon also hides
cartoon #1 suppressBackboneDisplay false        # backbone atoms visible together with the cartoon
```

## 3. Atom styles and sizes
```
style #1 stick; style ligand ball; style ions sphere
style :PHE,TYR,TRP ringFill thick               # filled aromatic rings (thin | off)
size stickRadius 0.25                           # default 0.2 Å
size ballScale 0.3; size ligand atomRadius +0.3; size atomRadius default
size hbonds pseudobondRadius 0.08
nucleotides #1 ladder; nucleotides #1 tube/slab; nucleotides #1 fill; ~nucleotides #1
```

## 4. Cartoon / ribbon style (per model; `cartoon style` alone reports)
```
cartoon style #1 width 1.5 thickness 0.3                    # Å; defaults 2.0 / 0.4
cartoon style #1 & helix xsection oval; cartoon style #1 & strand xsection rectangle width 2
cartoon style #1 xsection barbell                            # rounded edges, thin middle (not coil)
cartoon style protein modeHelix tube radius 2 sides 24      # helix cylinders (= preset cylinders)
cartoon style protein modeHelix default arrows false xsection oval width 1 thick 1   # licorice look
cartoon style #1 sides 24 divisions 20                       # smoother ribbon
cartoon style #1 arrowsHelix true arrowScale 2
cartoon tether #1 opacity 0                                  # hide tethers to displayed CA atoms
preset ribbons | preset cylinders | preset licorice          # built-in cartoon/nucleotide presets
worm bfactor #1 min:0.2 max:2.5; ~worm                      # radius by attribute (= cartoon byattribute)
```

## 5. Colouring
`color spec colorname [what|target letters] [transparency p]`; targets `a` atoms, `b` bonds,
`c`/`r` cartoons, `s` surfaces, `p` pseudobonds, `f` ring fill, `l` labels (default `abcspf`).
```
color #1 cornflower blue                       # everything of model 1 (names may contain spaces)
color /A gold target c; color /A gold cartoons # cartoon only
color #1/A:12,260-275 hot pink target a        # atoms/bonds only
color bychain; color #1 bychain target c       # chain scheme (same chain ID → same colour across models)
color byelement; color byhetero                # byhetero leaves carbons as they are
color ligand byhet; color C bymodel target a   # restore the model carbon colour
color bypolymer; color bynucleotide; color random
color #1 fromatoms target s; color #1 fromcartoons target s   # surface patches match atoms/cartoon
color #4 medium violet                         # a map or surface model
color name myteal 0,60,60; color #1 myteal     # define a colour name (R,G,B percent)
color #2 bymodel                               # initial model colours (separates two models)
```
Sequential: `rainbow spec [residues|chains|polymers|structures] [target c] [palette p]`
```
rainbow #1; rainbow #1 chains palette paired-8; rainbow #1/A:1-120 target c
color sequential #1 polymers palette cornflowerblue:red:gold
```
By attribute: `color byattribute attr spec [target] [palette p] [range lo,hi] [average residues]`
```
color bfactor #1 palette bluered range 20,80                   # = color byattribute bfactor
color bfactor (#1 & protein) palette rainbow average residues target c
measure sasa #1 & protein; color byattribute r:area #1 palette ylorrd-5   # residue attribute
color #1 & @@bfactor>60 red target a                           # attribute test inside the spec
color modify #1 lightness + 20 target c                        # tweak existing colours (hue, saturation…)
```
Palettes: `rainbow`, `bluered`/`blue-white-red`, `redblue`, `cyanmaroon`, `grayscale`, `alphafold`,
`esmfold`, `pae`, ColorBrewer (`paired-8`, `set2-6`, `ylgnbu-5`, `rdylbu-7`), `c1:c2:c3`,
`^name` reverses. `palette list` prints them.

## 6. Transparency
`transparency spec percent [target …]` — 0 opaque … 100 invisible; default target `s` (surfaces).
```
transparency #1 60                      # molecular surfaces of model 1
transparency #1 70 target c             # cartoons
transparency ligand 0 target a          # atoms opaque again
color #1.1 white transparency 50        # colour + transparency in one go (surface #1.1)
```
Volume isosurfaces: `volume #2 transparency 0.5` (fraction 0–1) or `transparency #2 50`.

## 7. Verify
- `run` → `changes` lists display/colour changes; nothing listed = the spec matched nothing
  (check with `selection_info("spec")`) or the representation was already in that state.
- `scene detail="full"` → `ribbon_colors` / `atom_colors` per chain, `shown_*` counts.
- `render` → `palette` names and shares; `layout by="chain"` → which chains are visible and how big.

## Pitfalls
- `color` without a target recolours surfaces too and destroys electrostatic/zone colouring; use
  `target a` / `target c`. `color single #1.1` returns a surface to one colour.
- Surfaces are created with the average cartoon colour; recolour them explicitly afterwards.
- Hiding atoms and cartoons leaves nothing visible → `render` reports `empty: true`.
- Cartoon style settings apply only to models already open.
- `hide H` also hides polar hydrogens needed for H-bond pictures; use `hide HC` (non-polar only).
- Ring fill colour is target `f`; nucleotide slabs/ladders follow it, not the atom colour.

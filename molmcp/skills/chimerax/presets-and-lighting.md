---
name: presets-and-lighting
title: Presets and lighting
app: chimerax
description: The preset command (publication, cartoon, surface and initial-style presets), custom preset folders (.cxc/.py), lighting modes simple/soft/full/flat/gentle and their options, material, silhouettes, graphics quality, background colour and colour-key contrast, and keeping one style across sessions (style scripts, aliases, startup commands, .cxs)
tags: preset, lighting, material, silhouettes, graphics, background, style, alias, startup, custom preset, shadows, ambient occlusion
---
Use for "apply the publication preset", "soft lighting", "no highlights", "outline everything",
"same look for all my figures", "make my own preset". Window size, `save` image options and
supersampling: skill publication-rendering; cartoon/atom styles: representations-and-colouring;
colour keys and 2D labels: labels-keys-and-measurements. Verified against ChimeraX 1.11.

## 1. Inspect first
`scene` → `lighting` (`key_light_intensity`, `fill_light_intensity`, `ambient_light_intensity`,
`shadows`, `multishadow` = ambient-occlusion directions, `depth_cue`, `silhouettes`, `material`
{ambient, diffuse, specular, exponent}) and `background.rgb`. `lighting`, `material`,
`graphics silhouettes`, `graphics selection` and `graphics quality` without arguments print their
current values into `output` (`set` alone prints only background colour and subdivision).

## 2. Built-in presets (`preset [category] name`)
Names match case-insensitively, exact → prefix → substring; quote names containing spaces.
```
preset sil           # Overall Look / Publication 1: white bg, silhouettes on, depth cue off (= preset 1)
preset depth         # Publication 2: white bg, silhouettes off, depth cue on               (= preset 2)
preset inter         # Interactive: background back to the preference, silhouettes off, depth cue on
preset ribbons | preset cylinders | preset licorice    # Cartoons/Nucleotides: cartoon + base slabs/stubs/ovals; hides surfaces, protein atoms, solvent
preset orig; preset cartoon; preset sticks             # Initial Styles = automatic styling (+ lighting simple)
preset "chain colors"; preset "single color"           # Initial Styles, all atoms as spheres (+ lighting full / soft)
preset ghost; preset surf atom; preset "molecular surfaces" chain   # white 80 % / atom colours 70 % / chain opaque
```
- Overall Look presets change only background, silhouettes and depth cue: shadows, intensities and
  material stay as they were. Cartoon/Surface/Initial-Style presets act on atomic models only and
  hide surfaces; Initial Styles rebuild the display and re-run automatic styling, which with at most
  one structure open also sets the lighting (`orig|cartoon|sticks` → simple, `"chain colors"` → full,
  `"single color"` → soft); with two or more structures open the lighting is left alone.
- `preset space` and `preset publication` are ambiguous (`error` lists the candidates);
  `preset full` is not a preset (`lighting full` is). There is no `preset list`; `run` → `output`
  logs "Using preset: Category / Name" plus the expanded commands. List names with the python tool:
```python
result = session.presets.presets_by_category   # {'Overall Look': ['publication 1 (silhouettes)', ...], 'Custom': [...]}
```

## 3. Lighting modes (`lighting [mode] [options]`, global)
```
lighting simple     # key 1.0 + fill 0.5 + ambient 0.4, no shadows (= lighting default); resets ALL values, depthCue true
lighting full       # key 0.7 with shadows + fill 0.3 + ambient 0.8 with 64-direction ambient occlusion
lighting soft       # ambient 1.5 only + ambient occlusion (64 dirs): surfaces, spheres, maps
lighting gentle     # soft with msMapSize 128 / msDepthBias 0.05: emphasises big pockets, less sooty
lighting flat       # ambient 1.45 only, no shadows; ALSO turns silhouettes on and sets depthJump 0.01
lighting shadows true qualityOfShadows fine        # key-light shadows; coarse 1024 … finer 8192 map
lighting multiShadow 256 msMapSize 2048            # smoother ambient occlusion (0 = off, max 1024)
lighting intensity 0.8 fillIntensity 0.3 ambientIntensity 1.0 direction 1,-1,-1 color white
lighting depthCue false                            # or depthCueStart 0.6 depthCueEnd 1 depthCueColor white
lighting moveWithCamera false                      # lights fixed to the scene instead of the screen
lighting model #2 shadows false; lighting model #3 directional false; lighting model #4 depthCue false
```
`simple`/`default` resets every lighting value (depth cue on with its colour = current background,
map sizes, `moveWithCamera`); `full|soft|gentle|flat` change only the intensities and shadow values
listed and leave depth cue as it is. Per-model options only switch a globally enabled effect off for
that model. Shadows need key intensity > 0 (invisible in `soft`/`flat`). `multiShadow N` re-renders
N depth maps whenever shapes or clipping change and costs N texture look-ups per pixel on every
frame: keep 64 while composing, raise it (256–512) just before `save`.

## 4. Material (global, all objects)
```
material dull        # specular 0: matte, no hot spots (pairs well with soft/full)
material shiny       # specular 1;  material chimera = specular 1, exponent 6 (old Chimera look)
material default     # 1.11 defaults: specular 0.3, exponent 30, reflectivity 0.8, ambientReflectivity 0.8
material specularReflectivity 0.2 exponent 60 reflectivity 0.9
material transparentCastShadows true; material meshesCastShadows true
```

## 5. Silhouettes, selection outline, geometry quality
```
graphics silhouettes true width 2 color black depthJump 0.03   # width in pixels (2 = Retina default)
graphics silhouettes false
graphics selection color yellow width 3                        # outline of selected items (default lime)
graphics quality 2; set subdivision 2                          # atom/bond triangles and ribbon divisions
graphics quality ribbonSides 24 ribbonDivisions 20 bondSides 16
graphics quality 1                                             # back to automatic; graphics triangles #1 = load
```
`depthJump` is a fraction of the near–far depth: lower (0.01) outlines helices inside a cartoon,
higher (0.05) keeps only outer contours. `width` is in output pixels: `save … supersample 3` only
smooths the lines (sub-pixel jitter at the same size), while a larger `save … width/height` makes
the same pixel width look thinner, so scale `width` with the image size.

## 6. Background and colour keys
```
set bgColor white; set bgColor #f4f4f4; set bgColor 10,10,20; ~set bgColor   # r,g,b in 0–100 %; ~ = user preference
graphics bgColor black                                                       # same as set bgColor
```
The depth-cue colour follows the background whenever the two are equal (`set bgColor white` on the
black default turns it white too; `lighting simple` resets it to the background), so far parts fade
into the background. If they drifted apart: `lighting depthCueColor <bg colour>` or `depthCue false`.
Dark background: `lighting simple|full`, `graphics silhouettes color white`.
White background: `preset sil` (depth cue off) or `lighting soft` + `material dull`.
`key … labelColor default` and `borderColor default` flip black/white with the background; set an
explicit colour only after the background is final. `save fig.png transparentBackground true`
makes the background fully transparent (alpha 0) while silhouettes and shadows on objects stay.

## 7. Custom presets
A folder of command files becomes the Presets menu: `my_presets/paper_white.cxc` → `preset "paper
white"` (category Custom); `my_presets/Lab_Style/teal_cartoon.cxc` → `preset "lab style" teal`
(sub-folder = category; underscores become spaces; `.py` files run as Python scripts). Files hold
any commands, one per line. Set the folder in Preferences ▸ Startup ▸ Custom presets folder, or:
```python
import os
folder = os.path.expanduser("~/chimerax_presets")
os.makedirs(folder, exist_ok=True)
with open(os.path.join(folder, "paper_white.cxc"), "w") as f:
    f.write("set bgColor white\nlighting soft\ngraphics silhouettes true width 1.5\nmaterial dull\n")
from chimerax.preset_mgr import settings as ps
ps.settings.folder = None; ps.settings.folder = folder   # change of value = rescan (also after edits)
ps.settings.save()                                        # remembered in future launches
result = session.presets.presets_by_category
```
`preset custom paper_white` fails (name is "paper white"); `preset paper` works.

## 8. One style across sessions
- Style script: `~/styles/paper.cxc`; begin every figure with `open ~/styles/paper.cxc`.
- `alias paper lighting soft; graphics silhouettes true; set bgColor white; material dull` → `paper`;
  `alias list` / `alias delete paper`. Aliases, `color name` definitions and the lighting, material,
  silhouette and background state are stored in `.cxs` sessions and restored by `open x.cxs`.
- Every launch: Preferences ▸ Startup ▸ "Execute these commands at startup" (runs when the GUI
  command line starts, not under `--nogui`), or from the python tool:
```python
from chimerax.cmd_line import settings as cl
cmds = [c for c in cl.settings.startup_commands if not c.startswith("alias paper")]
cmds += ["color name labteal 0,60,60", "alias paper lighting soft; graphics silhouettes true; set bgColor white"]
cl.settings.startup_commands = cmds; cl.settings.save()
```
- Batch: `ChimeraX --cmd "open ~/styles/paper.cxc"` or `--script make_figs.py` (+ `--nogui --exit`;
  `--offscreen` image rendering is Linux-only). `info path user unversioned config` prints the
  preferences folder.
- Order matters: `open`, `preset cartoon|orig|sticks` first, then lighting/material/background.

## 9. Verify
- `run` → `output`: "Using preset: …" and "Preset expands to …" (.cxc) or "Preset implemented in
  Python" (.py); unknown/ambiguous names come back in `error`.
- `scene`: `lighting.shadows`, `lighting.multishadow`, `lighting.silhouettes`,
  `lighting.material.specular`, `background.rgb` carry the new values.
- `render` before and after, then `compare_renders` → `changed_fraction` > 0 proves a visible effect;
  after a background change `luminance.contrast_ratio_fg_bg` > 3 and the old background colour
  leaves `palette`. `layout` ignores lighting (flat ID pass); use it only for framing.

## Pitfalls
- `lighting flat` enables silhouettes; `lighting simple|soft|full|gentle` leave them as they are (they
  only restore depthJump 0.03). Turn them off explicitly with `graphics silhouettes false`.
  `lighting simple|default` also switches depth cue back on and resets its colour to the background.
- `preset sil|depth|inter` never touch shadows or intensities; combine with a `lighting` mode.
- Ambient occlusion vanishes on transparent surfaces; they cast no shadows unless
  `material transparentCastShadows true`.
- Fixed `graphics quality` values persist until `graphics quality 1` / `set subdivision 1`.
- Lighting, material, silhouettes and background are per window: another ChimeraX window
  (`connect(pid=…)`) has its own; `~set bgColor` goes to the preference, not to black.
- `--nogui` has no OpenGL on macOS/Windows: `save x.png` fails and `lighting` omits its
  Multishadows line there; check the look in the live window with `render`.

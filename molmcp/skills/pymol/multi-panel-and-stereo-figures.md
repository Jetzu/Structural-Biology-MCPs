---
name: multi-panel-and-stereo-figures
title: Multi-panel and stereo figures
app: pymol
description: Side-by-side comparison panels (grid_mode/grid_slot/grid_max or translate object=), one camera for all panels (get_view/set_view origin swap, matrix_copy), batch rendering at identical size and scale, montage with panel letters, scale bars, stereo pairs via ray angle=
tags: multi-panel, grid_mode, grid_slot, side-by-side, comparison, set_view, matrix_copy, batch render, montage, scale bar, stereo pair
---
Figures with several structures, states or views next to each other, and stereo pairs. Ray settings/dpi:
publication-rendering skill; superposition: structure-alignment; GUI stereo viewing: sequence-view-and-stereo.
Verified on PyMOL 3.1.5 (headless ray). Example: `ref`, `mob` (after `align mob, ref`), map `mob_map` of `mob`.

## 1. One camera for every panel
```pml
matrix_copy mob, mob_map
orient ref and chain A
zoom ref and chain A, 3
set orthoscopic, 1
view fig, store
get_view
```
- Superpose first; `matrix_copy source, target` then gives objects the alignment did not move (ligand copies,
  maps, meshes) the mover's transformation (verified: identical object matrices). Undo: `matrix_reset target`.
- `get_view` = 18 numbers: 0-8 rotation (model -> camera, column-major), 9-11 origin relative to the camera in
  camera space (|11| = camera distance, i.e. zoom), 12-14 origin in model space, 15-16 clip planes, 17 field of
  view with the sign as orthoscopic flag (verified: -20 in perspective, +20 after `set orthoscopic, 1`). Same
  view + same image height = same scale: px per Angstrom = H / (2 * |view[11]| * tan(fov/2)) at the origin plane
  (verified 11.35 px/A at H=400, distance 100, fov 20; exact under `orthoscopic 1`, depth-dependent in perspective).
- Different proteins (not superposed): keep rotation and zoom, swap only the origin per object:
```python
v = list(cmd.get_view())
v[12:15] = cmd.centerofmass("mob")
cmd.set_view(v)
```

## 2. Quick comparison grid (grid_mode)
```pml
set grid_slot, 1, ref
set grid_slot, 2, mob
set grid_mode, 1
zoom all, 4
png grid.png, width=2400, height=800, ray=1
set grid_max, 1
ray 100, 100
set grid_mode, 0
set grid_max, -1
```
- `grid_mode 1` = one slot per enabled object (`grid_slot` -1 = object order, N = explicit), numbered left to
  right then top to bottom; rows x columns follow the image aspect (3 objects: 900x300 -> 1x3, 600x600 -> 2x2
  with an empty cell; 6 at 1800x600 -> 2x3, at 900x900 -> 3x2), so pick width/height for the panel shape you
  want. `grid_mode 2` = one slot per state (single-state objects repeat in every slot), `grid_mode 3` = one per
  object-state.
- All slots share the camera: superposed objects land centred, anything away from the origin is clipped at its
  slot border. `orient`/`zoom` fit the whole frame, not one slot: after switching the grid on, `zoom all, <A>`
  with a growing buffer until `layout` shows no object touching a slot edge.
- `grid_max N` caps the slot count (objects in higher slots vanish; -1 = unlimited).
- Slots are assigned when `set grid_mode, 1` runs: `grid_slot` values changed afterwards are ignored, and objects
  loaded, created or measured afterwards have no slot (drawn once with the whole-frame camera, straddling the
  panels) until you re-issue `set grid_mode, 1` (verified). After that re-issue measurement objects, pseudoatoms
  and labels land in the panel their `grid_slot` names (verified). Scale bars, corner letters: sections 3-4.
- `grid_slot 0` is not "every panel" under ray: the object is drawn once with the whole-frame camera, like an
  unassigned one (verified). To repeat a reference in every panel use `set grid_slot, -2, ref` (verified: one
  copy per slot) or `create ref_2, ref` + `set grid_slot, 2, ref_2`.
- Headless PyMOL (`launch(mode="headless")`, `pymol -c`): after one ray render in grid mode every later render
  keeps the grid layout, even after `set grid_mode, 0` or `reinitialize` (verified). The last four lines above
  (a throw-away one-slot grid render) reset it. The GUI redraw probably resets it: confirm with `compare_renders`.
- Side by side in ONE frame (shared lighting, one scale bar): `translate [40, 0, 0], camera=1, object=mob`
  (display matrix only, coordinates untouched), `zoom all, 4`; undo with `matrix_reset mob, mode=1`.

## 3. Batch rendering (publication path)
```python
import os
panels = "/path/to/panels"; os.makedirs(panels, exist_ok=True)
v = list(cmd.get_view())
for name in ["ref", "mob", "mob_mut"]:
    cmd.disable("all"); cmd.enable(name)
    v2 = list(v); v2[12:15] = cmd.centerofmass(name)   # drop this line when objects are superposed
    cmd.set_view(v2)
    cmd.png(f"{panels}/{name}.png", width=1200, height=900, dpi=300, ray=1)
cmd.enable("all"); cmd.set_view(v)
result = sorted(os.listdir(panels))
```
- Always give both `width` and `height`: `width` alone inherits the viewport aspect (headless 640x480 ->
  600x450, verified) and panels end up with different shapes. Keep `dpi` identical so the montage prints to scale.
- Several views of one object: `scene A, store` ... then `scene A` + `png` per scene (movies-and-scenes skill).
- Montage with panel letters (Pillow 11 is bundled with PyMOL 3.1; run in the `python` tool):
```python
from PIL import Image, ImageDraw, ImageFont
paths = [f"{panels}/{n}.png" for n in ["ref", "mob", "mob_mut"]]
cols, gap = 3, 40
ims = [Image.open(p).convert("RGBA") for p in paths]
w, h = ims[0].size; rows = -(-len(ims) // cols)
sheet = Image.new("RGBA", (cols * w + (cols - 1) * gap, rows * h + (rows - 1) * gap), "white")
font = ImageFont.load_default(size=int(h * 0.06))
for i, im in enumerate(ims):
    x, y = (i % cols) * (w + gap), (i // cols) * (h + gap)
    sheet.paste(im, (x, y), im)
    ImageDraw.Draw(sheet).text((x + 20, y + 10), "ABCDEFGH"[i], fill="black", font=font)
sheet.save("/path/to/figure.png", dpi=(300, 300)); result = sheet.size
```

## 4. Scale bar (10 A along the screen x axis, at the origin depth)
```python
v = cmd.get_view(); o = cmd.get_position()
cmd.pseudoatom("sb1", pos=list(o))
cmd.pseudoatom("sb2", pos=[o[i] + 10 * v[3 * i] for i in range(3)])
```
```pml
distance scalebar, sb1, sb2
set dash_gap, 0, scalebar
set dash_radius, 0.25, scalebar
set dash_color, black, scalebar
hide labels, scalebar
hide everything, sb1 or sb2
label sb2, "10 Å"
show labels, sb2
set label_size, 24, sb2
set label_color, black, sb2
set label_position, [1.5, 0, 0], sb2
translate [-8, -8, 0], sb1 or sb2, camera=1
```
`(v[0], v[3], v[6])` is the camera x axis in model space (verified: horizontal bar, 175 px for 10 A at H=400,
distance 65 A, fov 20 = the section 1 formula; `(v[0], v[1], v[2])` is NOT horizontal). Use `set orthoscopic, 1`
(else exact only at the origin depth); delete `sb1`, `sb2`, `scalebar` after.

## 5. Stereo pairs
```pml
ray 1200, 900, angle=2.1
png left.png
ray 1200, 900, angle=-2.1
png right.png
```
- `ray ..., angle=` rotates about the screen y axis: `+2.1` = left-eye view (near objects shift right, verified
  by parallax), `-2.1` = right eye (PyMOL's `stereo_angle` default is 2.1); `png` without `ray=1` saves that
  buffer. Wall-eye (parallel, the journal standard): left-eye image on the left, centres at most ~6.5 cm apart
  in print; cross-eye: swap. Keep perspective (`orthoscopic 0`) for stereo.
```python
from PIL import Image
L, R = Image.open("left.png"), Image.open("right.png"); gap = 60
pair = Image.new("RGB", (2 * L.width + gap, L.height), "white")
pair.paste(L, (0, 0)); pair.paste(R, (L.width + gap, 0))   # swap L and R for cross-eye
pair.save("stereo_walleye.png", dpi=(300, 300)); result = pair.size
```
- `stereo crosseye|walleye` also apply to ray: `png W, H, ray=1` with one active writes a real pair in one W x H
  image, each eye W/2 wide (verified by parallax, headless too: crosseye = right eye on the left, walleye = left
  eye on the left), so ask for double width; `stereo on` without hardware stereo = crosseye. `stereo sidebyside`
  gives a plain mono image under ray and `anaglyph` a red/cyan composite. Keep `stereo off` for `render`/`layout`.

## 6. Verify
- Grid: `layout(by="object", width=1200, height=400)` -> each object's bbox inside its own slot (slot k of a
  1xN row spans x = (k-1)*W/N .. k*W/N); a bbox touching a slot border or the frame is clipped -> bigger `zoom`
  buffer. `settings(names=["grid_mode", "grid_max", "stereo"])`, `settings(names=["grid_slot"], object="mob")`.
- Panels: `analyze_image(path)` on every PNG -> identical `width`/`height`, `clipped_edges == []`, similar
  `coverage`; `get_view` before each panel -> only the origin (12-14) differs.
- Stereo: `compare_renders("left.png", "right.png")` -> `changed_fraction` small but > 0 (0 = no parallax).
  Grid reset: `render(ray=True)` + `compare_renders` against a pre-grid render -> near 0.

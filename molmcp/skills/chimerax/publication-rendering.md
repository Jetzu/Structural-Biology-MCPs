---
name: publication-rendering
title: Publication-quality rendering
app: chimerax
description: Make a figure-quality image: lighting presets (simple/full/soft/flat), silhouettes, graphics quality, background, window size, and save image with supersampling or a transparent background
tags: rendering, figure, lighting, silhouettes, save image, publication, quality
---
Use this when the user wants a figure, a "nice" picture, a poster/paper panel, shadows, outlines,
a white background or a high-resolution PNG. Syntax verified against the ChimeraX 1.11 command docs.

## 1. Inspect first
- `scene` → `window` (pixel size of the graphics window), `lighting` (key/fill/ambient intensities,
  `shadows`, `multishadow`, `silhouettes`, `material`) and `background`.
- `get_view` if you must reason about or reproduce the camera.

## 2. Frame the scene
```
view                          # fit everything, turns near/far clipping off
view #1/A & protein pad 0.1   # fit a part; pad = free margin as a fraction of the window (default 0.05)
view orient                   # standard orientation (scene X right, Y up, Z towards viewer)
cofr #1:LIG                   # rotate about the ligand from now on
turn y 30; turn x -15         # fine orientation about screen axes (degrees)
camera ortho                  # orthographic (constant scale); `camera mono` restores perspective
windowsize 1200 900           # window = default pixel size and aspect ratio for save/movie
```
Verify with `render`: `coverage` 0.3–0.7 is usually right, `clipped_edges` must be empty, every
entry of `margins_frac` ≥ 0.05, `offset_from_centre_frac` close to 0,0.

## 3. Choose a look
```
set bgColor white                        # or: graphics bgColor white
lighting simple                          # key + fill + ambient, no shadows (= lighting default)
lighting full                            # key light with shadows + ambient occlusion (64 directions)
lighting soft                            # ambient only + ambient occlusion: best for surfaces/spheres
lighting gentle                          # soft tuned for larger indentations (less sooty)
lighting flat                            # ambient only, no shadows, also turns silhouettes ON
lighting shadows true                    # add key-light shadows to the current settings
lighting multiShadow 256 msMapSize 2048  # smoother ambient occlusion (slower; max 1024 directions)
lighting depthCue false                  # no fog (depth cueing fades the back of the scene)
lighting intensity 0.8 ambientIntensity 1.2 fillIntensity 0.3    # manual tuning
graphics silhouettes true width 2 color black depthJump 0.03     # outlines; width in pixels
material dull                            # no specular highlights (material shiny / default)
material specularReflectivity 0.3 exponent 30
```
Presets that combine these: `preset sil` (Publication 1: silhouettes on, depth cue off, white
background), `preset depth` (Publication 2: depth-cued, no silhouettes, white), `preset inter`
(interactive look). Lighting is global; `lighting model #2 shadows false` or
`lighting model #3 directional false` exempts one model.

## 4. Geometry quality
```
graphics quality 2                                   # scale factor for atom/bond triangles + ribbon divisions
graphics quality ribbonDivisions 20 ribbonSides 24   # smoother cartoons (fixed values)
set subdivision 3                                    # smoother sticks/balls/spheres
surface #1 gridSpacing 0.3                           # finer molecular surface (default 0.5 Å)
cartoon style #1 sides 24                            # rounder cartoon cross-section
```
`graphics quality` alone reports the current values; `graphics triangles #1` the triangle count.
Very large systems get slow above quality 2; `graphics quality 1` resets to automatic.

## 5. Save the image
```
save ~/figure.png width 2400 height 1800 supersample 3
save ~/figure.png width 3000 supersample 4 transparentBackground true   # alpha channel (PNG/TIFF)
save ~/figure.png pixelSize 0.1                     # Å per pixel at half depth (same scale across figures)
save ~/figure.tif width 2400 height 1800            # TIFF; .jpg also takes quality 0-100
```
- Without width/height the image has the window's pixel size (2× the window on HiDPI/Retina).
- Give only width (or only height) to keep the window aspect ratio. Giving both with a different
  ratio changes what is in the frame compared with the window and with the `render` analysis.
- `supersample 3` is the default (9 samples per pixel); 1 is fastest; silhouettes get thinner at
  high N (lower it if outlines vanish).
- With a transparent background the background colour is ignored; shadows/silhouettes are kept.

## 6. Verify
- `render` (same aspect ratio as the window, e.g. 800×600 for a 1200×900 window) and read
  `analysis`: `clipped_edges` empty, `margins_frac`, `coverage`, `palette` contains the intended
  colours, `luminance.contrast_ratio_fg_bg` > ~3, `empty` false. `transparent=true` previews the
  alpha version (`background.transparent`).
- `layout by="chain"` → `items[].share_of_frame` and `touches_edges`; `occlusion=true` →
  `occluded_fraction` of the subject (if high, rotate or make the occluder transparent).
- `compare_renders` after a lighting change: `changed_fraction` ≈ 0 means the command had no effect.
- `analyze_image` on the file written by `save` confirms pixel size and content of the final file.

## Pitfalls
- `lighting flat` switches silhouettes on; `lighting simple|full|soft` leave them as they were.
- `transparency` on a surface removes its ambient-occlusion shading; shadows from transparent
  objects are off by default (`material transparentCastShadows true`).
- Depth cueing (on by default) greys out the back of the molecule on a white background:
  `lighting depthCue false` or `preset sil`.
- `windowsize` acts on the live window; in `--nogui --offscreen` ChimeraX pass explicit
  width/height to `save` instead.
- Camera modes other than `mono`/`ortho` (stereo, 360, dome) are not meant for figures.
- The selection outline (green) is rendered into images: `select clear` before saving.

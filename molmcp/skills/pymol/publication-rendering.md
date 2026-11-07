---
name: publication-rendering
title: Publication-quality rendering
app: pymol
description: Ray-traced figure export - ray_trace_mode, antialias, lighting/shadows/ambient occlusion, size and dpi, transparent background, png
tags: rendering, figure, ray, png, export, lighting, dpi, transparent
---
Use this when the user wants a final image (paper, poster, slide). For quick looks use the `render` tool
without `ray`; everything below is about the ray tracer, which is what `png ..., ray=1` and `render(ray=True)` use.
Verified on PyMOL 3.1.5 (incentive build).

## 1. Compose first, render last
1. `scene` -> what is loaded/shown. Hide clutter (`hide everything, solvent`, `hide lines`).
2. Frame it: `orient sel` or `zoom sel, 3` (buffer in Angstrom), `clip slab, 30` to cut depth, `turn y, 20`.
3. Check with `render(width=800, height=600)` (fast, no ray): `clipped_edges` must be empty, `margins_frac`
   roughly balanced (0.03-0.15 each side), `offset_from_centre_frac` near 0. `analysis.coverage` depends on the
   representation: a cartoon of one domain after `orient` fills only 0.08-0.25 of the frame, sticks/lines even
   less, a surface or a large assembly 0.3-0.6; judge framing by margins and clipping, not by a coverage target.
4. Save the camera for later: `view fig, store` (or `get_view` tool -> `set_view` tool).

## 2. Figure settings (one `run` call)
```pml
bg_color white
set ray_opaque_background, 0
set antialias, 2
set ray_trace_mode, 1
set ray_trace_gain, 0.005
set ray_trace_color, black
set ray_shadow, 0
set depth_cue, 0
set fog, 0
set light_count, 2
set specular, 0.2
set spec_count, 1
set ambient, 0.15
set direct, 0.6
set reflect, 0.4
set ambient_occlusion_mode, 1
set ambient_occlusion_scale, 25
set cartoon_sampling, 20
set surface_quality, 1
set hash_max, 300
```
What they do:
- `ray_trace_mode`: 0 normal, 1 colour + black outlines (cartoon-style), 2 black/white outlines (needs white
  background), 3 quantised colour + outlines. `ray_trace_gain` scales outline thickness (default 0.12 is thick;
  0.005-0.05 for large images). Outline colour = `ray_trace_color`.
- `antialias` 0-4 (0 off, 1 adaptive, 2-4 = 2x/3x/4x oversampling plus adaptive; 3/4 are slow). `ray_shadow` 0
  removes shadows (cleaner cartoons); `util.ray_shadows("none")`, `("light")`, `("medium")`, `("heavy")`,
  `("black")`, `("matte")`, `("soft")`, `("occlusion")` are quick shadow/lighting presets (`"occlusion"` is a
  soft 9-light profile; real ambient occlusion is `ambient_occlusion_mode`).
- Lighting: `light_count` 1-10 (more = softer), `ambient`/`direct`/`reflect`/`specular` 0-1, `shininess` 10-90.
  `ambient_occlusion_mode` 1 (atoms) or 2 (triangles) darkens crevices; `ambient_occlusion_scale` 10-50.
- `depth_cue 0` + `fog 0` keep far parts as bright as near ones; `set depth_cue, 1` for depth perception.
- Transparent background: `ray_opaque_background 0` (ray) and `opaque_background 0` (OpenGL draw). Verified: the
  PNG is RGBA with alpha 0 outside the molecule.
- `set orthoscopic, 1` for parallel projection (no perspective distortion, good for scale bars);
  `field_of_view` 10-40 (default 20) controls perspective strength.
- `hash_max` raises the ray-tracer memory limit (300-500 for big surfaces); `max_threads` = CPU cores.

## 3. Export
```pml
png figure.png, width=2400, height=1800, dpi=300, ray=1
png figure_8cm.png, width=8cm, dpi=600, ray=1
ray 1200, 900
png figure_small.png
```
- `png` writes relative to PyMOL's working directory: pass an absolute path or `cd /path/to/dir` first.
- Give `width` only to keep the viewport's aspect ratio; physical units (`8cm`, `3.5in`) require `dpi`.
- `ray W, H` renders into a buffer; a following `png file` (no `ray=1`) saves that buffer unchanged.
- The `render` tool does the same: `render(width=2400, height=1800, ray=True, transparent=True, path="...png")`
  (it sets the opaque-background settings temporarily). It has no dpi argument; use `png` for dpi metadata.
- `save figure.png` is identical to `png figure.png`.

## 4. Pitfalls
- Headless PyMOL (`launch(mode="headless")`) always ray-traces; the OpenGL `draw` path needs the GUI.
- Shader (OpenGL) and ray images differ (shadows, outlines, transparency). Preview with `render(ray=True)` at
  800x600 before the large export.
- Large transparent surfaces + `antialias 3` can take minutes; drop `surface_quality` to 0 for previews.
- `ray_trace_mode 2/3` outlines need a light background; outlines scale with image size - re-tune `ray_trace_gain`.
- Labels: use `label_font_id` 5-15 (scalable) and `set label_outline_color, white` for ray tracing.
- Thin sticks/lines vanish at high dpi: raise `stick_radius` (0.25-0.3) and `line_width` (2-3), or use sticks.
- `viewport W, H` changes the GUI window size (aspect ratio), not the export size.
- Reset for interactive use afterwards: `set ray_trace_mode, 0`, `set ambient_occlusion_mode, 0`.

## 5. Verify
- `render(ray=True, width=800, height=600)`: check `analysis.clipped_edges == []`, `coverage`, `palette`
  (dominant named colours - the colours you expect), `luminance.contrast_ratio_fg_bg` (>3 on white),
  `background.name` (`white` or `transparent`).
- `analyze_image(path)` on the exported file confirms `width`/`height` and the same metrics.
- `compare_renders()` after a settings change: `changed_fraction` near 0 means the change had no visible effect.
- `settings(names=["ray_trace_mode", "antialias", "ray_opaque_background", "light_count", "ambient_occlusion_mode"])`
  confirms the values actually in effect (object-level overrides: `settings(names=[...], object="prot")`).

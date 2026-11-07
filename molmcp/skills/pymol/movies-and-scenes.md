---
name: movies-and-scenes
title: Movies and scenes
app: pymol
description: scene store/recall/update, movie frames (mset, mview keyframes, movie.add_* helpers, mdo), turntable and rock, state sweeps, frame export with mpng (ray) and encoding to mp4 with ffmpeg
tags: movie, scene, animation, mset, mview, mpng, turntable, frames, export
---
Scenes = named snapshots of camera + visibility + colours + reps (`scene`). Movies = a frame list (`mset`)
with camera keyframes (`mview`) and/or per-frame commands (`mdo`). Example object `prot`.

## Scenes
```pml
scene F1, store
turn y, 90
scene F2, store, Rotated 90 degrees
scene F1
scene F2, recall
scene F2, update
scene F1, rename, new_key=overview
scene new, store
scene F2, clear
set scene_animation_duration, 1.5
```
- `scene key, store` (key `new` auto-numbers; `F1`-`F12` bind to function keys), `recall` (default action),
  `update` (overwrite with the current state), `clear` (delete one; `scene *, clear` deletes all), `rename`,
  `insert_after`/`insert_before`, `next`/`previous`. The optional message is shown on playback.
- Scene recall animates the camera (`scene_animation_duration`); `set scene_animation, 0` for instant switches.
- `view key, store` / `view key` stores only the camera (no colours/reps).

## Movie basics
```pml
mset 1 x90
movie.roll 1, 90, 1, y
set movie_fps, 30
frame 1
```
- `mset 1 x90` = 90 frames all showing state 1. State sweeps: `mset 1 -30 30 -1` (states 1..30 and back),
  `mset 1 x30 1 -15 15 x30`. `madd 1 x30` appends frames. `mclear` clears cached frames, `mset` alone resets.
- Turntable: `movie.roll first, last, loop, axis` (full 360 over the range); `movie.rock 1, 90, 30` rocks +-30
  degrees; `movie.nutate 1, 90, 30`; `util.mroll 1, 90, 1` / `util.mrock 1, 90, 30` are equivalents.
- Legacy per-frame commands: `mdo 1: turn y, 3` (colon syntax; `mdo 1, ...` is invalid).
- Playback for the user: `mplay`, `mstop`, `frame 45`, `rewind`; `set movie_loop, 0` plays once;
  `set movie_panel, 1` shows the timeline.

## Keyframe camera movies (smooth, recommended)
```pml
mset 1 x120
orient prot
mview store, 1
turn y, 120
zoom prot and chain A, 5
mview store, 60
turn y, 120
orient prot
mview store, 120
mview reinterpolate
```
- `mview store, N` stores the current camera at frame N (and `scene=name` stores a scene switch at that
  frame; `object=prot` stores object motion); `mview reinterpolate` builds smooth interpolation (`power`/`bias`
  control easing); `mview clear` removes all keyframes.
- Scene-based movies with helpers (Python-call syntax, each appends frames to the movie):
```pml
mset 1 x1
movie.add_scenes(pause=4, loop=1)
movie.add_roll(8, loop=1, axis="y")
movie.add_rock(4, angle=30, loop=1)
movie.add_nutate(4, angle=15, loop=1)
movie.add_state_sweep(factor=1, pause=1)
```
Durations are seconds at `movie_fps`; `movie.add_scenes(["overview", "F2"], pause=4)` plays specific scenes
in order. Check the total with `python`: `result = cmd.count_frames()`.

## Export frames and encode
```pml
set ray_trace_frames, 1
set cache_frames, 0
set seq_view, 0
mpng frames/turn_, 1, 90, width=1280, height=720, mode=2
```
- `mpng prefix, first, last, width=, height=, mode=` writes `prefix0001.png`... `mode=2` ray-traces every
  frame (slow but GUI-independent), `mode=1` uses OpenGL draw (fast; GUI only - fails headless with
  "Missing rendered image"). The directory must exist; paths are relative to PyMOL's cwd (`cd` first).
- Ray settings from the rendering skill apply to every frame; keep `antialias 1` for speed.
- `movie.produce turntable.mp4, height=720, quality=90` encodes directly but needs `ffmpeg` (or ImageMagick
  `convert`) on PATH - not bundled with PyMOL 3.1 on macOS (verified: "neither ffmpeg nor convert available").
  Encode the PNGs yourself instead:
  `ffmpeg -framerate 30 -i frames/turn_%04d.png -c:v libx264 -pix_fmt yuv420p -crf 18 turntable.mp4`
  (even width/height required by yuv420p). GIF: `ffmpeg -i frames/turn_%04d.png -vf "fps=15,scale=640:-1" out.gif`.
- Single frame as a still: `frame 45` then `png frame45.png, ray=1`.

## Pitfalls
- `mset` resets `mdo` commands and keyframes; set up frames first, then keyframes.
- `mview store` without `mset` stores nothing useful - define the frame count first.
- Scenes store colours/visibility; after `scene X` your later `color`/`show` changes are lost on the next
  recall unless you `scene X, update`.
- `seq_view` conflicts with `mpng` (PyMOL disables it with a warning); turn it off before export.
- Each ray frame at 1280x720 takes ~0.5-2 s for a small protein, much more with surfaces: test `mpng ..., 1, 3`
  first and extrapolate.

## Verify
- `scene` -> `frames` (count), `frame` (current), `scenes` (names). After `frame 45` + `render()` +
  `compare_renders()` against the frame-1 render, `changed_fraction` > 0 confirms camera motion.
- `python`: `import os; result = sorted(os.listdir("frames"))[:5]` to confirm written files;
  `result = cmd.get_scene_list()` for scenes.
- `analyze_image("frames/turn_0001.png")` checks frame size and that the content is not clipped (`clipped_edges`).

---
name: movies
title: Recording movies
app: chimerax
description: Script and record movies: movie record/encode options, turn/roll/rock/wobble motions, wait for ordering, perframe loops, crossfade, named views and fly paths, trajectory playback (coordset) and morphs
tags: movie, animation, turn, roll, rock, perframe, wait, fly, morph, coordset, video
---
Use for "make a spinning movie", "animate the transition", "record a fly-through". Movies need a
graphics window (GUI) or Linux `--nogui --offscreen`. Syntax verified against the ChimeraX 1.11 docs.

## 1. Recipe (send as ONE `run` call with a list of commands, or a .cxc file)
```
windowsize 1280 720                  # frame size = window size unless `size` is given
lighting soft; graphics silhouettes true; set bgColor white
view; view name start
movie record supersample 3           # capture every frame from now on (PNG frames, 3 = smooth edges)
turn y 2 180                         # 2° per frame × 180 frames = one full turn
wait 180                             # block until the turn finished (plain `wait` also works after turn/roll/move/zoom/view/fly)
wait 10                              # a few static frames so the end is not blurred
movie encode ~/Desktop/spin.mp4 quality high framerate 25
```
`movie encode` stops recording, runs the bundled ffmpeg and deletes the frames. `movie status`
reports the frame count; `movie stop` / `movie reset` abandon a recording; `movie abort` cancels
encoding; `movie formats` lists formats.

## 2. movie options
```
movie record supersample 3 size 1920,1080 format png directory ~/frames pattern frame-* limit 5000
movie encode ~/out.mp4 format h264 quality highest framerate 30 roundTrip true
movie encode ~/out.webm                       # formats: h264 (.mp4) vp8/webm theora/ogv mov avi wmv apng
movie encode ~/out.mp4 bitrate 25000          # constant bit rate (HD); qscale 1-31 alternative
movie encode ~/out.mp4 resetMode keep         # keep the PNG frames on disk
movie encode ~/out.mp4 wait true              # block until encoding finished (needed before a second recording)
movie crossfade 25; movie duplicate 25        # dissolve / hold inside a recording (only visible in the file)
```
`transparentBackground true` only affects the PNG frames, never the encoded movie.

## 3. Motion commands (counts are frames; playback fps is set at encode time)
```
turn y 1 360                        # axis angle frames (defaults 90°, 1 frame)
roll y 1 360                        # like turn; default 1° per frame forever → give frames or `stop`
rock y 30 272 cycle 136             # wag ±30°, 136 frames per cycle, for 272 frames
turn y 1 360 center #1:LIG          # about a point; `cofr #1:LIG` does it persistently
turn y 1 360 models #2 center #2    # rotate one model about its own centre (side-by-side spins)
move x 10 50                        # translate 10 Å over 50 frames (screen axes)
zoom 1.5 frames 50                  # magnify ×1.5 over 50 frames (frame count needs the keyword)
view name v1 … view v1 60           # saved views; `view v1 60` interpolates camera, model positions and clip planes
fly 60 start v1 v2 v3               # smooth path through several named views, 60 frames per leg
crossfade 30; hide ligand; wait 30  # dissolve between two appearances (same size as window only)
```
Put `wait N` after each motion (or `wait` without a number after turn/roll/rock/move/zoom/view/fly).

## 4. Per-frame changes
```
perframe "volume #2 level $1" range 0.3,0.05 frames 50; wait 50; ~perframe
perframe "color /A $1,$2,$3" range 100,0 range 0,0 range 0,100 frames 30; wait 30; ~perframe
perframe "hide protein; show :$1" range 17,355 interval 10; wait 340; ~perframe
perframe "turn y 2; save ~/frames/$1.png width 800" frames 180 zeroPadWidth 3   # image series instead of a movie
perframe dssp interval 5; coordset #1 1,200; wait 200; ~perframe
```
Several commands inside the quotes are separated by `;`. Always finish with `~perframe`.

## 5. Trajectories and morphs
```
coordset #1 1,100                  # play frames 1→100 (one per graphics frame); `coordset #1 50` jumps
coordset #1 1,100 pauseFrames 3    # slower; `loop 3 bounce true` repeats back and forth
coordset #1 1,100 holdSteady @CA computeSs true
coordset slider #1                 # GUI slider with a record button
morph #1,2 frames 60 wrap true     # trajectory model between conformations (matchmaker them first)
morph #1,2,3 frames 40 same true   # identical numbering/naming (NMR ensemble style)
```
Record as in section 1: `movie record; coordset #3 1,121; wait 121; movie encode ~/morph.mp4`.

## 6. Verify
- `run` → `output` of `movie status` ("N frames"), of `movie encode` (file name); then check the
  file with `python`: `import os; result = os.path.getsize(os.path.expanduser('~/Desktop/spin.mp4'))`.
- Before recording, `render` at the movie aspect ratio; `clipped_edges` must stay empty throughout
  the motion — for a spin check the widest orientation (`turn y 90`, `render`, `turn y -90`).
- `events` lists "command failed" entries if a script line errored (recording continues regardless).

## Pitfalls
- No implicit `wait`: without it `movie encode` runs before the motion ends (0 or few frames).
- One `run` call blocks the bridge until all commands finished; the `run` tool times out after
  600 s — split long movies into several calls and encode with `wait true` last.
- `size` with another aspect ratio than the window shows more/less of the scene than `render` did.
- `roll`/`rock` without a frame count run forever; `stop` halts them.
- `lighting full|soft` + `supersample 3` is slow for big systems; test with `supersample 1`.
- Recording while the user interacts captures their mouse moves too (`events` shows them).

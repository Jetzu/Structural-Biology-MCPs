---
name: performance-and-large-systems
title: Performance and large systems
app: pymol
description: Keep PyMOL responsive and ray tracing bounded on viruses, ribosomes, assemblies and trajectories - trim before building reps, defer_builds_mode/async_builds, cartoon_sampling/surface_quality/sphere_mode, hash_max/antialias/thread budgets, memory, layout checks on 50+ chains
tags: performance, large, memory, trajectory, defer_builds_mode, async_builds, hash_max, surface_quality, cartoon_sampling, sphere_mode, ray, threads
---
Use this when an object has > ~100k atoms, > 20 chains or > 50 states, or when `run`/`render` calls take more than
~10 s. Timings below: PyMOL 3.1.5, 12 cores (`max_threads` 12), 25k-atom spike (6vxx), 240k-atom ribosome (4v6x),
40-state x 24k-atom trajectory. Figure-quality ray settings are in publication-rendering, surface details in
surfaces-and-electrostatics, `util.performance` presets in styling-presets, trajectories/movies in movies-and-scenes.

## 1. Measure before tuning
- `scene` -> `atoms`, `states` and the `chains` list per object. With 50+ chains call
  `scene(detail="summary", objects=["big"])`; `detail="full"` adds per-chain residue ranges, hetero groups and
  representation counts for every chain (large output on an 89-chain ribosome).
- `ray 400, 300, renderer=2` is a dry run: it prints `RayRenderTest: obtained N graphics primitives.` and renders
  nothing. The line comes back in the `run` response's output (in the GUI `log(n=5)` also shows it; headless
  PyMOL prints feedback straight to stdout, which only the `run` output captures). N ~25k (all-atom spheres of
  a 25k-atom object) renders in seconds; N > 1M (ribosome cartoon 1.3M, `surface_quality 1` on a few chains)
  means minutes per image.
- Memory from the `python` tool (PyMOL's Python ships no psutil; `resource` is Unix-only):
```python
import os, sys
try:
    import psutil; result = psutil.Process(os.getpid()).memory_info().rss / 1e6
except ImportError:
    import resource; r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result = r / 1e6 if sys.platform == "darwin" else r / 1e3   # MB, peak RSS
```

## 2. Before loading something huge
```pml
set auto_show_classified, 0
set auto_show_lines, 0
set auto_show_nonbonded, 0
set auto_zoom, 0
set defer_builds_mode, 3
load /path/huge.cif, big
remove big and solvent
remove big and hydro
remove big and not (polymer or organic)
show cartoon, big and chain A+B
```
- PyMOL 3.x auto-shows cartoon/sticks/spheres by classification on load (`auto_show_classified -1`), so a 240k-atom
  cif immediately builds a 240k-atom cartoon in the GUI. With the auto-shows off you trim first, then show what matters.
- `remove` frees atoms (memory, selection and bonding cost); `hide` does not. `set assembly, 1` and `symexp`
  multiply atoms - check `scene` after them.
- Trajectories: subsample at load, `load_traj traj.dcd, big, interval=10, start=1, stop=5000, max=500`; drop frames
  later with `delete_states big, 201-1000`. `remove big and not polymer` BEFORE `load_traj`, not after.
- Only the chains you need: `create core, big and chain A+B+C` then `disable big` - a disabled object is neither
  built nor drawn. `extract core, big and chain A+B+C` moves the atoms instead (no double memory; 6 s for 87k atoms).

## 3. Multi-state objects: defer_builds_mode and async_builds
- `defer_builds_mode` (global or `, obj`): 0 (default) builds and caches the geometry of ALL states on the first draw
  (40 states x 24k atoms cartoon: 7.8 s, +850 MB); 1 builds the current state when first needed and keeps it;
  2 builds on demand and keeps only the current state (also for disabled objects); 3 = 2 but builds enabled
  objects only (lowest memory of 0-3; what PyMOL's own File > Load Trajectory dialog sets); 5 = 3 plus
  immediate-mode OpenGL: only lines, nonbonded, spheres, sticks and ribbon are drawn in the viewport (cartoon and
  surface show up only in `ray`), lowest memory, ~2x slower per state change in the test. Loading an object with
  >= `auto_defer_builds` (500) states switches the global setting from 0 to 3 automatically (a non-zero value
  is left alone; `auto_defer_builds -1` disables this).
- Mode 3 costs a rebuild per state change (~1 s per state for a 24k-atom cartoon): scrubbing is slower, `mpng` is
  fine. Set it before loading; if geometry is already cached, `set defer_builds_mode, 3` then `rebuild` purges it.
- `set async_builds, 1`: the per-state geometry builds of a multi-state object run in parallel on `max_threads`
  threads (with defer modes >= 1 it prebuilds the block of `max_threads` states around the current one). Measured:
  40-state first build 7.8 s -> 2.3 s, peak memory 1.06 -> 1.8 GB because states build concurrently. No effect on
  single-state objects or on ray tracing. Use it when every frame must be built anyway (movie export, smooth
  playback with `defer_builds_mode 0`) and RAM allows; with little RAM use `defer_builds_mode 3` and leave it off.
  PyMOL's own setting help warns it "can create instability and should be used with caution": if PyMOL crashes
  during a build, `set async_builds, 0` and `rebuild`.

## 4. Representation cost knobs
- `cartoon_sampling` -1 (default) = auto: 7 segments per residue below 100k atoms per state, 5 below 500k, 3 below
  1M, 2 above. Explicit 3 cuts cartoon primitives ~2.3x (264k -> 116k for 25k atoms), 1 ~6x. Values >= 10 only for
  close-ups. `ribbon` is ~45x cheaper than cartoon for the same atoms (5.8k vs 264k primitives) - use it for context.
- `surface_quality` -4..4 (official range; 3 is "nearly impractical" and 4 "totally impractical" in the source -
  4 hung for minutes on 660 atoms): grid 0.125 A at 2, 0.25 A at 1, 0.5 A at 0, 0.85 A at -1, 1.3 A at -2,
  2 A at -3, 2.4 A at -4. 8k-atom surface build+ray: -2 5 s, -1 6.7 s,
  0 8.5 s, 1 141 s (+700 MB). Keep 0 on big surfaces, -1/-2 for previews, and surface only the chains that matter
  (`show surface, big and chain A`). Millions of atoms: a Gaussian map of the CA atoms instead of a real surface,
  `map_new gmap, gaussian, 3, big and name CA, 10` then `isosurface gsurf, gmap, 1` (0.03 s for 3k CA atoms).
- `sphere_mode` (OpenGL only - the ray tracer always draws exact spheres): 9 = GLSL impostors (default with
  `use_shaders 1`, millions of atoms are fine; falls back to 0 without shaders), 0 = triangle meshes
  (`sphere_quality` 0-4, PyMOL clamps higher values; 1M atoms x quality 2 exhausts GPU memory), 1-3 = flat point
  sprites (square / scaled / circle) for weak GPUs or remote desktops, 6-8 = 1-3 with fake lighting, 4 and 5 are
  removed (treated as 9; 5 prints a one-time warning), 10/11 = cube/tetrahedron stand-ins (3.x).
- `util.performance(100)` (Display > Quality > Maximum Performance) = `surface_quality -1`, `cartoon_sampling 3`,
  `ribbon_sampling 1`, `stick_quality 5`, `sphere_quality 0`, `antialias_shader 0`, `line_smooth 0`, `specular 0`,
  `depth_cue 0`, `transparency_mode 0`, `max_ups 0` + `rebuild`. `util.performance(0)` is NOT a reset: it is the
  Maximum Quality preset (`surface_quality 1`, `cartoon_sampling 14`, `stick_quality 15`, `sphere_quality 2`),
  slower than the defaults; `util.performance(33)` (Reasonable Quality: `surface_quality 0`, `cartoon_sampling 7`)
  is the sane way back. `util.modernize_rendering(1)` switches every representation to shaders, `sphere_mode 9`,
  `stick_as_cylinders 1` and `max_ups 0`.

## 5. Ray-tracing time budget
```pml
set max_threads, 12
set hash_max, 170
set antialias, 0
ray 400, 300
```
- Time scales with primitives x pixels x antialias passes x shadow/transparency passes, divided by `max_threads`
  (default = CPU count; `max_threads 1` was 3.6x slower). Preview at 400x300 with `antialias 0`. Pixels scale
  sub-linearly (1600x1200 took 5x the 400x300 time); expect 10x+ for a 2400x1800 final and tell the user first.
- `hash_max` = ray-tracer voxel grid; memory grows with hash_max^3 (`help faster`: 80 -> 9 MB, 160 -> 72 MB,
  240 -> 243 MB). 170 (the GUI's "Use More") won every test: 25k-atom cartoon+sticks 1600x1200 13 s at 100, 7.4 s at
  170, 8.6 s at 300 (+300 MB); ribosome cartoon 800x600 44 s -> 33 s. 300+ was equal or slower, and 500 made a
  cheap sphere render 14x slower (grid setup dominates). Raise it only for renders that take > 10 s.
- `antialias 0` ~0.5x, `antialias 2` ~1.3x the time of 1 (3-4 much more). `ray_shadow 0` ~0.5x. `light_count 8`
  cost +370 MB (one shadow map per light) but little time. `transparency` > 0 on a surface doubled the time
  (12 -> 28 s); `ambient_occlusion_mode 1` and `ray_trace_mode 1` were cheap (< 1.3x). Ribosome cartoon 800x600:
  44-60 s, `antialias 0` 30 s; all-atom spheres 14 s.
- Headless PyMOL always ray-traces, so even `render(ray=False)` costs the above; in the GUI `render()` is an OpenGL
  draw and is the right tool for layout checks on huge scenes. `ray ..., async=1` (background thread) is for the
  user's own interactive use - through the bridge prefer one blocking `png file, width=..., height=..., ray=1`.

## 6. Memory
- `set pse_binary_dump, 1` before `save big.pse`: ribosome session 94 s / 87 MB -> 2.4 s / 43 MB. PyMOL's setting
  help marks it "Unsupported" and older PyMOL versions cannot read the file (see sessions-and-export), so leave it
  off for sessions you hand to others.
- `cache clear` drops cached surfaces (`cache_max`, default ~100 MB); `delete` unused objects and selections;
  `reinitialize` starts clean. After a crash or swapping, lower in this order: `hash_max` (100), `light_count` (2),
  `async_builds` (0), `surface_quality` (-1), then `defer_builds_mode 3` and `remove` atoms.

## 7. Verify
- `settings(names=["defer_builds_mode", "async_builds", "cartoon_sampling", "surface_quality", "sphere_mode",
  "hash_max", "max_threads", "antialias"])`; `object_info("big")` -> `setting_overrides` for object-level values.
- `scene(detail="summary")` -> atoms/states per object, and that the trimmed object is enabled while the big one is not.
- `layout(by="chain")` silently keeps only the first 60 items: on an 89-chain ribosome use `layout(by="items",
  items=["big and polymer.nucleic", "big and polymer.protein", "core"], width=400, height=300)`; avoid
  `occlusion=True` (one extra render per item).
- `compare_renders()` after lowering `cartoon_sampling`/`surface_quality`/`antialias`: `changed_fraction` < 0.05 at
  the target size means the cheaper setting is visually equivalent - keep it.
- `measure(kind="count", selection1="big and name CA")` and `residue_table(selection="big and chain A and name CA",
  max_rows=200)`: always restrict the selection on huge objects; `log(n=5)` after `ray ..., renderer=2` for the
  primitive count.

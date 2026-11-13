# molmcp in detail

Reference material moved out of the README: what the servers give an agent, the full tool table, environment
variables, how the pieces talk to each other, PyMOL quirks the bridge works around, what has been verified on which
platform, and development notes. Installation is in [SETUP.md](SETUP.md); the in-app chat in
[agent-chat.md](agent-chat.md); the per-command coverage audit in [FEATURE_COVERAGE.md](FEATURE_COVERAGE.md).

## What the servers give an agent

Two independent [MCP](https://modelcontextprotocol.io) servers, `pymol-mcp` and `chimerax-mcp`. Each talks to a
small bridge that runs *inside* the viewer (a PyMOL plugin / a ChimeraX bundle):

* **Fast, synchronous command execution** over a persistent localhost connection (about 0.2 ms overhead per call).
  A batch of commands returns per-command output and errors, plus a list of what actually changed.
* **Full state awareness**: structured snapshots of objects/models, chains, representations, colours, selections,
  camera, lighting and settings, and an event stream of what the user typed or changed in the GUI.
* **Render analysis without a vision model**: every render is described numerically (coverage, bounding box,
  centroid offset, which frame edges clip the content, free margins, dominant *named* colours, contrast, an ASCII
  density map). An **ID pass** reports per object or chain whether it is visible, its screen share, 2D contacts and
  occlusion. Renders can be diffed to confirm that a change took effect.
* **In-tool integration**: the bridge starts with the application. PyMOL gets `agent_status`, `agent_start`,
  `agent_stop` (and a Plugin-menu entry); ChimeraX gets `agent status|start|stop`. The MCP server can also launch
  the application itself, with a window or headless.
* **Skills**: 43 reviewed instruction files the agent reads on demand (`skills`, `skill`): publication rendering,
  representations and colouring, selections and atom specs, surfaces and electrostatics, alignment, movies and
  trajectories, maps and cryo-EM, ligand sites and docking poses, hydrogen bonds, contacts and interfaces,
  AlphaFold, mutagenesis, symmetry and assemblies, markers, attributes, presets and lighting, multi-panel figures,
  large systems, sessions and export. Add your own under `~/.molmcp/skills/<app>/`, or let the agent store one
  with `save_skill`; user files override built-ins.
* **Structured helpers** for the questions agents ask most: `measure` (distance, angle, dihedral, extent, RMSD,
  count, SASA), `align` + `alignment_info` (RMSD, atom counts and the residue pairs behind them), `sequence`,
  `contacts` (residue pairs, polar-only option), `residue_table` (per-residue secondary structure, B-factor or
  pLDDT, shown representations, colours), `mutate` (rotamer-aware point mutations), `map_info` / `set_isolevel`
  (PyMOL density levels), `set_setting`, `set_view` and `wait_for_jobs` (ChimeraX), `save_file`. Everything else
  in either program stays reachable through `run` (any command) and `python`.
* **Several windows**: every PyMOL or ChimeraX window is its own session with its own bridge. `status` lists them
  with their loaded objects, name and which one has focus. The server connects to the window you are working in
  and names it in every reply while more than one is open; `connect(pid=...)` / `connect(name=...)` switch. Name a
  window with `agent_name mywork` (PyMOL) or `agent name mywork` (ChimeraX).

Only the standard library plus numpy and Pillow (both shipped with the viewers) run inside the applications; the
servers need Python 3.10 or newer.

## Typical agent flow

Open PyMOL or ChimeraX (the bridge starts automatically; `agent_status` / `agent status` shows the port), or let
the agent call `launch`. Then:

1. `status`: is a bridge running, which process, where renders go.
2. `scene`: what is loaded and shown (objects/models, chains, representations, colours, camera).
3. `run`: commands; read `changes` to see what happened.
4. `render` / `layout`: numerical description of the picture; `compare_renders` to verify a change.
5. `events` / `log`: what the user did in the GUI in the meantime.

## Tools (both servers)

PyMOL exposes 34 tools, ChimeraX 31.

| tool | purpose |
|------|---------|
| `status`, `launch`, `connect` | discover / start / pick a viewer process (several can run at once) |
| `run` | execute viewer commands; per-command ok/output/error + scene changes (ChimeraX: `json=True` returns structured values for the commands that provide them); quitting, reset and shell commands need `allow_dangerous=True` |
| `python` | run Python inside the viewer (`cmd`/`pymol` or `session`/`run`), return `result` |
| `scene` | structured state snapshot (`detail="full"` adds per-chain details) |
| `object_info` / `model_info` | everything about one object / model |
| `selection_info` | what a selection or atom spec matches (counts, ranges with insertion codes, names, centre) |
| `get_view` (+ `set_view`) | camera |
| `render` | render + analysis (coverage, bbox, clipping, margins, named colours, contrast, ASCII map); PNG saved to `~/.molmcp/renders` |
| `layout` | ID-pass render: which objects/chains are visible where, screen share, 2D contacts, optional occlusion |
| `compare_renders`, `analyze_image` | diff two renders; analyse any PNG on disk |
| `events`, `log` | activity since the last call (paged, with error text); viewer log |
| `help`, `commands` | command documentation / list |
| `skills`, `skill`, `save_skill` | instruction files for common jobs; add your own |
| `measure`, `align`, `alignment_info`, `sequence`, `contacts`, `residue_table`, `mutate`, `save_file` | structured helpers with JSON results |
| `map_info`, `set_isolevel`, `set_setting` (PyMOL); `set_view`, `wait_for_jobs` (ChimeraX) | density levels, settings writes, camera round-trips, background jobs |
| `settings` (PyMOL) | read settings, globally or per object |
| `quit_pymol` / `quit_chimerax` | terminate the viewer (needs `confirm=True`) |

## Environment variables

| variable | meaning |
|----------|---------|
| `MOLMCP_HOME` | state directory (default `~/.molmcp`): bridge discovery files, renders, build artefacts, fetched structures of headless sessions |
| `MOLMCP_OUTPUT_DIR` | where `render` writes PNGs (default `$MOLMCP_HOME/renders`) |
| `MOLMCP_AUTOLAUNCH=0` | never start the viewer automatically from a tool call |
| `MOLMCP_APP_CWD` | working directory for viewers started by `launch` (default: your home directory) |
| `PYMOL_EXE`, `CHIMERAX_EXE`, `PYMOL_PYTHON` | explicit executables (headless PyMOL uses a Python that imports PyMOL as a library) |
| `MOLMCP_PYMOL_PORT`, `MOLMCP_CHIMERAX_PORT` | fixed bridge ports (default: random free port) |
| `MOLMCP_PYMOL_AUTOSTART=0`, `MOLMCP_CHIMERAX_AUTOSTART=0` | don't start the bridge with the application |
| `MOLMCP_PYMOL_FORCE_DRAW=1`, `MOLMCP_PYMOL_FORCE_RAY=1` | override the OpenGL probe for GUI renders (see below) |
| `MOLMCP_CLAUDE_EXE`, `MOLMCP_CODEX_EXE` | which CLI the in-app chat runs |

## How it works

```
Claude Code / Codex ──stdio──> pymol-mcp    ──HTTP (127.0.0.1, token)──> bridge thread in PyMOL    ──> PyMOL main thread
                    ──stdio──> chimerax-mcp ──HTTP (127.0.0.1, token)──> bridge thread in ChimeraX ──> Qt main thread
```

* Each bridge binds a random localhost port, generates a token and writes `$MOLMCP_HOME/instances/<app>-<pid>.json`.
  Servers discover live bridges from these files; files whose process is gone, or whose pid now belongs to a
  newer process, are removed. Requests are JSON (`{"op": ..., "args": ...}`); images travel as base64 PNG.
* Operations run on the application's main thread (PyMOL `MainThreadCaller`, ChimeraX `ui.thread_safe`), so GUI,
  rendering and command execution stay consistent with what the user sees.
* Render analysis (`molmcp/common/imageanalysis.py`) is pure numpy: background estimation, foreground mask,
  bounding box, centroid and edge coverage, a Lab-space nearest-named-colour palette, hue shares, WCAG contrast and
  an ASCII occupancy grid. The ID pass recolours each item flat (ambient-only lighting, no fog, shadows or
  transparency) and restores every colour, setting, representation and selection afterwards (verified by re-render
  diff).
* Headless PyMOL runs PyMOL as a library inside a Python that can import it (no busy keep-alive loop); headless
  ChimeraX needs Linux with `--offscreen` for rendering.

## PyMOL quirks the servers work around

* **Licence banner.** A PyMOL without a valid (or with an expired) licence burns "No License File - For Evaluation
  Only" into every ray-traced frame. The bridge reports this (`status.watermark`), and `render`, `layout`,
  `analyze_image` and `compare_renders` detect the grey text band and exclude it from the numbers (the PNG keeps it).
* **Undo history vs. reused object names (PyMOL 3.1.5).** Once the undo history is active, `delete x` followed by
  reloading an object named `x` leaves that object unselectable ("Invalid selection name") after about 30 further
  undoable commands. Headless sessions keep undo disabled; in the GUI the bridge clears the undo cache whenever an
  agent command removed objects. If you hit it yourself in the GUI, run `undo_clear_cache`.
* **Headless feedback.** Command output such as `Executive: RMSD = ...` goes to the process's C-level stdout; the
  bridge captures it per command so `run` and `log` show it.
* **Weak OpenGL (VMs, remote desktops, CI).** On contexts without shader support (PyMOL turns `use_shaders` off,
  e.g. Microsoft's "GDI Generic" OpenGL 1.1) an offscreen `draw` crashes PyMOL, and so does `scene ... store` (it
  renders a thumbnail). The bridge then renders with the CPU ray tracer (`fallback` in the reply) and the ID pass
  saves and restores state without scenes.

ChimeraX note: `view` frames for the window's aspect ratio. Rendering at a different aspect (for example 1600x1200
from a wide window) can clip the top and bottom; `render` reports this as `clipped_edges`, and `windowsize` with the
render's aspect avoids it.

## What has been verified where

| | macOS | Linux | Windows |
|---|---|---|---|
| PyMOL GUI: run / scene / render / layout / events / compare | tested, PyMOL 3.1.5 | n/a (no display) | tested on a GitHub Actions `windows-latest` runner: Qt window launched by the server, status/run/scene, render and ID pass (ray-tracer fallback, the runner only has OpenGL 1.1), quit |
| PyMOL headless (library mode, ray renders) | tested (incentive PyMOL 3.1.5 and open-source PyMOL 3.1) | tested, open-source PyMOL 3.1 from conda-forge | tested on the Windows runner (Python 3.11 + open-source PyMOL 3.2 wheel): MCP stdio client -> server -> headless PyMOL launched by the server, run/scene/render/quit |
| PyMOL plugin install through PyMOL's plugin prefs | tested | tested | tested (`%APPDATA%\pymol\startup`) |
| Installer: detection, venv, console scripts, Claude/Codex config files | tested | tested | tested |
| Unit + platform tests (58) | pass | pass (CI) | pass (CI) |
| ChimeraX GUI: run / scene / render / layout / events / compare | tested, ChimeraX 1.11.1 | n/a (no display) | not run: the ChimeraX installer needs a licence click-through, so CI cannot install it. On the runner `chimerax-mcp.exe` serves all tools, `status`/`skills`/`skill`/`analyze_image` work without the app, and the bundle wheel builds |
| ChimeraX headless `--nogui --offscreen` via MCP | not possible on macOS (ChimeraX: "running without graphics") | tested in UCSF's official `ucsfrbvi/chimerax` image as a normal user | not possible |
| ChimeraX bundle install + autostart + `agent`/`claude`/`codex` commands | tested | tested (same image) | not tested |
| Live Claude Code and Codex sessions calling the tools on both servers | tested (Claude Code 2.1.319, Codex CLI 0.160.0) | configs written and parsed | configs written and parsed |
| In-app chat with both backends changing the live scene | tested | not run | not tested |
| Red-team QA: 24 scenario agents plus a second round, every critical/major report reproduced before fixing ([FEATURE_COVERAGE.md](FEATURE_COVERAGE.md)) | done | PyMOL headless scenarios | not run |

The CI workflow ([.github/workflows/ci.yml](../.github/workflows/ci.yml)) runs on every push: Linux unit tests, a
Windows job with the installer, unit tests, the headless PyMOL end-to-end run and the ChimeraX server checks, and a
second Windows job that drives the PyMOL GUI. Earlier, the Windows code paths were also exercised under Wine
(`tests/docker/Dockerfile.windows-wine`).

### Linux containers

```bash
# open-source PyMOL from conda-forge, headless; runs installer, unit tests and the full MCP e2e
docker build --platform linux/amd64 -f tests/docker/Dockerfile.pymol-linux -t molmcp-pymol-linux .
docker run --rm --platform linux/amd64 molmcp-pymol-linux

# ChimeraX headless with offscreen rendering, from UCSF's official headless image (multi-arch, no click-through):
docker build -f tests/docker/Dockerfile.chimerax-official -t molmcp-chimerax-official .
docker run --rm molmcp-chimerax-official                     # installer + MCP e2e with --nogui --offscreen
docker run --rm molmcp-chimerax-official bash /home/tester/work/mol-mcp/tests/docker/linux_bundle_check_chimerax.sh

# Alternative with a release .deb: download the Ubuntu 24.04 package for your CPU from
# https://www.rbvi.ucsf.edu/chimerax/download.html, save it as tests/docker/chimerax.deb, then
docker build -f tests/docker/Dockerfile.chimerax-linux -t molmcp-chimerax-linux .
docker run --rm molmcp-chimerax-linux
```

## Development

```bash
.venv/bin/python -m unittest discover -s tests            # analysis, installer and platform-simulation unit tests
.venv/bin/python tests/e2e_mcp_client.py pymol --launch   # end-to-end through the real MCP server
.venv/bin/python tests/e2e_mcp_client.py chimerax --launch
.venv/bin/python examples/make_gallery.py                 # regenerate the README images (see the script's docstring)
```

Layout: `molmcp/common` (analysis, discovery, client, shared tool bodies), `molmcp/pymol_server`,
`molmcp/chimerax_server`, `molmcp/inapp/pymol` (plugin + launchers), `molmcp/inapp/chimerax` (bundle),
`molmcp/inapp/shared` (HTTP bridge core, CLI driver and chat panel, copied into both in-app packages by the
installer), `molmcp/skills` (built-in skills).

# molmcp — PyMOL and ChimeraX MCP servers with real scene awareness

Two independent [MCP](https://modelcontextprotocol.io) servers, `pymol-mcp` and `chimerax-mcp`, for
Claude Code, Codex CLI, Claude Desktop or any other MCP client.  Each server talks to a small bridge that
runs *inside* the viewer (a PyMOL plugin / a ChimeraX bundle), so the agent gets:

* **Fast, synchronous command execution** over a persistent localhost connection (~0.2 ms per call
  overhead; a batch of commands returns per-command output, errors, and a list of what actually changed).
* **Full state awareness** — structured snapshots of objects/models, chains, representations, colours,
  selections, camera, lighting and settings; an event stream of what the user typed or changed in the GUI.
* **Render analysis without a vision model** — every render is described numerically: coverage, bounding
  box, centroid offset, which frame edges clip the content, free margins, dominant *named* colours,
  contrast, an ASCII density map; an **ID pass** reports per object/chain visibility, screen share,
  2D contacts and occlusion; renders can be diffed to confirm a change.
* **In-tool integration** — the bridge auto-starts with the application; PyMOL gets `agent_status`,
  `agent_start`, `agent_stop` commands (and a Plugin-menu entry), ChimeraX gets `agent status|start|stop`.
  The MCP server can also launch the application itself (GUI or headless).
* **Claude / Codex inside the app** — a Claude-Code-style chat panel (PyMOL: *Plugin ▸ Agent Chat*, or
  `agent_chat`; ChimeraX: *Tools ▸ General ▸ Agent Chat*, or `agent chat`) and the commands `claude <text>` /
  `codex <text>` run your installed Claude Code or Codex CLI non-interactively, with the app's MCP server pinned
  to that very process.  The panel streams the agent's text, shows every tool call (`⏺ pymol/run(...)`) with a
  collapsed result preview (`⎿`), an animated status line while it works, and the cost/tokens when done.
  Slash commands: `/clear`, `/claude`, `/codex`, `/stop`, `/help`; Enter sends, Shift+Enter newline, Esc
  interrupts, ↑/↓ recall prompts.  Conversations continue across turns per backend.

Works on macOS, Linux and Windows.  Only the standard library plus numpy/Pillow (both shipped with the
viewers) run inside the applications; the servers need Python ≥ 3.10.

## Install

```bash
git clone git@github.com:Jetzu/Structural-Biology-MCPs.git mol-mcp && cd mol-mcp   # or https://github.com/Jetzu/Structural-Biology-MCPs.git
python install.py            # creates .venv, installs molmcp, installs the PyMOL plugin and ChimeraX bundle,
                             # registers both servers with Claude Code, Codex CLI and Claude Desktop (if present)
python install.py --check    # only report what was found
python install.py --help     # individual steps: --pymol --chimerax --claude --codex --claude-desktop, --uninstall, --dry-run
```

The installer finds PyMOL/ChimeraX on `PATH` or in the usual install locations (`/Applications/*.app`,
`/opt/UCSF/ChimeraX*`, `C:\Program Files\...`, conda envs).  Override with `PYMOL_EXE` / `CHIMERAX_EXE`.

What it does:

| step | effect |
|------|--------|
| PyMOL plugin | copies `molmcp_pymol_bridge` into your PyMOL plugin directory using PyMOL's own plugin preferences (autoload on). Fallback: a `run` line in `~/.pymolrc`. |
| ChimeraX bundle | builds `ChimeraX-AgentBridge` as a wheel (no build tools needed) and installs it with `toolshed install`; the bundle starts the bridge at ChimeraX startup. |
| Claude Code | adds `pymol` and `chimerax` to `~/.claude.json` (user scope). Run `/mcp` in Claude Code. |
| Codex CLI | adds `[mcp_servers.pymol]` / `[mcp_servers.chimerax]` to `~/.codex/config.toml`. |
| Claude Desktop | adds both servers to `claude_desktop_config.json` if that file exists. |

Config files are backed up as `*.molmcp-backup` before editing.  Restart the viewers after installing.

Manual registration (any MCP client): command `<repo>/.venv/bin/pymol-mcp` or `<repo>/.venv/bin/chimerax-mcp`
(`.venv\Scripts\*.exe` on Windows), stdio transport, no arguments.

## Using it

Open PyMOL or ChimeraX (the bridge starts automatically — `agent_status` / `agent status` shows the port),
or let the agent call `launch`.  Typical agent flow:

1. `status` → is a bridge running, which process, where renders go.
2. `scene` → what is loaded and shown (objects/models, chains, reps, colours, camera).
3. `run` → commands; read `changes` to see what happened.
4. `render` / `layout` → numerical description of the picture; `compare_renders` to verify.
5. `events` / `log` → what the user did in the GUI in the meantime.

### Tools (both servers)

| tool | purpose |
|------|---------|
| `status`, `launch`, `connect` | discover / start / pick a viewer process (several can run at once) |
| `run` | execute viewer commands; per-command ok/output/error + scene changes |
| `python` | run Python inside the viewer (`cmd`/`pymol` or `session`/`run`), return `result` |
| `scene` | structured state snapshot (`detail="full"` adds per-chain details) |
| `object_info` / `model_info` | everything about one object / model |
| `selection_info` | what a selection / atom-spec matches (counts, ranges, names, centre) |
| `get_view` (+ `set_view` in PyMOL) | camera |
| `render` | render + analysis (coverage, bbox, clipping, margins, named colours, contrast, ASCII map); PNG saved to `~/.molmcp/renders` |
| `layout` | ID-pass render: which objects/chains are visible where, screen share, contacts, optional occlusion |
| `compare_renders`, `analyze_image` | diff two renders; analyse any PNG on disk |
| `events`, `log` | activity since last call; viewer log |
| `help`, `commands` | command documentation / list |
| `settings` (PyMOL) | read settings, globally or per object |
| `quit_pymol` / `quit_chimerax` | terminate the viewer |

### Environment variables

| variable | meaning |
|----------|---------|
| `MOLMCP_HOME` | state directory (default `~/.molmcp`): bridge discovery files, renders, build artefacts |
| `MOLMCP_OUTPUT_DIR` | where `render` writes PNGs (default `$MOLMCP_HOME/renders`) |
| `MOLMCP_AUTOLAUNCH=0` | never start the viewer automatically from a tool call |
| `MOLMCP_APP_CWD` | working directory for viewers started by `launch` (default: your home directory) |
| `PYMOL_EXE`, `CHIMERAX_EXE`, `PYMOL_PYTHON` | explicit executables (headless PyMOL uses the bundled Python as a library) |
| `MOLMCP_PYMOL_PORT`, `MOLMCP_CHIMERAX_PORT` | fixed bridge ports (default: random free port) |
| `MOLMCP_PYMOL_AUTOSTART=0`, `MOLMCP_CHIMERAX_AUTOSTART=0` | don't start the bridge with the application |

## Claude / Codex inside PyMOL and ChimeraX

```
PyMOL>  claude which chains are shown and how are they coloured?
PyMOL>  codex colour all carbons magenta and zoom on the ligand
ChimeraX: claude colour the ribbon of chain A hot pink
ChimeraX: agent chat            (opens the panel; Enter sends, Shift+Enter = newline)
```

```
✻ Welcome to Agent Chat for PyMOL
> colour the helices marine and the strands yellow, then say what you changed
⏺ I'll update the colours in the current PyMOL session.
⏺ pymol/scene({"detail": "summary"})
  ⎿  {"app": "pymol", "gui": true, "viewport": [1230, 1404], "objects": [{"name": "1ubq", ...
⏺ pymol/run({"commands": ["color marine, ss H", "color yellow, ss S"]})
  ⎿  {"results": [{"command": "color marine, ss H", "ok": true, ...
⏺ I coloured the helices marine and the strands yellow in the current PyMOL session.
✓ codex · 22.9s · 328 output tokens
```

The command spawns `claude -p ... --output-format stream-json --allowedTools mcp__<app>` or
`codex exec --json --approve-for-me ...` from inside the application with `MOLMCP_<APP>_PID` set, so the MCP
server the CLI starts attaches to this exact viewer process.  The CLI is found on `PATH`, in the VS Code
Claude Code extension, in `~/.claude/local`, or (Codex) in the ChatGPT desktop app; override with
`MOLMCP_CLAUDE_EXE` / `MOLMCP_CODEX_EXE`.  Each candidate is checked with `--version`, so a stale or
wrong-architecture install is skipped.  The viewer's own interpreter settings (`PYTHONHOME`,
`PYTHONEXECUTABLE`, `DYLD_*`, `QT_*`...) are stripped from the CLI's environment so that the server's Python
starts cleanly.  Both CLIs use your own accounts and consume your own usage.

## How it works

```
Claude Code / Codex ──stdio──> pymol-mcp ──HTTP (127.0.0.1, token)──> bridge thread inside PyMOL ──> PyMOL main thread
                     ──stdio──> chimerax-mcp ──HTTP (127.0.0.1, token)──> bridge thread inside ChimeraX ──> Qt main thread
```

* Each bridge binds a random localhost port, generates a token, and writes
  `$MOLMCP_HOME/instances/<app>-<pid>.json`; servers discover live bridges from these files (stale ones are
  removed).  Requests are JSON (`{"op": ..., "args": ...}`); images travel as base64 PNG.
* Operations run on the application's main thread (PyMOL `MainThreadCaller`, ChimeraX `ui.thread_safe`),
  so GUI, rendering and command execution stay consistent with what the user sees.
* Render analysis (`molmcp/common/imageanalysis.py`) is pure numpy: background estimation, foreground mask,
  bounding box/centroid/edge coverage, Lab-space nearest-named-colour palette, hue shares, WCAG contrast,
  ASCII occupancy grid; the ID pass recolours each item flat (ambient-only lighting, no fog/shadows/
  transparency) and restores every colour, setting and selection afterwards (verified by re-render diff).
* Headless PyMOL runs PyMOL as a library inside its bundled Python (no busy keep-alive loop); headless
  ChimeraX needs Linux with `--offscreen` for rendering.

## What has been verified where

| | macOS (this build) | Linux (x86_64 container) | Windows |
|---|---|---|---|
| PyMOL GUI: run / scene / render / layout / events / compare | tested, PyMOL 3.1.5 | n/a (no display) | not tested |
| PyMOL headless (library mode, ray renders) | tested | tested, open-source PyMOL 3.1 via conda-forge | not tested |
| PyMOL plugin install through PyMOL's plugin prefs | tested | tested | not tested |
| ChimeraX GUI: run / scene / render / layout / events / compare | tested, ChimeraX 1.11.1 | n/a (no display) | not tested |
| ChimeraX headless `--nogui --offscreen`: launch via MCP, run / scene / offscreen render / layout / events / compare | not possible on macOS (verified: "running without graphics") | tested as a normal user in UCSF's official `ucsfrbvi/chimerax` image (arm64, ChimeraX 1.13 dev) | not possible |
| ChimeraX bundle install via `toolshed install` + autostart of the bridge + `agent`/`claude`/`codex` commands | tested | tested (same image; note: ChimeraX redirects root's data dir, so run as a normal user) | not tested |
| Claude Code registration (`claude mcp list` → Connected) | tested | config written and parsed | not tested |
| Codex CLI live session calling the tools (`codex exec` → launch/run/layout/render on both servers) | tested, Codex CLI 0.160.0 | config written and parsed | not tested |
| Claude Code live session calling the tools (`claude -p` → launch/run/layout/render on both servers) | tested, Claude Code 2.1.319 | not run | not tested |
| In-app chat: PyMOL `claude`/`codex` commands and dock; ChimeraX `claude`/`codex` commands and tool panel, both backends changing the live scene | tested | not run | not tested |
| Platform-simulation tests (`tests/test_platform.py`) | pass | pass | Windows branches exercised by simulation only |

Windows support is implemented (path discovery for Schrodinger/conda PyMOL and ChimeraX, `.exe` console
scripts, `%APPDATA%` plugin dir, detached process creation, Windows-safe pid checks, `ChimeraX-console.exe`
for scripted/headless runs, `python.exe -m pymol -cq` for the headless plugin installer) but has not been run
on a Windows machine.  Please report issues from the first Windows run.

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
.venv/bin/python -m unittest discover -s tests          # image-analysis + platform-simulation unit tests
.venv/bin/python tests/e2e_mcp_client.py pymol --launch   # end-to-end through the real MCP server
.venv/bin/python tests/e2e_mcp_client.py chimerax --launch
```

Layout: `molmcp/common` (analysis, discovery, client, shared tool bodies), `molmcp/pymol_server`,
`molmcp/chimerax_server`, `molmcp/inapp/pymol` (plugin + launchers), `molmcp/inapp/chimerax` (bundle),
`molmcp/inapp/shared/bridgecore.py` (HTTP bridge core copied into both in-app packages by the installer).

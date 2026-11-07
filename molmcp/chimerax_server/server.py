"""chimerax-mcp: MCP server that drives UCSF ChimeraX through the in-app molmcp bridge."""
import os
import sys
from typing import List, Optional, Union

from molmcp.common.mcpcompat import FastMCP

from molmcp.common import discovery
from molmcp.common import server_common as sc

INSTRUCTIONS = """ChimeraX MCP server (molmcp). You control a live UCSF ChimeraX process through a bridge running inside it.

Workflow:
1. `status` - is a ChimeraX bridge running?  `launch` starts ChimeraX if needed.
2. `scene` - structured snapshot: models (#ids, types, atoms, chains, shown atoms/ribbons/surfaces, colours),
   selection, camera, lighting, background.  Call it before assuming what is loaded or displayed.
3. `run` - execute ChimeraX commands (same syntax as the ChimeraX command line).  Each response has per-command
   ok/output/error (the log text) and a `changes` list (models added/removed, display changes, camera moves).
   Batch several commands per call.
4. `render` - draw the current view and get a numerical description: coverage, bounding box, clipping at the
   frame edges, margins, dominant named colours, contrast and an ASCII density map.  `layout` renders an ID pass
   (each model or chain in a unique flat colour, then everything is restored) and reports which items are visible
   where, their on-screen share, 2D contacts and (optionally) occlusion.  Use these instead of looking at images.
   `compare_renders` diffs two renders to verify that a change took effect.
5. `events` / `log` - what the user (or you) did since last check: commands, errors, model changes.
6. `python` - run Python inside ChimeraX (`session` and `run(cmd)` available; set `result` to return data).
7. `skills` / `skill` - instruction files for common jobs (publication rendering, movies, surfaces, alignment,
   maps, ligand sites, ...). Read the matching skill before a non-trivial task; `save_skill` stores your own
   recipe for next time.  Structured helpers: `measure`, `align`, `sequence`, `contacts`, `save_file`.

Atom-spec reminders: `#1` model, `#1/A` chain, `#1/A:10-20` residues, `:LIG` residue name, `@CA` atom name,
`protein`, `ligand`, `solvent`, `sel` (current selection), `#1 & ~solvent`, zones: `#2 & #1 @< 5`.
Rendered files are written to the renders directory reported by `status` so the user can open them.
Several ChimeraX windows may be open: each is a separate session with its own bridge. `status` lists them (pid, name,
loaded items, which one has focus); the server connects to the focused / most recently used window and every
`run`/`scene`/`events` reply names the window when more than one is open. Switch with `connect(pid=...)` or
`connect(name=...)`; the user can name a window with `agent name <name>`.
"""

mcp = FastMCP("chimerax", instructions=INSTRUCTIONS)


def _launcher(mode: str) -> List[str]:
    exe = discovery.find_chimerax()
    launch_script = sc.inapp_path("chimerax", "molmcp_chimerax_launch.py")
    argv = [exe or ""]
    if mode in ("nogui", "headless"):
        argv = [discovery.chimerax_console_exe(exe) or ""]
        argv += ["--nogui"]
        if sys.platform.startswith("linux"):
            argv += ["--offscreen"]
    argv += ["--script", launch_script]
    return argv


SESSION = sc.AppSession("chimerax", _launcher, discovery.find_chimerax)
sc.register_skill_extras(mcp, "chimerax")
from . import extra_tools  # noqa: E402
extra_tools.register(mcp, SESSION)
extra_tools.register_more(mcp, SESSION)


@mcp.tool()
def status() -> str:
    """Connection status: running ChimeraX bridges, which one is connected, version, window size, renders directory."""
    return sc.status(SESSION)


@mcp.tool()
def launch(mode: str = "gui", wait_seconds: float = 120) -> str:
    """Start a new ChimeraX process with the molmcp bridge and connect to it.

    mode: "gui" (normal window) or "nogui" (no window; rendering only works on Linux with offscreen support).
    """
    return sc.launch(SESSION, mode, wait_seconds)


@mcp.tool()
def connect(pid: Optional[int] = None, port: Optional[int] = None, name: Optional[str] = None) -> str:
    """Attach to a specific running ChimeraX window (see `status` for pids and names). Without arguments picks the
    window that has focus, else the most recently used one. Users can name a window with `agent name <name>`."""
    return sc.connect(SESSION, pid, port, name)


@mcp.tool()
def run(commands: Union[str, List[str]], stop_on_error: bool = True, allow_dangerous: bool = False, json: bool = False) -> str:
    """Execute ChimeraX commands synchronously (list of strings, or one string with one command per line).

    Returns per-command ok/output (log text)/error/value plus `changes`: what the commands changed (models
    added/removed, display toggles, atoms/ribbons shown, camera moves). json=True also returns the structured
    `json` value for the commands that provide one in ChimeraX 1.11 (the `info ...` family and `open`; most
    others, e.g. measure/hbonds, only log text - use `measure`/`contacts`/`python` for numbers). Commands that quit,
    reset the session or run shell/package managers are refused unless allow_dangerous=True (ask the user first).
    """
    return sc.run(SESSION, commands, stop_on_error=stop_on_error, allow_dangerous=allow_dangerous, extra={"json": True} if json else None)


@mcp.tool()
def python(code: str) -> str:
    """Run Python inside ChimeraX. `session` and `run(command_text)` are available; assign `result` to return data.
    Captures stdout and log output; also reports scene `changes`."""
    return sc.python(SESSION, code)


@mcp.tool()
def scene(detail: str = "summary", models: Optional[List[str]] = None) -> str:
    """Structured snapshot of the ChimeraX state.

    detail="summary": every model (#id, name, type, display, bounds, atoms/residues/chains, shown atoms and
    ribbons, atom styles, categories, surfaces, pseudobond groups), selection summary, camera (position, view
    direction, field of view, centre of rotation, clip planes), lighting, background.  detail="full" adds per-chain
    residue ranges, descriptions, secondary structure fractions, top atom/ribbon colours and ligand-like residues.
    models: restrict to these ids (e.g. ["#1", "#2.1"]).
    """
    return sc.scene(SESSION, detail, models, key="models")


@mcp.tool()
def model_info(model: str) -> str:
    """Full details for one model id (e.g. "#1"): chains, residue ranges, ligands, displayed reps, colours, surfaces."""
    return sc.simple_call(SESSION, "model_info", model=model)


@mcp.tool()
def selection_info(spec: str = "sel") -> str:
    """Describe what an atom specifier matches (default: the current selection `sel`): atoms/residues per
    structure and chain, residue ranges and names, elements, shown/selected counts, centre and extent."""
    return sc.simple_call(SESSION, "selection_info", spec=spec)


@mcp.tool()
def get_view() -> str:
    """Current camera: position, view direction, up vector, 3x4 matrix, field of view, centre of rotation, clip planes.
    To set the camera use `run` with `view matrix camera ...`, `view #1`, `turn`, `move`, `zoom`."""
    return sc.simple_call(SESSION, "get_view")


@mcp.tool()
def render(width: int = 800, height: int = 600, supersample: int = 3, transparent: bool = False,
           path: Optional[str] = None, return_image: bool = False, grid: str = "48x20"):
    """Render the current view and analyse it numerically (no vision needed).

    Returns the saved PNG path and an analysis: coverage, bounding box, centroid offset, margins, which frame
    edges clip the content, dominant named colours, hue shares, contrast, edge density and an ASCII density map
    (grid = columns x rows).  supersample 1 is fastest, 3 is ChimeraX's default quality.  path saves to a specific
    file.  return_image=True additionally returns the PNG for clients that can display it.
    """
    return sc.render(SESSION, width, height, path, return_image, grid, {"supersample": supersample, "transparent": transparent})


@mcp.tool()
def layout(by: str = "model", items: Optional[List[str]] = None, width: int = 640, height: int = 480,
           occlusion: bool = False, return_image: bool = False, grid: str = "48x20"):
    """Which models/chains are visible where: an ID-pass render (each item in a unique flat colour, state fully
    restored afterwards) analysed per item: on-screen share, bounding box, centroid, frame-edge contact, 2D
    contacts between items and an ASCII map with one letter per item.

    by="model" (displayed top-level structures, volumes and surfaces), by="chain" (every chain of every displayed
    structure, e.g. #1/A), or by="items" with `items` = list of atom specs (each becomes one item).
    occlusion=True also renders each item alone to report how much of it is hidden behind others (slower).
    """
    try:
        sc_json = SESSION.call("scene", detail="summary")
    except Exception as e:
        return sc.dumps({"ok": False, "error": str(e)})
    models = [m for m in sc_json.get("models", []) if m.get("visible", m.get("display"))]
    seg_items = []
    structural = ("AtomicStructure", "Structure", "Volume", "MolecularSurface", "Surface", "MarkerSet", "VolumeSurface")
    if by == "items":
        for s in items or []:
            seg_items.append({"label": s, "spec": s})
    elif by == "chain":
        for m in models:
            if "atoms" in m:
                chains = [c["chain"] for c in m.get("chains", [])] if m.get("chains") else None
                if chains is None:
                    try:
                        full = SESSION.call("model_info", model=m["id"])
                        chains = [c["chain"] for c in full.get("chains", [])]
                    except Exception:
                        chains = []
                for ch in chains:
                    seg_items.append({"label": "%s/%s" % (m["id"], ch), "spec": "%s/%s" % (m["id"], ch)})
            elif m.get("type") in ("Volume", "Surface", "MarkerSet") and m.get("parent") is None:
                seg_items.append({"label": "%s %s" % (m["id"], m["name"]), "spec": m["id"]})
    else:
        for m in models:
            if m.get("parent") is None and m.get("type") in structural:
                seg_items.append({"label": "%s %s" % (m["id"], m["name"]), "spec": m["id"]})
    if len(seg_items) > 60:
        seg_items = seg_items[:60]
    return sc.layout(SESSION, seg_items, width, height, occlusion, return_image, grid, {})


@mcp.tool()
def compare_renders(path_a: Optional[str] = None, path_b: Optional[str] = None, grid: str = "48x20") -> str:
    """Diff two rendered PNGs (defaults: the last two renders): fraction of pixels changed, region, ASCII change map."""
    return sc.compare(SESSION, path_a, path_b, grid)


@mcp.tool()
def analyze_image(path: str, grid: str = "48x20") -> str:
    """Numerical analysis of any PNG/JPEG on disk (e.g. a figure the user saved): same report as `render`."""
    return sc.analyze_image(path, grid)


@mcp.tool()
def events(since: Optional[int] = None, limit: int = 100) -> str:
    """What happened since the last call: commands run (by the user or by you), models added/removed, selection
    changes, warnings/errors, renders, plus `changes_now` (diff against the previous scene snapshot)."""
    return sc.events(SESSION, since, limit)


@mcp.tool()
def log(n: int = 50) -> str:
    """Last n lines of the ChimeraX log as plain text."""
    return sc.log(SESSION, n)


@mcp.tool()
def help(command: str) -> str:
    """Usage text for a ChimeraX command (like `usage <command>`), or close matches if unknown."""
    return sc.simple_call(SESSION, "help", command=command)


@mcp.tool()
def commands(prefix: str = "") -> str:
    """List registered ChimeraX command names (optionally filtered by prefix)."""
    return sc.simple_call(SESSION, "commands", prefix=prefix)


@mcp.tool()
def quit_chimerax(confirm: bool = False) -> str:
    """Terminate the connected ChimeraX process. Refused unless confirm=True; ask the user before closing their window."""
    return sc.quit_app(SESSION, confirm)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

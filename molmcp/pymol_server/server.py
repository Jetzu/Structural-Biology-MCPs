"""pymol-mcp: MCP server that drives PyMOL through the in-app molmcp bridge."""
import os
import sys
from typing import List, Optional, Union

from molmcp.common.mcpcompat import FastMCP

from molmcp.common import discovery
from molmcp.common import server_common as sc

INSTRUCTIONS = """PyMOL MCP server (molmcp). You control a live PyMOL process through a bridge running inside it.

Workflow:
1. `status` - see whether a PyMOL bridge is running (GUI or headless). `launch` starts PyMOL if needed.
2. `scene` - structured snapshot: objects (atoms, chains, representations, colours), selections, view, settings.
   Call it before making assumptions about what is loaded or shown.
3. `run` - execute PyMOL commands (same syntax as the PyMOL command line). Each response reports per-command
   success/output and a `changes` list (objects added/removed, representation/view changes) so you know what
   actually happened. Prefer batching several commands in one call.
4. `render` - draw the current view and get a numerical description: coverage, bounding box, clipping at the
   frame edges, margins, dominant named colours, contrast, and an ASCII density map. `layout` renders an ID pass
   (each object or chain in a unique flat colour) and tells you which items are visible where, how much of each
   is on screen, 2D contacts, and (optionally) how much of each is occluded.  Use these instead of looking at
   images.  `compare_renders` diffs two renders to verify a change took effect.
5. `events` / `log` - what the user (or you) did since last check: commands typed in the GUI, errors, state changes.
6. `python` - run Python inside PyMOL (`cmd`, `pymol`, `stored` available; set `result` to return data).
7. `skills` / `skill` - instruction files for common jobs (publication rendering, movies, surfaces, alignment,
   maps, ligand sites, ...). Read the matching skill before a non-trivial task; `save_skill` stores your own
   recipe for next time.  Structured helpers: `measure`, `align`, `sequence`, `contacts`, `save_file`.

Selection syntax reminders: object names can be referenced as `%name`; chains `chain A`; residues `resi 10-20`;
`polymer`, `organic`, `solvent`, `name CA`, `ss H/S/L`, `within 5 of (sel)`, `byres`.
Rendered files are written to the renders directory reported by `status` so the user can open them.
Several PyMOL windows may be open: each is a separate session with its own bridge. `status` lists them (pid, name,
loaded items, which one has focus); the server connects to the focused / most recently used window and every
`run`/`scene`/`events` reply names the window when more than one is open. Switch with `connect(pid=...)` or
`connect(name=...)`; the user can name a window with `agent_name <name>`.
"""

mcp = FastMCP("pymol", instructions=INSTRUCTIONS)


def _launcher(mode: str) -> List[str]:
    exe = discovery.find_pymol()
    launch_script = sc.inapp_path("pymol", "molmcp_pymol_launch.py")
    if mode == "headless":
        py = discovery.find_pymol_python(exe)
        if py:
            return [py, sc.inapp_path("pymol", "molmcp_pymol_headless.py")]
        return ([exe or "", "-cq", "-r", launch_script], {"MOLMCP_KEEPALIVE": "1"})
    return [exe or "", "-r", launch_script]


SESSION = sc.AppSession("pymol", _launcher, discovery.find_pymol)
sc.register_skill_extras(mcp, "pymol")
from . import extra_tools  # noqa: E402
extra_tools.register(mcp, SESSION)
extra_tools.register_more(mcp, SESSION)


@mcp.tool()
def status() -> str:
    """Connection status: running PyMOL bridges, which one is connected, PyMOL version, viewport, renders directory."""
    return sc.status(SESSION)


@mcp.tool()
def launch(mode: str = "gui", wait_seconds: float = 120) -> str:
    """Start a new PyMOL process with the molmcp bridge and connect to it.

    mode: "gui" (normal PyMOL window) or "headless" (no window, ray-traced renders; good for servers/CI).
    """
    return sc.launch(SESSION, mode, wait_seconds)


@mcp.tool()
def connect(pid: Optional[int] = None, port: Optional[int] = None, name: Optional[str] = None) -> str:
    """Attach to a specific running PyMOL window (see `status` for pids and names). Without arguments picks the
    window that has focus, else the most recently used one. Users can name a window with `agent_name <name>`."""
    return sc.connect(SESSION, pid, port, name)


@mcp.tool()
def run(commands: Union[str, List[str]], stop_on_error: bool = True, allow_dangerous: bool = False) -> str:
    """Execute PyMOL commands synchronously (list of strings, or one string with one command per line).

    Returns per-command ok/output/error plus `changes`: what the commands changed in the scene (objects
    added/removed/enabled, representations, view, selections). Use `fetch 1abc, async=0` to load from the PDB.
    Commands that quit, reinitialize or run shell/package managers are refused unless allow_dangerous=True (ask
    the user first).
    """
    return sc.run(SESSION, commands, stop_on_error=stop_on_error, allow_dangerous=allow_dangerous)


@mcp.tool()
def python(code: str) -> str:
    """Run Python inside PyMOL. `cmd`, `pymol` and `stored` are available; assign `result` to return data.
    Captures stdout and PyMOL feedback; also reports scene `changes`."""
    return sc.python(SESSION, code)


@mcp.tool()
def scene(detail: str = "summary", objects: Optional[List[str]] = None) -> str:
    """Structured snapshot of the PyMOL state.

    detail="summary": objects (type, enabled, atoms, states, chains, extent), selections, view/camera, background,
    key settings, movie frame/state, scenes.  detail="full" adds per-chain residue ranges, hetero groups,
    representation atom counts, top colours per chain and secondary-structure fractions.
    objects: restrict to these object names.
    """
    return sc.scene(SESSION, detail, objects, key="objects")


@mcp.tool()
def object_info(name: str) -> str:
    """Full details for one object (chains, residue ranges, ligands, representations, colours, setting overrides)."""
    return sc.simple_call(SESSION, "object_info", name=name)


@mcp.tool()
def selection_info(selection: str) -> str:
    """Describe what a PyMOL selection expression matches: atom/residue counts per object and chain, residue
    ranges, residue names, elements, extent and centre.  Use it to check a selection before acting on it."""
    return sc.simple_call(SESSION, "selection_info", selection=selection)


@mcp.tool()
def get_view() -> str:
    """Current camera: 18-value PyMOL view matrix decoded into rotation, distance, origin and clipping planes."""
    return sc.simple_call(SESSION, "get_view")


@mcp.tool()
def set_view(view: List[float]) -> str:
    """Set the camera from an 18-value PyMOL view (as returned by get_view / `get_view`)."""
    return sc.simple_call(SESSION, "set_view", view=view)


@mcp.tool()
def render(width: int = 800, height: int = 600, ray: bool = False, transparent: bool = False,
           path: Optional[str] = None, return_image: bool = False, grid: str = "48x20"):
    """Render the current view and analyse it numerically (no vision needed).

    Returns the saved PNG path and an analysis: coverage, bounding box, centroid offset, margins, which frame
    edges clip the content, dominant named colours, hue shares, contrast, edge density and an ASCII density map
    (grid = columns x rows).  ray=True uses the ray tracer (slower, publication quality).  path saves to a
    specific file.  return_image=True additionally returns the PNG for clients that can display it.
    """
    return sc.render(SESSION, width, height, path, return_image, grid, {"ray": ray, "transparent": transparent})


@mcp.tool()
def layout(by: str = "object", items: Optional[List[str]] = None, width: int = 640, height: int = 480,
           occlusion: bool = False, return_image: bool = False, grid: str = "48x20"):
    """Which objects/chains are visible where: an ID-pass render (each item drawn in a unique flat colour, state
    fully restored afterwards) analysed per item: on-screen share, bounding box, centroid, frame-edge contact,
    2D contacts between items and an ASCII map with one letter per item.

    by="object" (enabled objects), by="chain" (every chain of every enabled molecule), or by="items" with
    `items` = list of PyMOL selection expressions (each becomes one item).  occlusion=True also renders each item
    alone to report how much of it is hidden behind others (slower).
    """
    try:
        sc_json = SESSION.call("scene", detail="summary")
    except Exception as e:
        return sc.dumps({"ok": False, "error": str(e)})
    objs = [o for o in sc_json.get("objects", []) if o.get("enabled")]
    seg_items = []
    if by == "items":
        for s in items or []:
            seg_items.append({"label": s, "selection": s})
    elif by == "chain":
        for o in objs:
            if o.get("type") == "molecule":
                for ch in o.get("chains") or [""]:
                    sel = '(%%%s and chain "%s")' % (o["name"], ch) if ch == "" else "(%%%s and chain %s)" % (o["name"], ch)
                    seg_items.append({"label": "%s/%s" % (o["name"], ch or "''"), "selection": sel})
            elif o.get("type") in ("map", "mesh", "surface", "cgo"):
                seg_items.append({"label": o["name"], "selection": "%" + o["name"]})
    else:
        for o in objs:
            if o.get("type") in ("molecule", "map", "mesh", "surface", "cgo", "slice", "volume", "measurement"):
                seg_items.append({"label": o["name"], "selection": "%" + o["name"]})
    if len(seg_items) > 60:
        seg_items = seg_items[:60]
    return sc.layout(SESSION, seg_items, width, height, occlusion, return_image, grid, {})


@mcp.tool()
def compare_renders(path_a: Optional[str] = None, path_b: Optional[str] = None, grid: str = "48x20") -> str:
    """Diff two rendered PNGs (defaults: the last two renders): fraction of pixels changed, region, ASCII change map.
    Use after a `run` to confirm the view really changed (or stayed the same)."""
    return sc.compare(SESSION, path_a, path_b, grid)


@mcp.tool()
def analyze_image(path: str, grid: str = "48x20") -> str:
    """Numerical analysis of any PNG/JPEG on disk (e.g. a figure the user saved): same report as `render`."""
    return sc.analyze_image(path, grid)


@mcp.tool()
def events(since: Optional[int] = None, limit: int = 100) -> str:
    """What happened since the last call: commands typed by the user in the GUI, errors, renders, and detected
    state changes (objects added/removed, view moved, selections).  Also returns `changes_now`, a diff of the
    scene against the previous snapshot.  `since` = event sequence number (default: continue from last call)."""
    return sc.events(SESSION, since, limit)


@mcp.tool()
def log(n: int = 50) -> str:
    """Last n lines of PyMOL's output/feedback (including the user's own commands and their results)."""
    return sc.log(SESSION, n)


@mcp.tool()
def help(command: str) -> str:
    """Documentation for a PyMOL command (same text as `help <command>` in PyMOL), or close matches if unknown."""
    return sc.simple_call(SESSION, "help", command=command)


@mcp.tool()
def commands(prefix: str = "") -> str:
    """List available PyMOL command names (optionally filtered by a case-insensitive prefix)."""
    return sc.simple_call(SESSION, "commands", prefix=prefix)


@mcp.tool()
def settings(names: Optional[List[str]] = None, object: Optional[str] = None) -> str:
    """Read PyMOL settings (defaults to a curated list of rendering-relevant ones); object= reads object-level values."""
    return sc.simple_call(SESSION, "settings", names=names, object=object)


@mcp.tool()
def quit_pymol(confirm: bool = False) -> str:
    """Terminate the connected PyMOL process. Refused unless confirm=True; ask the user before closing their window."""
    return sc.quit_app(SESSION, confirm)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

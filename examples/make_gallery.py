"""Regenerate the README gallery (docs/images/*.png) through the MCP servers.

Every image is produced the way an agent produces it: this script is an MCP client that starts `pymol-mcp` /
`chimerax-mcp`, launches the viewer with `launch`, sends `run` commands and saves `render` / `layout` results.
With PYMOL_PYTHON set (a Python that imports open-source PyMOL, e.g. `conda create -p pymol-os -c conda-forge
pymol-open-source`), the PyMOL entries run headless with it and are ray-traced; otherwise the PyMOL GUI is used.
An image in which a licence banner is detected (incentive PyMOL without a valid licence) is not saved.
Next to each PNG it writes what the agent got back instead of a picture (docs/images/analysis/<name>.json):
the numerical render description, the ASCII density map and, for ID passes, the per-chain table.

Run (one viewer at a time; each is started in its own state directory and quit at the end):

    PYMOL_PYTHON=/path/to/python-with-open-source-pymol \
    .venv/bin/python examples/make_gallery.py                 # everything
    .venv/bin/python examples/make_gallery.py pymol           # only the PyMOL entries
    .venv/bin/python examples/make_gallery.py biotin layout   # only these entries
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "images"
ANALYSIS = OUT / "analysis"
BIN = ROOT / ".venv" / ("Scripts" if sys.platform.startswith("win") else "bin")
EXE = ".exe" if sys.platform.startswith("win") else ""
MAX_WIDTH = 1400

# name -> app, prompt (as shown in the README), commands, how to capture
ENTRIES = {
    # ---------------------------------------------------------------- PyMOL
    "ubiquitin": dict(app="pymol", prompt=(
        "Make a publication figure of ubiquitin (1UBQ): cartoon coloured by secondary structure, Lys48 and Lys63 "
        "as labelled sticks, white background."), commands=[
        "fetch 1ubq, async=0", "remove solvent", "hide everything", "show cartoon", "dss",
        "set cartoon_fancy_helices, 1", "set cartoon_transparency, 0",
        "color grey80", "color skyblue, ss H", "color salmon, ss S",
        "show sticks, resi 48+63 and not name N+C+O", "color yelloworange, resi 48+63 and elem C",
        "color blue, resi 48+63 and elem N", "set stick_radius, 0.3",
        "label resi 48+63 and name NZ, 'K' + resi", "set label_size, 28", "set label_color, black",
        "set label_position, (1.5, 1.5, 2)", "set float_labels, 1",
        "bg_color white", "set antialias, 2", "set ray_shadow, 0", "set depth_cue, 0", "set specular, 0.2",
        "orient", "turn x, -30", "turn y, 20", "zoom all, 2"],
        capture="render", size=(1600, 1200)),
    "density": dict(app="pymol", prompt=(
        "Show the 2mFo-DFc density of ubiquitin at 1.5 sigma around the Ile44 hydrophobic patch "
        "(Leu8, Ile44, Val70) as a carved mesh."), commands=[
        "fetch 1ubq, async=0", "fetch 1ubq, type=2fofc, async=0", "remove solvent", "hide everything",
        "show sticks, resi 8+44+70+42+68", "color grey60, elem C", "color red, elem O", "color blue, elem N",
        "color yelloworange, resi 8+44+70 and elem C", "set stick_radius, 0.2",
        "isomesh patch, 1ubq_2fofc, 1.5, resi 8+44+70+42+68, carve=1.8", "color skyblue, patch",
        "set mesh_width, 1.2",
        "bg_color white", "set antialias, 2", "set depth_cue, 0",
        "orient resi 8+44+70", "zoom resi 8+44+70+42+68, 2"],
        capture="render", size=(1600, 1200)),
    "layout": dict(app="pymol", prompt=(
        "Show haemoglobin (4HHB) with each chain in its own colour and the hemes as sticks, then tell me how much "
        "of each chain is visible and which chains hide each other."), commands=[
        "fetch 4hhb, async=0", "remove solvent", "hide everything", "show cartoon",
        "color skyblue, chain A", "color salmon, chain B", "color palegreen, chain C", "color wheat, chain D",
        "show sticks, resn HEM", "color grey40, resn HEM and elem C", "set stick_radius, 0.2",
        "bg_color white", "set antialias, 2", "set depth_cue, 0", "orient", "zoom all, 1"],
        capture="layout", size=(1200, 900)),
    "align": dict(app="pymol", prompt=(
        "Superpose closed (1AKE) and open (4AKE) adenylate kinase, colour them differently and give me the RMSD."),
        commands=[
        "fetch 1ake, async=0", "fetch 4ake, async=0", "remove not chain A", "remove solvent or organic",
        "hide everything", "show cartoon", "color marine, 1ake", "color salmon, 4ake",
        "bg_color white", "set antialias, 2", "set depth_cue, 0", "set cartoon_transparency, 0.15, 4ake"],
        tool=("align", {"mobile": "4ake", "target": "1ake", "method": "super"}),
        after=["orient 1ake", "zoom all, 1"], capture="render", size=(1600, 1200)),
    # ------------------------------------------------------------- ChimeraX
    "biotin": dict(app="chimerax", prompt=(
        "Zoom into the biotin pocket of streptavidin (1STP): biotin as ball-and-stick, the pocket residues as "
        "sticks, hydrogen bonds as dashed lines."), commands=[
        "open 1stp", "set bgColor white", "lighting soft", "graphics silhouettes true",
        "hide atoms", "cartoon", "color #1 lightsteelblue target c", "transparency #1 60 target c",
        "show :BTN :<4.5 & ~solvent atoms", "style stick", "color byhetero", "color :BTN & C gold",
        "style :BTN ball", "hbonds :BTN reveal true color black radius 0.06 dashes 8",
        "view :BTN :<4.5", "zoom 0.85"],
        capture="render", size=(1600, 1200)),
    "coulombic": dict(app="chimerax", prompt=(
        "Colour barnase by Coulombic potential and show its inhibitor barstar as a cartoon next to it (1BRS)."),
        commands=[
        "open 1brs", "delete #1 & ~/A,D", "delete solvent", "set bgColor white", "lighting soft",
        "hide atoms", "surface /A", "coulombic /A", "hide /A cartoon", "cartoon /D", "color /D gold target c",
        "view", "turn x -60", "view", "zoom 0.9"],
        capture="render", size=(1600, 1200)),
    "alphafold": dict(app="chimerax", prompt=(
        "Fetch the AlphaFold model of human p53 and colour it by pLDDT confidence."), commands=[
        "alphafold fetch P04637", "set bgColor white", "lighting soft", "graphics silhouettes true",
        "color bfactor palette alphafold", "view", "zoom 0.85"],
        capture="render", size=(1600, 1200)),
    "cryoem": dict(app="chimerax", prompt=(
        "Open the GroEL cryo-EM map EMD-1080 as a surface coloured radially from its centre, side view."),
        commands=[
        "open 1080 from emdb", "set bgColor white", "lighting soft",
        "volume #1 style surface", "color radial #1 palette spectral", "view", "turn x 70", "view", "zoom 0.9"],
        capture="render", size=(1600, 1200)),
}


def _json(result) -> dict:
    text = "".join(getattr(c, "text", "") for c in result.content)
    try:
        return json.loads(text)
    except Exception:
        return {"_text": text}


def content_box(src: str, pad_frac: float = 0.06):
    """Bounding box of everything that differs from the background (corner colour), with a margin."""
    from PIL import ImageChops
    im = Image.open(src).convert("RGB")
    bg = Image.new("RGB", im.size, im.getpixel((0, 0)))
    diff = ImageChops.difference(im, bg).convert("L").point(lambda v: 255 if v > 14 else 0)
    box = diff.getbbox()
    if not box:
        return None
    pad = int(pad_frac * max(box[2] - box[0], box[3] - box[1]))
    return (max(0, box[0] - pad), max(0, box[1] - pad), min(im.width, box[2] + pad), min(im.height, box[3] + pad))


def _shrink(src: str, dst: Path, box=None):
    im = Image.open(src).convert("RGB")
    if box:
        im = im.crop(box)
    if im.width > MAX_WIDTH:
        im = im.resize((MAX_WIDTH, round(im.height * MAX_WIDTH / im.width)), Image.LANCZOS)
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst, optimize=True)


def _keep(analysis: dict) -> dict:
    """The part of a render reply an agent reads instead of the picture."""
    keys = ("summary", "coverage", "bbox", "margins_frac", "clipped_edges", "palette", "background", "ascii")
    out = {k: analysis.get(k) for k in keys if k in analysis}
    if out.get("palette"):
        out["palette"] = [{"name": p["name"], "share": p["share"]} for p in out["palette"][:5]]
    return out


async def run_app(app: str, names):
    home = tempfile.mkdtemp(prefix="molmcp-gallery-%s-" % app)
    env = dict(os.environ, MOLMCP_HOME=home, MOLMCP_APP_CWD=home, MOLMCP_AUTOLAUNCH="0")
    params = StdioServerParameters(command=str(BIN / ("%s-mcp%s" % (app, EXE))), args=[], env=env)
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            call = lambda tool, args=None, **kw: s.call_tool(tool, args or {}, **kw)  # noqa: E731
            mode = "headless" if (app == "pymol" and os.environ.get("PYMOL_PYTHON")) else "gui"
            launched = _json(await call("launch", {"mode": mode}))
            if not launched.get("ok"):
                raise SystemExit("could not launch %s: %s" % (app, launched))
            print("== %s pid %s (%s)" % (app, launched.get("pid"), mode), flush=True)
            try:
                for name in names:
                    e = ENTRIES[name]
                    print("-- %s" % name, flush=True)
                    # ChimeraX frames the view for the window's aspect ratio: make it match the render's
                    reset = ["delete all"] if app == "pymol" else ["close", "windowsize %d %d" % (e["size"][0] // 2, e["size"][1] // 2)]
                    await call("run", {"commands": reset})
                    res = _json(await call("run", {"commands": e["commands"], "stop_on_error": False}))
                    bad = [x for x in res.get("results", []) if not x.get("ok")]
                    for x in bad:
                        print("   ! %s -> %s" % (x.get("command"), (x.get("error") or "")[:160]), flush=True)
                    record = {"prompt": e["prompt"], "commands": e["commands"], "failed": [x.get("command") for x in bad]}
                    if e.get("tool"):
                        tool, args = e["tool"]
                        record["tool"] = {"name": tool, "args": args, "result": _json(await call(tool, args))}
                    if e.get("after"):
                        await call("run", {"commands": e["after"]})
                    w_, h_ = e["size"]
                    png = os.path.join(home, "%s.png" % name)
                    r1 = _json(await call("render", {"width": w_, "height": h_, "path": png}))
                    if "analysis" not in r1:
                        print("   ! render failed: %s" % str(r1)[:300], flush=True)
                        continue
                    if (r1.get("watermark") or {}).get("detected"):
                        print("   ! licence banner in the frame, not saved (set PYMOL_PYTHON to an open-source PyMOL)", flush=True)
                        continue
                    box = content_box(r1["path"])
                    _shrink(r1["path"], OUT / ("%s.png" % name), box)
                    record["render"] = _keep(r1["analysis"])
                    record["viewer"] = "%s %s (%s)" % (app, launched.get("version"), mode)
                    if e["capture"] == "layout":
                        lay = _json(await call("layout", {"by": "chain", "width": w_, "height": h_, "occlusion": True}))
                        if lay.get("id_pass_path"):
                            _shrink(lay["id_pass_path"], OUT / ("%s_idpass.png" % name), box)
                        L = lay.get("layout", {})
                        record["layout"] = {
                            "items": [{k: it.get(k) for k in ("label", "visible", "pixels", "share_of_frame",
                                                              "share_of_content", "bbox", "centroid_frac", "touches_edges")}
                                      for it in L.get("items", [])],
                            "contacts_2d": L.get("contacts_2d"),
                            "summary": L.get("summary"), "occlusion": lay.get("occlusion"), "ascii": L.get("ascii"),
                            "legend": L.get("ascii_legend")}
                    ANALYSIS.mkdir(parents=True, exist_ok=True)
                    (ANALYSIS / ("%s.json" % name)).write_text(json.dumps(record, indent=1))
                    print("   saved docs/images/%s.png (coverage %s)" % (name, record["render"].get("coverage")), flush=True)
            finally:
                q = "quit_pymol" if app == "pymol" else "quit_chimerax"
                print("== quit:", _json(await call(q, {"confirm": True})), flush=True)
    shutil.rmtree(home, ignore_errors=True)


def main(argv):
    wanted = argv or list(ENTRIES)
    names = [n for n in ENTRIES if n in wanted or ENTRIES[n]["app"] in wanted]
    unknown = [w for w in wanted if w not in ENTRIES and w not in ("pymol", "chimerax")]
    if unknown:
        raise SystemExit("unknown entries: %s (have: %s)" % (", ".join(unknown), ", ".join(ENTRIES)))
    for app in ("pymol", "chimerax"):
        todo = [n for n in names if ENTRIES[n]["app"] == app]
        if todo:
            asyncio.run(run_app(app, todo))


if __name__ == "__main__":
    main(sys.argv[1:])

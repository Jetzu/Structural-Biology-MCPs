"""Shared implementation of the MCP tools for both viewer servers."""
from __future__ import annotations

import base64
import datetime as _dt
import json
import os
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Sequence

from . import discovery
from . import imageanalysis as ia
from .bridge_client import BridgeClient, BridgeError, NotConnected
from .colornames import nearest_color_name

PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../molmcp
INAPP_DIR = os.path.join(PKG_ROOT, "inapp")

MAX_OUTPUT_CHARS = 6000


def renders_dir() -> str:
    d = os.environ.get("MOLMCP_OUTPUT_DIR") or os.path.join(discovery.molmcp_home(), "renders")
    os.makedirs(d, exist_ok=True)
    return d


def dumps(obj: Any) -> str:
    return json.dumps(obj, indent=1, ensure_ascii=False, default=str)


def _trim(text: Optional[str], limit: int = MAX_OUTPUT_CHARS) -> Optional[str]:
    if text is None or len(text) <= limit:
        return text
    return text[:limit // 2] + "\n... [%d chars omitted] ...\n" % (len(text) - limit) + text[-limit // 2:]


def _timestamp() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]


def _named_color(rgb: Sequence[int]) -> dict:
    name, dist = nearest_color_name(rgb)
    return {"rgb": list(rgb), "hex": "#%02x%02x%02x" % tuple(int(x) for x in rgb[:3]), "name": name}


class AppSession:
    """One viewer application (PyMOL or ChimeraX) as seen from the MCP server."""

    def __init__(self, app: str, launcher: Callable[[str], List[str]], exe_finder: Callable[[], Optional[str]]):
        self.app = app
        self.client = BridgeClient(app)
        self.launcher = launcher
        self.exe_finder = exe_finder
        self.events_seq = 0
        self.renders: List[str] = []
        self.last_launch: Optional[dict] = None

    # -- connection -----------------------------------------------------------
    def connect(self, auto_launch: bool = True, mode: str = "gui") -> dict:
        pinned = os.environ.get("MOLMCP_%s_PID" % self.app.upper())
        if pinned and (self.client.info is None or str(self.client.info.get("pid")) != pinned):
            try:
                return self.client.connect(pid=int(pinned))
            except (NotConnected, ValueError):
                pass   # pinned instance gone: fall back to discovery
        try:
            return self.client.ensure()
        except NotConnected:
            if auto_launch and os.environ.get("MOLMCP_AUTOLAUNCH", "1") != "0":
                return self.launch(mode)
            raise

    def launch(self, mode: str = "gui", wait_s: float = 120.0) -> dict:
        known = {int(i.get("pid", 0)) for i in discovery.list_instances(self.app)}
        spec = self.launcher(mode)
        argv, extra_env = (spec if isinstance(spec, tuple) else (spec, None))
        if not argv or not argv[0]:
            raise RuntimeError("%s executable not found. Set %s_EXE or put it on PATH." % (self.app, self.app.upper()))
        t0 = time.time()
        # start the viewer in the user's home (like a Finder/Start-menu launch) unless told otherwise
        cwd = os.environ.get("MOLMCP_APP_CWD") or os.path.expanduser("~")
        proc = discovery.popen_detached(argv, cwd=cwd, extra_env=extra_env)
        self.last_launch = {"argv": argv, "pid": proc.pid, "mode": mode, "t": t0}
        inst = discovery.wait_for_instance(self.app, timeout=wait_s, not_pids=known)
        if inst is None:
            rc = proc.poll()
            raise RuntimeError("launched %s (%s) but no bridge appeared within %.0fs%s" % (
                self.app, " ".join(argv), wait_s, "" if rc is None else " (process exited with code %s)" % rc))
        self.client.connect(inst)
        self.events_seq = 0
        return inst

    def call(self, op: str, timeout: Optional[float] = None, **args) -> Any:
        self.connect()
        return self.client.call(op, timeout=timeout, **args)

    # -- renders ---------------------------------------------------------------
    def save_png(self, data: bytes, tag: str) -> str:
        path = os.path.join(renders_dir(), "%s_%s_%s.png" % (self.app, tag, _timestamp()))
        with open(path, "wb") as f:
            f.write(data)
        self.renders.append(path)
        self.renders = self.renders[-30:]
        return path


# ---------------------------------------------------------------------------
# tool bodies (return JSON strings or [str, Image])
# ---------------------------------------------------------------------------

def status(sess: AppSession) -> str:
    instances = discovery.list_instances(sess.app)
    out: Dict[str, Any] = {
        "app": sess.app,
        "executable": sess.exe_finder(),
        "bridges_found": [{"pid": i.get("pid"), "port": i.get("port"), "version": i.get("app_version"),
                           "gui": i.get("gui"), "started": _dt.datetime.fromtimestamp(i.get("started", 0)).isoformat(timespec="seconds"),
                           "cwd": i.get("cwd")} for i in instances],
        "connected": False,
        "renders_dir": renders_dir(),
    }
    try:
        info = sess.client.ensure() if instances else None
    except NotConnected:
        info = None
    if info:
        out["connected"] = True
        out["connected_pid"] = info.get("pid")
        try:
            out["ping"] = sess.client.call("ping", timeout=10)
        except Exception as e:
            out["ping_error"] = str(e)
        out["client_stats"] = sess.client.stats
    else:
        out["hint"] = ("No running %s bridge found. Start %s with the molmcp bridge (it auto-starts when the plugin/bundle "
                       "is installed) or call the launch tool." % (sess.app, sess.app))
    if sess.last_launch:
        out["last_launch"] = sess.last_launch
    return dumps(out)


def launch(sess: AppSession, mode: str = "gui", wait_s: float = 120.0) -> str:
    try:
        inst = sess.launch(mode, wait_s)
    except Exception as e:
        return dumps({"ok": False, "error": str(e), "executable": sess.exe_finder(), "mode": mode})
    return dumps({"ok": True, "pid": inst.get("pid"), "port": inst.get("port"), "mode": mode,
                  "version": inst.get("app_version"), "gui": inst.get("gui")})


def connect(sess: AppSession, pid: Optional[int] = None, port: Optional[int] = None) -> str:
    try:
        info = sess.client.connect(pid=pid, port=port)
    except NotConnected as e:
        return dumps({"ok": False, "error": str(e), "bridges_found": discovery.list_instances(sess.app)})
    sess.events_seq = 0
    return dumps({"ok": True, "pid": info.get("pid"), "port": info.get("port"), "gui": info.get("gui")})


def _normalize_commands(commands) -> List[str]:
    if isinstance(commands, str):
        commands = commands.splitlines()
    out = []
    for c in commands or []:
        c = str(c).strip()
        if c:
            out.append(c)
    return out


def run(sess: AppSession, commands, stop_on_error: bool = True, timeout: float = 600.0) -> str:
    cmds = _normalize_commands(commands)
    if not cmds:
        return dumps({"error": "no commands given"})
    try:
        r = sess.call("run", timeout=timeout, commands=cmds, stop_on_error=stop_on_error)
    except (BridgeError, NotConnected) as e:
        return dumps({"ok": False, "error": str(e)})
    for res in r.get("results", []):
        res["output"] = _trim(res.get("output"))
        if res.get("traceback"):
            res["traceback"] = _trim(res["traceback"], 2000)
        if res.get("value") is None:
            res.pop("value", None)
        if res.get("error") is None:
            res.pop("error", None)
        if res.get("traceback") is None:
            res.pop("traceback", None)
    return dumps(r)


def python(sess: AppSession, code: str, timeout: float = 600.0) -> str:
    try:
        r = sess.call("python", timeout=timeout, code=code)
    except (BridgeError, NotConnected) as e:
        return dumps({"ok": False, "error": str(e)})
    r["stdout"] = _trim(r.get("stdout"))
    if r.get("traceback"):
        r["traceback"] = _trim(r["traceback"], 3000)
    res_text = dumps(r)
    if len(res_text) > 60000:
        r["result"] = "[result too large: %d chars; store it to a file instead]" % len(res_text)
        res_text = dumps(r)
    return res_text


def scene(sess: AppSession, detail: str = "summary", names: Optional[List[str]] = None, key: str = "objects") -> str:
    try:
        r = sess.call("scene", detail=detail, **({key: names} if names else {}))
    except (BridgeError, NotConnected) as e:
        return dumps({"ok": False, "error": str(e)})
    if "background" in r and "rgb" in r["background"]:
        r["background"].update(_named_color(r["background"]["rgb"]))
    sess.events_seq = max(sess.events_seq, int(r.get("events_seq", 0)))
    return dumps(r)


def simple_call(sess: AppSession, op: str, **args) -> str:
    try:
        return dumps(sess.call(op, **args))
    except (BridgeError, NotConnected) as e:
        return dumps({"ok": False, "error": str(e)})


def _grid(grid: str):
    try:
        c, r = grid.lower().split("x")
        return max(8, min(int(c), 160)), max(4, min(int(r), 80))
    except Exception:
        return 48, 20


def render(sess: AppSession, width: int, height: int, path: Optional[str], return_image: bool,
           grid: str, extra: dict, tag: str = "render", timeout: float = 600.0, analyze: bool = True):
    from .mcpcompat import Image
    cols, rows = _grid(grid)
    try:
        r = sess.call("render", timeout=timeout, width=width, height=height, path=path, **extra)
    except (BridgeError, NotConnected) as e:
        return dumps({"ok": False, "error": str(e)})
    png = base64.b64decode(r["png"])
    saved = r.get("path") or sess.save_png(png, tag)
    if not r.get("path"):
        pass
    else:
        sess.renders.append(saved)
    out: Dict[str, Any] = {"path": saved, "render_ms": r.get("ms"), "background": _named_color(r["background"]["rgb"])}
    for k in ("ray", "transparent", "viewport", "window"):
        if k in r:
            out[k] = r[k]
    if analyze:
        a = ia.analyze_render(png, grid_cols=cols, grid_rows=rows, bg_rgb=r["background"]["rgb"])
        out["analysis"] = a
    else:
        rgba = ia.load_rgba(png)
        out["width"], out["height"] = int(rgba.shape[1]), int(rgba.shape[0])
    text = dumps(out)
    if return_image:
        return [text, Image(data=ia.thumbnail_png(png, 1024), format="png")]
    return text


def layout(sess: AppSession, items: List[dict], width: int, height: int, occlusion: bool, return_image: bool,
           grid: str, extra: dict, timeout: float = 900.0):
    """items: [{label, <spec_key>: ...}] - the spec key is app specific ('selection' or 'spec')."""
    from .mcpcompat import Image
    cols, rows = _grid(grid)
    if not items:
        return dumps({"ok": False, "error": "nothing to lay out: no displayed items found"})
    colors = ia.id_colors(len(items))
    for it, rgb in zip(items, colors):
        it["rgb"] = list(rgb)
    try:
        r = sess.call("render_ids", timeout=timeout, items=items, width=width, height=height, solo=occlusion, **extra)
    except (BridgeError, NotConnected) as e:
        return dumps({"ok": False, "error": str(e)})
    png = base64.b64decode(r["png"])
    seg = ia.analyze_segmentation(png, r["legend"], grid_cols=cols, grid_rows=rows)
    out: Dict[str, Any] = {"items_requested": [it["label"] for it in items], "layout": seg}
    if occlusion and r.get("solo"):
        solo_counts = {}
        for label, b64 in r["solo"].items():
            legend = {k: v for k, v in r["legend"].items() if v == label}
            s = ia.analyze_segmentation(base64.b64decode(b64), legend, grid_cols=8, grid_rows=4)
            solo_counts[label] = s["items"][0]["pixels"] if s["items"] else 0
        out["occlusion"] = ia.occlusion_report(seg, solo_counts)
    saved = sess.save_png(png, "layout")
    out["id_pass_path"] = saved
    text = dumps(out)
    if return_image:
        return [text, Image(data=ia.thumbnail_png(png, 1024), format="png")]
    return text


def compare(sess: AppSession, path_a: Optional[str], path_b: Optional[str], grid: str) -> str:
    cols, rows = _grid(grid)
    if not path_a or not path_b:
        if len(sess.renders) < 2:
            return dumps({"ok": False, "error": "need two renders (paths) to compare; only %d saved so far" % len(sess.renders)})
        path_a = path_a or sess.renders[-2]
        path_b = path_b or sess.renders[-1]
    try:
        d = ia.diff_images(os.path.expanduser(path_a), os.path.expanduser(path_b), grid_cols=cols, grid_rows=rows)
    except Exception as e:
        return dumps({"ok": False, "error": str(e)})
    d["a"], d["b"] = path_a, path_b
    return dumps(d)


def analyze_image(path: str, grid: str) -> str:
    cols, rows = _grid(grid)
    try:
        a = ia.analyze_render(os.path.expanduser(path), grid_cols=cols, grid_rows=rows)
    except Exception as e:
        return dumps({"ok": False, "error": str(e)})
    a["path"] = path
    return dumps(a)


def events(sess: AppSession, since: Optional[int], limit: int) -> str:
    try:
        r = sess.call("events", since=sess.events_seq if since is None else since, limit=limit)
    except (BridgeError, NotConnected) as e:
        return dumps({"ok": False, "error": str(e)})
    sess.events_seq = int(r.get("seq", sess.events_seq))
    for e in r.get("events", []):
        e["t"] = _dt.datetime.fromtimestamp(e["t"]).strftime("%H:%M:%S.%f")[:-3]
    return dumps(r)


def log(sess: AppSession, n: int) -> str:
    try:
        r = sess.call("log", n=n)
    except (BridgeError, NotConnected) as e:
        return dumps({"ok": False, "error": str(e)})
    lines = []
    for l in r.get("lines", []):
        ts = _dt.datetime.fromtimestamp(l["t"]).strftime("%H:%M:%S")
        lines.append("%s %s%s" % (ts, ("[%s] " % l["level"]) if l.get("level") and l["level"] != "info" else "", l["text"]))
    return "\n".join(lines) if lines else "(log empty)"


def quit_app(sess: AppSession) -> str:
    try:
        r = sess.call("quit", timeout=10)
    except (BridgeError, NotConnected) as e:
        return dumps({"ok": False, "error": str(e)})
    sess.client.info = None
    return dumps(r)


def inapp_path(*parts: str) -> str:
    return os.path.join(INAPP_DIR, *parts)

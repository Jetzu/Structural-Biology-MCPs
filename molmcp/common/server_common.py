"""Shared implementation of the MCP tools for both viewer servers."""
from __future__ import annotations

import base64
import datetime as _dt
import json
import os
import re
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
        if pinned:
            if self.client.info is not None and str(self.client.info.get("pid")) == pinned:
                return self.client.info
            try:
                return self.client.connect(pid=int(pinned))
            except (NotConnected, ValueError):
                raise NotConnected("the %s window this chat is bound to (pid %s) is no longer running or not responding; "
                                   "restart the chat from a live window" % (self.app, pinned))
        try:
            return self.client.ensure()
        except NotConnected:
            files = discovery.list_instances(self.app)
            if files:
                # bridges exist but none answered: busy (long command, modal dialog) - never start another window
                raise NotConnected("%d %s window(s) are running but none answered the bridge ping (busy or showing a dialog); "
                                   "retry in a moment or call `status`" % (len(files), self.app))
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

def _instance_summary(d: dict) -> dict:
    items = d.get("objects") or d.get("models") or []
    return {
        "pid": d.get("pid"), "name": d.get("name") or "", "items": items, "responsive": d.get("responsive", True),
        "window_active": d.get("window_active"), "gui": d.get("gui"),
        "last_activity": _dt.datetime.fromtimestamp(d["last_activity"]).strftime("%H:%M:%S") if d.get("last_activity") else None,
        "started": _dt.datetime.fromtimestamp(d.get("started") or 0).strftime("%H:%M:%S"),
        "cwd": d.get("cwd"),
    }


def instance_note(sess: AppSession) -> Optional[str]:
    """One line naming the window acted on, only when several windows are open (added to tool responses)."""
    try:
        files = discovery.list_instances(sess.app)
    except Exception:
        return None
    if len(files) < 2 or not sess.client.info:
        return None
    pid = sess.client.info.get("pid")
    try:
        ident = sess.client.call("ping", timeout=5)
    except Exception:
        ident = {}
    items = ident.get("objects") or ident.get("models") or []
    name = ident.get("name") or ""
    return "%s window pid %s%s · %s (%d windows open; use `connect` to switch)" % (
        sess.app, pid, (" '%s'" % name) if name else "", ", ".join(items[:5]) or "empty", len(files))


def status(sess: AppSession) -> str:
    instances = sess.client.describe_instances()
    responsive = {int(i.get("pid", 0)) for i in instances}
    for f in discovery.list_instances(sess.app):
        if int(f.get("pid", 0)) not in responsive:
            instances.append({"pid": f.get("pid"), "name": f.get("name", ""), "started": f.get("started"), "cwd": f.get("cwd"),
                              "gui": f.get("gui"), "responsive": False, "window_active": None, "last_activity": None})
    out: Dict[str, Any] = {
        "app": sess.app,
        "executable": sess.exe_finder(),
        "windows": [_instance_summary(i) for i in instances],
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
        if len(instances) > 1:
            out["hint"] = ("%d %s windows are open; connected to pid %s. Each window is a separate session. "
                           "`connect(pid=...)` or `connect(name=...)` switches; the user can name a window with "
                           "%s." % (len(instances), sess.app, info.get("pid"),
                                    "`agent_name mywindow` in PyMOL" if sess.app == "pymol" else "`agent name mywindow` in ChimeraX"))
    elif instances:
        out["hint"] = ("%d %s window(s) have a bridge but none answered the ping (busy with a long command or showing a "
                       "dialog). Wait and call `status` again, `connect(pid=...)` once it answers, or close that window; "
                       "`launch` is refused while such a window exists." % (len(instances), sess.app))
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


def connect(sess: AppSession, pid: Optional[int] = None, port: Optional[int] = None, name: Optional[str] = None) -> str:
    try:
        info = sess.client.connect(pid=pid, port=port, name=name)
    except NotConnected as e:
        return dumps({"ok": False, "error": str(e), "windows": [_instance_summary(i) for i in sess.client.describe_instances()]})
    sess.events_seq = 0
    try:
        ident = sess.client.call("ping", timeout=5)
    except Exception:
        ident = {}
    return dumps({"ok": True, "pid": info.get("pid"), "port": info.get("port"), "gui": info.get("gui"),
                  "name": ident.get("name", ""), "items": ident.get("objects") or ident.get("models") or []})


def _normalize_commands(commands) -> List[str]:
    if isinstance(commands, str):
        commands = commands.splitlines()
    out = []
    for c in commands or []:
        c = str(c).strip()
        if c:
            out.append(c)
    return out


DANGEROUS = {
    "pymol": re.compile(r"^\s*(?:(?:q|qu|qui|quit|exit|reinit\w*|syst\w*|pip|conda|cd|rm|python|cmd\.(?:quit|system|reinitialize))\b|[/@])", re.I),
    "chimerax": re.compile(r"^\s*(exit|quit|clo\w*\s+sess\w*|pip\b|shell\b|system\b|remotecontrol\b|runscript\b|open\s+\S+\.(py|cxc)\b)", re.I),
}


def dangerous_parts(app: str, cmds) -> list:
    """Sub-commands (split on ';') that would quit/reset the program or run shell/package/script code."""
    pat = DANGEROUS.get(app)
    if not pat:
        return []
    bad = []
    for c in cmds:
        for part in str(c).split(";"):
            if part.strip() and pat.match(part):
                bad.append(part.strip()[:120])
    return bad


def run(sess: AppSession, commands, stop_on_error: bool = True, timeout: float = 600.0,
        allow_dangerous: bool = False, extra: Optional[dict] = None) -> str:
    cmds = _normalize_commands(commands)
    if not cmds:
        return dumps({"error": "no commands given"})
    if not allow_dangerous:
        bad = dangerous_parts(sess.app, cmds)
        if bad:
            return dumps({"ok": False, "error": "refused without allow_dangerous=true: %s (these quit the program, reset the "
                                               "session or run shell/package/script code; confirm with the user first)" % bad})
    if any(len(c) > 20000 for c in cmds):
        return dumps({"ok": False, "error": "a command is longer than 20000 characters; put long content in a file"})
    try:
        r = sess.call("run", timeout=timeout, commands=cmds, stop_on_error=stop_on_error, **(extra or {}))
    except (BridgeError, NotConnected) as e:
        return dumps({"ok": False, "error": str(e)})
    note = instance_note(sess)
    if note:
        r["instance"] = note
    for res in r.get("results", []):
        res["output"] = _trim(res.get("output"))
        if isinstance(res.get("command"), str) and len(res["command"]) > 500:
            res["command"] = res["command"][:500] + "…"
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
    if detail not in ("summary", "full"):
        return dumps({"ok": False, "error": "detail must be 'summary' or 'full'"})
    try:
        r = sess.call("scene", detail=detail, **({key: names} if names else {}))
    except (BridgeError, NotConnected) as e:
        return dumps({"ok": False, "error": str(e)})
    if "background" in r and "rgb" in r["background"]:
        r["background"].update(_named_color(r["background"]["rgb"]))
    sess.events_seq = max(sess.events_seq, int(r.get("events_seq", 0)))
    note = instance_note(sess)
    if note:
        r = dict(instance=note, **r)
    return dumps(r)


def simple_call(sess: AppSession, op: str, **args) -> str:
    try:
        return dumps(sess.call(op, **args))
    except (BridgeError, NotConnected) as e:
        return dumps({"ok": False, "error": str(e)})


def _grid(grid: str):
    """Parse "<cols>x<rows>"; raises ValueError for malformed input, clamps to 8-160 x 4-80."""
    try:
        c, r = str(grid).lower().split("x")
        c, r = int(c), int(r)
    except Exception:
        raise ValueError("grid must look like '48x20' (columns x rows), got %r" % (grid,))
    return max(8, min(c, 160)), max(4, min(r, 80))


def _grid_or_error(grid: str):
    try:
        cols, rows = _grid(grid)
    except ValueError as e:
        return None, None, dumps({"ok": False, "error": str(e)})
    return cols, rows, None


def _session_watermark(sess: AppSession) -> bool:
    """Whether the connected viewer burns a licence banner into renders (PyMOL without a valid licence)."""
    v = getattr(sess, "watermark", None)
    if v is None:
        try:
            info = sess.call("status", timeout=10)
            v = bool(info.get("watermark"))
        except Exception:
            v = False
        sess.watermark = v
    return v


def render(sess: AppSession, width: int, height: int, path: Optional[str], return_image: bool,
           grid: str, extra: dict, tag: str = "render", timeout: float = 600.0, analyze: bool = True):
    from .mcpcompat import Image
    cols, rows, gerr = _grid_or_error(grid)
    if gerr:
        return gerr
    err = _check_size(width, height)
    if err:
        return dumps({"ok": False, "error": err})
    try:
        r = sess.call("render", timeout=timeout, width=width, height=height, path=path, **extra)
    except (BridgeError, NotConnected) as e:
        return dumps({"ok": False, "error": str(e)})
    if "watermark" in r:
        sess.watermark = bool(r["watermark"])
    png = base64.b64decode(r["png"])
    saved = r.get("path") or sess.save_png(png, tag)
    if not r.get("path"):
        pass
    else:
        sess.renders.append(saved)
    out: Dict[str, Any] = {"path": saved, "render_ms": r.get("ms"), "background": _named_color(r["background"]["rgb"])}
    for k in ("ray", "transparent", "viewport", "window", "fallback"):
        if k in r:
            out[k] = r[k]
    if analyze:
        a = ia.analyze_render(png, grid_cols=cols, grid_rows=rows, bg_rgb=r["background"]["rgb"],
                              mask_watermark=bool(r.get("watermark")))
        out["analysis"] = a
        if r.get("watermark"):
            out["watermark"] = a.get("watermark")
    else:
        rgba = ia.load_rgba(png)
        out["width"], out["height"] = int(rgba.shape[1]), int(rgba.shape[0])
    note = instance_note(sess)
    if note:
        out["instance"] = note
    text = dumps(out)
    if return_image:
        return [text, Image(data=ia.thumbnail_png(png, 1024), format="png")]
    return text


MAX_RENDER_PIXELS = 16_000_000   # 4000x4000; bigger frames exhaust GPU/CPU memory and can kill the viewer


def _check_size(width, height) -> Optional[str]:
    try:
        w, h = int(width), int(height)
    except Exception:
        return "width/height must be integers"
    if w == 0 and h == 0:
        return None
    if w < 16 or h < 16:
        return "width and height must be at least 16 pixels (or both 0 for the current window size)"
    if w * h > MAX_RENDER_PIXELS:
        return "frame too large (%dx%d); the limit is %d pixels" % (w, h, MAX_RENDER_PIXELS)
    return None


def layout(sess: AppSession, items: List[dict], width: int, height: int, occlusion: bool, return_image: bool,
           grid: str, extra: dict, timeout: float = 900.0):
    """items: [{label, <spec_key>: ...}] - the spec key is app specific ('selection' or 'spec')."""
    from .mcpcompat import Image
    cols, rows, gerr = _grid_or_error(grid)
    if gerr:
        return gerr
    err = _check_size(width, height)
    if err:
        return dumps({"ok": False, "error": err})
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
    wm = bool(r.get("watermark"))
    if "watermark" in r:
        sess.watermark = wm
    seg = ia.analyze_segmentation(png, r["legend"], grid_cols=cols, grid_rows=rows, mask_watermark=wm)
    out: Dict[str, Any] = {"items_requested": [it["label"] for it in items], "layout": seg}
    if wm:
        out["watermark"] = "PyMOL runs without a valid licence; its evaluation banner was excluded from the ID pass"
    if r.get("errors"):
        out["item_errors"] = r["errors"]
    if occlusion and r.get("solo"):
        solo_counts = {}
        for label, b64 in r["solo"].items():
            legend = {k: v for k, v in r["legend"].items() if v == label}
            s = ia.analyze_segmentation(base64.b64decode(b64), legend, grid_cols=8, grid_rows=4, mask_watermark=wm)
            solo_counts[label] = s["items"][0]["pixels"] if s["items"] else 0
        out["occlusion"] = ia.occlusion_report(seg, solo_counts)
    saved = sess.save_png(png, "layout")
    out["id_pass_path"] = saved
    text = dumps(out)
    if return_image:
        return [text, Image(data=ia.thumbnail_png(png, 1024), format="png")]
    return text


def compare(sess: AppSession, path_a: Optional[str], path_b: Optional[str], grid: str) -> str:
    cols, rows, gerr = _grid_or_error(grid)
    if gerr:
        return gerr
    if not path_a or not path_b:
        renders = list(sess.renders)
        if len(renders) < 2:   # fresh server process: fall back to the newest files on disk
            try:
                files = sorted((os.path.join(renders_dir(), f) for f in os.listdir(renders_dir())
                                if f.startswith(sess.app + "_render_") and f.endswith(".png")), key=os.path.getmtime)
                renders = files[-2:]
            except OSError:
                renders = []
        if len(renders) < 2:
            return dumps({"ok": False, "error": "need two renders (paths) to compare; only %d found" % len(renders)})
        path_a = path_a or renders[-2]
        path_b = path_b or renders[-1]
    try:
        d = ia.diff_images(os.path.expanduser(path_a), os.path.expanduser(path_b), grid_cols=cols, grid_rows=rows,
                           mask_watermark=_session_watermark(sess))
    except Exception as e:
        return dumps({"ok": False, "error": str(e)})
    d["a"], d["b"] = path_a, path_b
    return dumps(d)


def analyze_image(path: str, grid: str, mask_watermark: bool = False) -> str:
    cols, rows, gerr = _grid_or_error(grid)
    if gerr:
        return gerr
    try:
        a = ia.analyze_render(os.path.expanduser(path), grid_cols=cols, grid_rows=rows, mask_watermark=mask_watermark)
    except Exception as e:
        return dumps({"ok": False, "error": str(e)})
    a["path"] = path
    return dumps(a)


def events(sess: AppSession, since: Optional[int], limit: int) -> str:
    if limit is None or int(limit) < 1:
        return dumps({"ok": False, "error": "limit must be >= 1"})
    try:
        r = sess.call("events", since=sess.events_seq if since is None else since, limit=limit)
    except (BridgeError, NotConnected) as e:
        return dumps({"ok": False, "error": str(e)})
    # advance the cursor only past what was returned: a truncated page is continued with its next_since
    sess.events_seq = int(r.get("next_since", r.get("seq", sess.events_seq)) if r.get("truncated") else r.get("seq", sess.events_seq))
    if r.get("truncated"):
        r["note"] = "more events than `limit`: call events(since=%d) for the rest" % sess.events_seq
    for e in r.get("events", []):
        e["t"] = _dt.datetime.fromtimestamp(e["t"]).strftime("%H:%M:%S.%f")[:-3]
    note = instance_note(sess)
    if note:
        r["instance"] = note
        try:
            others = [i for i in sess.client.describe_instances() if i.get("pid") != sess.client.info.get("pid")]
            active = [i for i in others if i.get("window_active")]
            if active:
                a = active[0]
                r["note"] = "The user is currently working in another %s window: pid %s%s (%s). Call connect(pid=%s) to act there." % (
                    sess.app, a.get("pid"), (" '%s'" % a["name"]) if a.get("name") else "",
                    ", ".join((a.get("objects") or a.get("models") or [])[:5]) or "empty", a.get("pid"))
        except Exception:
            pass
    return dumps(r)


def log(sess: AppSession, n: int) -> str:
    if n is None or int(n) < 1:
        return dumps({"ok": False, "error": "n must be >= 1"})
    try:
        r = sess.call("log", n=n)
    except (BridgeError, NotConnected) as e:
        return dumps({"ok": False, "error": str(e)})
    lines = []
    for l in r.get("lines", []):
        ts = _dt.datetime.fromtimestamp(l["t"]).strftime("%H:%M:%S")
        lines.append("%s %s%s" % (ts, ("[%s] " % l["level"]) if l.get("level") and l["level"] != "info" else "", l["text"]))
    return "\n".join(lines) if lines else "(log empty)"


def quit_app(sess: AppSession, confirm: bool = False) -> str:
    if not confirm:
        return dumps({"ok": False, "error": "refused: pass confirm=true after the user agreed to close the program"})
    try:
        sess.connect(auto_launch=False)
        r = sess.client.call("quit", timeout=10)
    except (BridgeError, NotConnected) as e:
        return dumps({"ok": False, "error": str(e)})
    sess.client.info = None
    return dumps(r)


def inapp_path(*parts: str) -> str:
    return os.path.join(INAPP_DIR, *parts)


# ---------------------------------------------------------------------------
# skills
# ---------------------------------------------------------------------------

def skills_index(app: str) -> str:
    from . import skills as sk
    return sk.index_text(app)


def skill_text(app: str, name: str) -> str:
    from . import skills as sk
    s = sk.get_skill(app, name)
    if not s:
        import difflib
        names = [x["name"] for x in sk.list_skills(app)]
        close = difflib.get_close_matches(name, names, n=5, cutoff=0.5)
        if not close:
            close = [n for n in names if any(t and t in n for t in re.split(r"[-_ ]+", name.lower()))][:5]
        return dumps({"ok": False, "error": "no skill named %r" % name, "did_you_mean": close, "available": names})
    return "# %s\n(%s skill '%s'%s)\n\n%s" % (s["title"], s["app"], s["name"], "" if s["source"] == "builtin" else ", user file " + s["path"], s["body"])


def save_skill(app: str, name: str, content: str) -> str:
    from . import skills as sk
    try:
        path = sk.save_user_skill(app, name, content)
    except Exception as e:
        return dumps({"ok": False, "error": str(e)})
    return dumps({"ok": True, "path": path, "note": "user skills override built-in ones with the same name"})


def register_skill_extras(mcp, app: str):
    """Expose skills also as MCP resources and prompts where the SDK supports it (tools always work)."""
    from . import skills as sk
    try:
        @mcp.resource("molmcp://%s/skills" % app, name="%s skills index" % app, description="Index of the available skills")
        def _skills_index() -> str:  # pragma: no cover - depends on SDK
            return sk.index_text(app)

        @mcp.resource("molmcp://%s/skills/{name}" % app, name="%s skill" % app, description="One skill by name")
        def _skill(name: str) -> str:  # pragma: no cover
            s = sk.get_skill(app, name)
            return s["body"] if s else "no such skill"
    except Exception:
        pass
    try:
        # one prompt per built-in skill so Claude Code lists them as /mcp__<app>__<skill-name>
        for s0 in sk.list_skills(app):
            def _make(name):
                def _p(task: str = "") -> str:
                    s1 = sk.get_skill(app, name)
                    return "Follow these %s instructions:\n\n%s\n\nTask: %s" % (app, s1["body"] if s1 else "", task or "as discussed")
                return _p
            try:
                mcp.prompt(name=s0["name"].replace("-", "_"), description=s0["description"] or s0["title"])(_make(s0["name"]))
            except Exception:
                pass
    except Exception:
        pass
    try:
        @mcp.prompt(name="use_skill", description="Load a %s skill and follow it for the given task" % app)
        def _use_skill(skill: str, task: str = "") -> str:  # pragma: no cover
            s = sk.get_skill(app, skill)
            body = s["body"] if s else "(skill %r not found; call the skills tool)" % skill
            return "Follow these %s instructions:\n\n%s\n\nTask: %s" % (app, body, task or "as discussed")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# structured convenience tools (run Python inside the app through the bridge)
# ---------------------------------------------------------------------------

def python_json(sess: AppSession, code: str, timeout: float = 600.0) -> str:
    """Run code that assigns `result`; return its JSON (or the error)."""
    try:
        r = sess.call("python", timeout=timeout, code=code)
    except (BridgeError, NotConnected) as e:
        return dumps({"ok": False, "error": str(e)})
    if not r.get("ok"):
        err = r.get("error") or "python code failed"
        if err.startswith(("ValueError:", "KeyError:", "TypeError:")):
            return dumps({"ok": False, "error": err.split(":", 1)[1].strip() if ":" in err else err,
                          "stdout": _trim(r.get("stdout"), 2000)})
        return dumps({"ok": False, "error": err, "traceback": _trim(r.get("traceback"), 2000), "stdout": _trim(r.get("stdout"), 2000)})
    out = r.get("result")
    if isinstance(out, dict):
        out.setdefault("ok", True)
        if r.get("changes"):
            out["changes"] = r["changes"]
    text = dumps(out)
    if len(text) > 120_000:
        return dumps({"ok": False, "error": "result too large (%d chars); use paging (max_rows/offset) or a narrower selection" % len(text)})
    return text

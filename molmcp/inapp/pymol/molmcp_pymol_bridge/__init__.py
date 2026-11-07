"""molmcp PyMOL bridge - lets an MCP server (Claude Code, Codex, ...) drive PyMOL.

Install as a PyMOL plugin (directory in your plugin startup path) or run the
launcher script with ``pymol -r molmcp_pymol_launch.py``.  Exposes the PyMOL
commands ``agent_start``, ``agent_stop``, ``agent_status`` and ``agent_info``
plus a "Plugin > Agent Bridge (MCP)" menu entry in the Qt GUI.

Only the standard library and PyMOL are required.
"""
from __future__ import annotations

import io
import os
import re
import sys
import tempfile
import threading
import time
import traceback
from collections import Counter, deque

from . import bridgecore
from .bridgecore import Bridge, Tee

__version__ = "0.1.0"

_bridge = None
_lock = threading.RLock()            # serialises dispatched operations (held while waiting for the GUI thread)
_lifecycle_lock = threading.RLock()  # start/stop only
_feedback = deque(maxlen=5000)       # (time, line) of everything PyMOL printed
_last_fp = None                      # fingerprint used by the events op
_orig_get_feedback = None
_shutdown = False
_window_active = None
_focus_timer = None


def _start_focus_poll():
    """GUI only: poll whether this PyMOL window has keyboard focus (used to pick the right window)."""
    global _focus_timer
    if _focus_timer is not None or not is_gui():
        return
    try:
        from pymol.Qt import QtCore

        def poll():
            global _window_active
            try:
                w = _qtwindow()
                _window_active = bool(w is not None and w.isActiveWindow())
            except Exception:
                _window_active = None
        _focus_timer = QtCore.QTimer()
        _focus_timer.timeout.connect(poll)
        _focus_timer.start(1000)
    except Exception:
        _focus_timer = None


def set_name(name=""):
    """`agent_name <name>`: label this window so an agent can pick it (shows in the MCP status tool)."""
    if _bridge is None:
        _log(" Agent bridge not running")
        return None
    n = _bridge.set_name(str(name))
    _log(" Agent bridge: this window is now named %r" % n)
    return n

REP_NAMES = {0: "sticks", 1: "spheres", 2: "surface", 3: "labels", 4: "nb_spheres", 5: "cartoon",
             6: "ribbon", 7: "lines", 8: "mesh", 9: "dots", 10: "dashes", 11: "nonbonded", 12: "cell",
             13: "cgo", 14: "callback", 15: "extent", 16: "slice", 17: "angles", 18: "dihedrals",
             19: "ellipsoids", 20: "volume"}

REP_COLOR_SETTINGS = ["cartoon_color", "ribbon_color", "surface_color", "mesh_color", "dot_color",
                      "sphere_color", "stick_color", "line_color", "label_color", "ellipsoid_color"]
OBJ_COLOR_SETTINGS = ["cartoon_nucleic_acid_color", "cartoon_ladder_color", "cartoon_ring_color"]
TRANSPARENCY_SETTINGS = ["transparency", "cartoon_transparency", "sphere_transparency", "stick_transparency",
                         "ribbon_transparency", "nonbonded_transparency", "ellipsoid_transparency",
                         "cgo_transparency", "label_transparency"]
FLAT_RENDER_SETTINGS = {
    "ambient": 1.0, "direct": 0.0, "reflect": 0.0, "specular": 0.0, "spec_direct": 0.0,
    "light_count": 1, "depth_cue": 0, "fog": 0, "ray_shadow": 0, "antialias": 0,
    "ray_trace_mode": 0, "ray_trace_fog": 0, "ambient_occlusion_mode": 0,
    "cartoon_discrete_colors": 1, "cartoon_highlight_color": -1, "ray_opaque_background": 1,
    "opaque_background": 1, "line_smooth": 0, "dot_lighting": 0, "mesh_lighting": 0,
    "label_shadow_mode": 0, "ray_interior_color": -1, "surface_color_smoothing": 0,
    "ray_trace_gain": 0.0, "spec_count": 0, "cartoon_smooth_loops": 0,
}
INTERESTING_SETTINGS = [
    "bg_rgb", "ray_opaque_background", "opaque_background", "antialias", "ray_trace_mode", "ray_shadow",
    "light_count", "ambient", "specular", "depth_cue", "fog", "orthoscopic", "field_of_view",
    "transparency", "cartoon_transparency", "sphere_transparency", "stick_transparency",
    "cartoon_fancy_helices", "cartoon_side_chain_helper", "cartoon_cylindrical_helices", "cartoon_putty_scale_min",
    "stick_radius", "sphere_scale", "surface_quality", "valence", "label_size", "cartoon_highlight_color",
    "ray_trace_frames", "scene_animation", "movie_fps", "stereo", "dash_width", "seq_view", "auto_zoom",
    "surface_mode", "surface_color_smoothing", "spec_reflect", "ray_trace_gain", "ambient_occlusion_mode",
]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _pymol():
    import pymol
    return pymol


def _cmd():
    from pymol import cmd
    return cmd


_LICENSE_STATE = None


def _unlicensed():
    """True when this PyMOL has no valid licence: incentive builds then burn an evaluation text banner into
    every ray-traced frame, which the server's image analysis masks out."""
    global _LICENSE_STATE
    if _LICENSE_STATE is None:
        state = False
        try:
            from pymol import licensing
            info = licensing.get_license_info()
            state = bool((not info.is_valid()) or info.is_eval() or info.is_expired())
        except Exception:
            state = False
        _LICENSE_STATE = state
    return _LICENSE_STATE


class _FdCapture:
    """Capture what C code writes to file descriptors 1/2 while a command runs.

    Headless PyMOL prints its command feedback ("Executive: RMSD = ...", "ObjectMolecule: ...") straight to
    the C stdout, which neither ``sys.stdout`` nor ``cmd._get_feedback()`` ever sees.
    """

    def __init__(self, enabled=True):
        self.enabled = enabled
        self.text = ""
        self._tmp = None
        self._saved = None

    def __enter__(self):
        if not self.enabled:
            return self
        try:
            sys.__stdout__.flush()
            sys.__stderr__.flush()
        except Exception:
            pass
        try:
            self._tmp = tempfile.TemporaryFile(mode="w+b")
            self._saved = (os.dup(1), os.dup(2))
            os.dup2(self._tmp.fileno(), 1)
            os.dup2(self._tmp.fileno(), 2)
        except Exception:
            self._tmp = None
            self._saved = None
        return self

    @staticmethod
    def _flush_c():
        try:
            import ctypes
            if sys.platform.startswith("win"):
                ctypes.cdll.msvcrt.fflush(None)
            else:
                ctypes.CDLL(None).fflush(None)
        except Exception:
            pass

    def __exit__(self, *exc):
        if self._tmp is None:
            return False
        self._flush_c()
        try:
            os.dup2(self._saved[0], 1)
            os.dup2(self._saved[1], 2)
            os.close(self._saved[0])
            os.close(self._saved[1])
            self._tmp.seek(0)
            self.text = self._tmp.read().decode("utf-8", "replace")
        except Exception:
            self.text = ""
        finally:
            try:
                self._tmp.close()
            except Exception:
                pass
        for line in self.text.splitlines():
            if line.strip():
                _feedback.append((time.time(), _strip_ansi(line)))
        return False


def _undo_guard(changes):
    """Work around a PyMOL 3.1 bug: once the undo history is active, deleting an object and reloading the same
    name leaves the live object unselectable ("Invalid selection name") as soon as the undo record of the
    deletion is evicted (about 30 undoable commands later).  Headless sessions have no user who could undo, so
    undo stays disabled; in the GUI the history is cleared whenever an agent command removed objects."""
    cmd = _cmd()
    try:
        if not is_gui():
            if cmd.undo_is_enabled():
                cmd.undo_disable()
            return
        if any(c.get("change") == "objects_removed" for c in (changes or [])) and cmd.undo_is_enabled():
            cmd.undo_clear_cache()
    except Exception:
        pass


def is_gui() -> bool:
    try:
        return not int(getattr(_pymol().invocation.options, "no_gui", 0))
    except Exception:
        return False


def _qtwindow():
    try:
        from pymol import gui
        return gui.get_qtwindow()
    except Exception:
        return None


def _log(msg: str):
    if not isinstance(sys.stdout, _StdoutRecorder):
        _feedback.append((time.time(), msg))
    try:
        print(msg)
    except Exception:
        pass


def on_main(fn):
    """Run ``fn`` on PyMOL's GUI thread (blocking) or directly when headless."""
    cmd = _cmd()
    caller = getattr(cmd, "_call_in_gui_thread", None)
    if caller is None:
        return fn()
    return caller(fn)


def _install_feedback_tee():
    """Wrap cmd._get_feedback so everything the GUI drains is also recorded."""
    global _orig_get_feedback
    cmd = _cmd()
    if _orig_get_feedback is not None:
        return
    orig = cmd._get_feedback
    _orig_get_feedback = orig

    def tee(*a, **kw):
        lines = orig(*a, **kw)
        if lines:
            now = time.time()
            for line in lines:
                line = _strip_ansi(line)
                _feedback.append((now, line))
                if _bridge is not None and line.startswith("PyMOL>"):
                    _bridge.touch()
                if _bridge is not None and (line.startswith("PyMOL>") or line.startswith("Error") or " Error" in line or line.startswith("Traceback")):
                    _bridge.events.add("log", text=line)
        return lines

    cmd._get_feedback = tee


def _show_in_gui(lines):
    """Echo text into the Qt GUI output panel (we may have stolen it from the feedback queue)."""
    if not lines:
        return
    w = _qtwindow()
    if w is None:
        return
    try:
        from pymol import colorprinting
        w.browser.appendHtml(colorprinting.text2html("\n".join(lines)))
        sb = w.browser.verticalScrollBar()
        sb.setValue(sb.maximum())
    except Exception:
        pass


_ANSI_RE = None


def _strip_ansi(s):
    global _ANSI_RE
    if _ANSI_RE is None:
        import re
        _ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
    return _ANSI_RE.sub("", s)


def _decode_color_value(v, color_names=None):
    """PyMOL colour setting -> (name, [r,g,b] in 0-255)."""
    cmd = _cmd()
    try:
        if isinstance(v, (list, tuple)):
            if len(v) == 3 and all(isinstance(x, float) for x in v):
                return "rgb", [int(round(x * 255)) for x in v]
            v = v[0]
        v = int(v)
        if v >= 0x40000000:
            return "rgb", [(v >> 16) & 255, (v >> 8) & 255, v & 255]
        if v < 0:
            return "default", None
        rgb = cmd.get_color_tuple(v)
        name = None
        if color_names is not None:
            name = color_names.get(v)
        if name is None:
            for n, i in cmd.get_color_indices(all=1):
                if i == v:
                    name = n
                    break
        if name is not None and re.match(r"^[a-z]\d{3,4}$", name):
            name = None          # spectrum / auto colour slot: report the nearest real colour name instead
        if name is None and rgb:
            try:
                from pymol import colornames  # noqa: F401  (not in every build)
            except Exception:
                pass
            # last resort: nearest of the standard palette names PyMOL ships
            best, bd = None, 1e9
            for n, i in cmd.get_color_indices():
                if re.match(r"^[a-z]\d{3,4}$", n):
                    continue
                t = cmd.get_color_tuple(i)
                if t:
                    d = sum((a - b) ** 2 for a, b in zip(t, rgb))
                    if d < bd:
                        best, bd = n, d
            name = best if bd < 0.02 else None
        return name or "index_%d" % v, [int(round(x * 255)) for x in rgb] if rgb else None
    except Exception:
        return str(v), None


def _setting_value(name, obj=None):
    cmd = _cmd()
    try:
        t, v = cmd.get_setting_tuple(name, obj) if obj else cmd.get_setting_tuple(name)
    except Exception:
        return None
    if isinstance(v, (list, tuple)) and len(v) == 1:
        v = v[0]
    return v


def _setting_display(name, obj=None):
    v = _setting_value(name, obj)
    if name.endswith("color") or name == "bg_rgb":
        cname, rgb = _decode_color_value(v)
        return {"name": cname, "rgb": rgb}
    return v


def _background_rgb():
    cname, rgb = _decode_color_value(_setting_value("bg_rgb"))
    return rgb or [0, 0, 0], cname


# ---------------------------------------------------------------------------
# state fingerprint & diff (makes every response "aware" of what changed)
# ---------------------------------------------------------------------------

def fingerprint():
    cmd = _cmd()
    objs = cmd.get_names("objects")
    sels = cmd.get_names("selections")
    enabled = cmd.get_names("objects", enabled_only=1)
    vis = cmd.get_vis()
    view = tuple(round(float(x), 3) for x in cmd.get_view())
    n_atoms = {}
    for o in objs:
        try:
            if cmd.get_type(o) == "object:molecule":
                n_atoms[o] = cmd.count_atoms("%" + o)
        except Exception:
            pass
    try:
        sele_atoms = cmd.count_atoms("%sele") if "sele" in sels else 0
    except Exception:
        sele_atoms = 0
    colours = {}
    for o in objs:
        try:
            v = vis.get(o)
            colours[o] = v[3] if v else None
            if o in n_atoms and n_atoms[o] <= 50000:
                acc = []
                cmd.iterate("%" + o, "_a.append(color)", space={"_a": acc})
                colours[o] = (colours[o], sum(acc), len(set(acc)))
        except Exception:
            pass
    rep_counts = {}
    for o in objs:
        if o in n_atoms:
            try:
                rep_counts[o] = tuple(cmd.count_atoms("(rep %s) and %%%s" % (rep, o)) for rep in ("cartoon", "sticks", "spheres", "surface", "lines", "ribbon", "mesh", "dots"))
            except Exception:
                pass
    try:
        n_frames = cmd.count_frames()
    except Exception:
        n_frames = 0
    settings = {}
    for s_ in INTERESTING_SETTINGS:
        try:
            settings[s_] = _setting_value(s_)
        except Exception:
            pass
    obj_colors = {}
    levels = {}
    for o in objs:
        if o in n_atoms:
            continue
        try:
            typ = cmd.get_type(o)
            if typ in ("object:mesh", "object:surface", "object:map", "object:slice", "object:volume", "object:cgo"):
                obj_colors[o] = cmd.get_object_color_index(o)
            if typ in ("object:mesh", "object:surface"):
                levels[o] = round(float(cmd.isolevel(o, 0.0, query=1)), 4)
        except Exception:
            pass
    try:
        viewport = tuple(int(x) for x in cmd.get_viewport())
    except Exception:
        viewport = None
    fp = {
        "objects": objs,
        "settings": settings,
        "obj_colors": obj_colors,
        "levels": levels,
        "viewport": viewport,
        "enabled": enabled,
        "selections": sels,
        "n_atoms": n_atoms,
        "rep_counts": rep_counts,
        "frames": n_frames,
        "colours": colours,
        "reps": {o: tuple(vis.get(o, [None, [], [], None])[2] or []) for o in objs},
        "view": view,
        "state": cmd.get_state(),
        "frame": cmd.get_frame(),
        "sele_atoms": sele_atoms,
        "scenes": list(cmd.get_scene_list()),
    }
    return fp


def diff_fingerprints(a, b):
    if a is None:
        return []
    ch = []
    added = [o for o in b["objects"] if o not in a["objects"]]
    removed = [o for o in a["objects"] if o not in b["objects"]]
    if added:
        ch.append({"change": "objects_added", "names": added})
    if removed:
        ch.append({"change": "objects_removed", "names": removed})
    en = [o for o in b["enabled"] if o not in a["enabled"] and o in a["objects"]]
    dis = [o for o in a["enabled"] if o not in b["enabled"] and o in b["objects"]]
    if en:
        ch.append({"change": "objects_enabled", "names": en})
    if dis:
        ch.append({"change": "objects_disabled", "names": dis})
    for o, n in b["n_atoms"].items():
        if o in a["n_atoms"] and a["n_atoms"][o] != n:
            ch.append({"change": "atom_count", "object": o, "from": a["n_atoms"][o], "to": n})
    rep_order = ("cartoon", "sticks", "spheres", "surface", "lines", "ribbon", "mesh", "dots")
    for o, counts in b.get("rep_counts", {}).items():
        old_c = a.get("rep_counts", {}).get(o)
        if old_c is not None and old_c != counts:
            ch.append({"change": "representations", "object": o,
                       "atoms_per_rep": {r: n for r, n in zip(rep_order, counts) if n},
                       "was": {r: n for r, n in zip(rep_order, old_c) if n}})
    if a.get("frames") != b.get("frames"):
        ch.append({"change": "movie_frames", "from": a.get("frames"), "to": b.get("frames")})
    for o, col in b.get("colours", {}).items():
        if o in a.get("colours", {}) and a["colours"][o] != col:
            ch.append({"change": "colours", "object": o, "detail": "atom/object colours changed"})
    for o, col in b.get("obj_colors", {}).items():
        if o in a.get("obj_colors", {}) and a["obj_colors"][o] != col:
            ch.append({"change": "colours", "object": o, "detail": "object colour changed",
                       "to": _decode_color_value(col)[0]})
    for o, lv in b.get("levels", {}).items():
        if o in a.get("levels", {}) and a["levels"][o] != lv:
            ch.append({"change": "isolevel", "object": o, "from": a["levels"][o], "to": lv})
    sa_ = a.get("settings", {})
    changed_settings = {k: v for k, v in b.get("settings", {}).items() if k in sa_ and sa_[k] != v}
    if changed_settings:
        ch.append({"change": "settings", "settings": {k: {"from": _display_setting_value(k, sa_[k]),
                                                           "to": _display_setting_value(k, v)}
                                                       for k, v in changed_settings.items()}})
    if a.get("viewport") and b.get("viewport") and a["viewport"] != b["viewport"]:
        ch.append({"change": "viewport", "from": list(a["viewport"]), "to": list(b["viewport"])})
    sa = [s for s in b["selections"] if s not in a["selections"]]
    sr = [s for s in a["selections"] if s not in b["selections"]]
    if sa:
        ch.append({"change": "selections_added", "names": sa})
    if sr:
        ch.append({"change": "selections_removed", "names": sr})
    if a["sele_atoms"] != b["sele_atoms"]:
        ch.append({"change": "sele_atoms", "from": a["sele_atoms"], "to": b["sele_atoms"]})
    if a["view"] != b["view"]:
        ch.append({"change": "view", "detail": _describe_view_change(a["view"], b["view"])})
    if a["state"] != b["state"] or a["frame"] != b["frame"]:
        ch.append({"change": "state_or_frame", "state": b["state"], "frame": b["frame"]})
    if a["scenes"] != b["scenes"]:
        ch.append({"change": "scenes", "scenes": b["scenes"]})
    return ch


def _display_setting_value(name, v):
    if name.endswith("color") or name == "bg_rgb":
        try:
            cname, rgb = _decode_color_value(v)
            return {"name": cname, "rgb": rgb}
        except Exception:
            return v
    return v


def _describe_view_change(a, b):
    rot = any(abs(a[i] - b[i]) > 1e-3 for i in range(9))
    zoom = abs(a[11] - b[11]) > 1e-3
    pan = any(abs(a[i] - b[i]) > 1e-3 for i in range(9, 11))
    origin = any(abs(a[i] - b[i]) > 1e-3 for i in range(12, 15))
    clip = any(abs(a[i] - b[i]) > 1e-3 for i in range(15, 17))
    bits = []
    if rot:
        bits.append("rotated")
    if zoom:
        bits.append("zoomed (camera distance %.1f -> %.1f)" % (-a[11], -b[11]))
    if pan:
        bits.append("panned (camera offset %.1f, %.1f -> %.1f, %.1f)" % (a[9], a[10], b[9], b[10]))
    if origin:
        bits.append("rotation origin moved")
    if clip:
        bits.append("clipping changed")
    if a[17] != b[17]:
        bits.append("orthoscopic toggled")
    return ", ".join(bits) or "minor"


# ---------------------------------------------------------------------------
# operations
# ---------------------------------------------------------------------------

def op_ping(args):
    cmd = _cmd()
    try:
        version = cmd.get_version()[0]
    except Exception:
        version = "?"
    busy = not _lock.acquire(blocking=False)
    if not busy:
        _lock.release()
    out = {"app": "pymol", "version": version, "pid": os.getpid(), "gui": is_gui(), "watermark": _unlicensed(),
           "events_seq": _bridge.events.seq if _bridge else 0, "cwd": os.getcwd(), "main_thread_busy": busy,
           "name": _bridge.name if _bridge else "", "last_activity": _bridge.last_activity if _bridge else None,
           "window_active": _window_active}
    try:
        out["viewport"] = list(cmd.get_viewport())
        names = cmd.get_names("public_objects")
        out["n_objects"] = len(names)
        out["objects"] = names[:8]
    except Exception:
        pass
    return out


def _run_one(line: str, echo: bool, log: bool):
    cmd = _cmd()
    pre = cmd._get_feedback()          # whatever was pending belongs to earlier activity
    _show_in_gui(pre)
    out_tee = Tee(sys.stdout)
    err_tee = Tee(sys.stderr)
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = out_tee, err_tee
    t0 = time.time()
    fdcap = _FdCapture(enabled=not is_gui())
    try:
        if echo:
            try:
                from pymol import colorprinting
                colorprinting.parrot("PyMOL>" + line)
            except Exception:
                pass
        with fdcap:
            result = cmd._parser.parse(line, 0)
    finally:
        sys.stdout, sys.stderr = old_out, old_err
    post = cmd._get_feedback() or []
    _show_in_gui(post)
    text = _strip_ansi(out_tee.getvalue() + err_tee.getvalue() + fdcap.text)
    lines = [l for l in text.splitlines() if l.strip()] + [_strip_ansi(l) for l in post if l.strip() and not _strip_ansi(l).startswith("PyMOL>")]
    if log:
        try:
            cmd.log(line + "\n", "cmd.do('%s')\n" % line.replace("'", "\\'"))
        except Exception:
            pass
    ok = result == 1
    err = None
    if not ok:
        err_lines = [l for l in lines if "Error" in l or "error" in l or l.startswith("Traceback") or "Exception" in l]
        err = (err_lines[-1] if err_lines else (lines[-1] if lines else "command failed")).strip()
    return {"command": line, "ok": ok, "output": "\n".join(lines), "error": err,
            "ms": round((time.time() - t0) * 1000, 1)}


def op_run(args):
    cmds = args.get("commands")
    if isinstance(cmds, str):
        cmds = [c for c in cmds.splitlines()]
    cmds = [c for c in (cmds or []) if c and c.strip()]
    echo = bool(args.get("echo", True))
    log = bool(args.get("log", False))
    stop_on_error = bool(args.get("stop_on_error", True))
    global _last_fp
    before = fingerprint()
    results = []
    for c in cmds:
        r = _run_one(c.strip(), echo, log)
        results.append(r)
        if _bridge:
            _bridge.events.add("agent_command", command=c.strip(), ok=r["ok"], error=r.get("error"))
        if not r["ok"] and stop_on_error:
            break
    after = fingerprint()
    changes = diff_fingerprints(before, after)
    _last_fp = after
    _undo_guard(changes)
    return {"results": results, "all_ok": all(r["ok"] for r in results), "changes": changes,
            "executed": len(results), "requested": len(cmds)}


def op_python(args):
    code = args.get("code", "")
    cmd = _cmd()
    pymol = _pymol()
    ns = {"cmd": cmd, "pymol": pymol, "stored": pymol.stored, "__name__": "__molmcp__"}
    out_tee = Tee(sys.stdout)
    err_tee = Tee(sys.stderr)
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = out_tee, err_tee
    before = fingerprint()
    error = None
    tb = None
    t0 = time.time()
    fdcap = _FdCapture(enabled=not is_gui())
    try:
        with fdcap:
            exec(compile(code, "<molmcp>", "exec"), ns, ns)
    except (Exception, SystemExit, KeyboardInterrupt) as e:
        error = "%s: %s" % (type(e).__name__, e)
        tb = traceback.format_exc()
    finally:
        sys.stdout, sys.stderr = old_out, old_err
    post = cmd._get_feedback() or []
    _show_in_gui(post)
    after = fingerprint()
    global _last_fp
    _last_fp = after
    changes = diff_fingerprints(before, after)
    _undo_guard(changes)
    if _bridge:
        _bridge.events.add("agent_python", ok=error is None, chars=len(code), error=error)
    return {"ok": error is None, "stdout": _strip_ansi(out_tee.getvalue() + err_tee.getvalue() + fdcap.text + "\n".join(post)),
            "result": bridgecore.json_safe(ns.get("result")), "error": error, "traceback": tb,
            "changes": changes, "ms": round((time.time() - t0) * 1000, 1)}


def _view_dict(view):
    v = [float(x) for x in view]
    return {
        "raw": v,
        "rotation_matrix": [v[0:3], v[3:6], v[6:9]],
        "camera_offset": v[9:12],
        "distance": -v[11],
        "origin": v[12:15],
        "clip_front": v[15],
        "clip_back": v[16],
        "orthoscopic": v[17] > 0,
    }


def _object_summary(name, detail, color_names):
    cmd = _cmd()
    pymol = _pymol()
    typ = cmd.get_type(name)
    vis = cmd.get_vis().get(name, [1, [], [], None])
    info = {"name": name, "type": typ.replace("object:", ""), "enabled": bool(vis[0])}
    try:
        ext = cmd.get_extent("%" + name)
        if ext and ext[0][0] < 1e30:
            info["extent"] = [[round(x, 2) for x in ext[0]], [round(x, 2) for x in ext[1]]]
            info["center"] = [round((ext[0][i] + ext[1][i]) / 2, 2) for i in range(3)]
            info["size"] = [round(ext[1][i] - ext[0][i], 2) for i in range(3)]
    except Exception:
        pass
    if typ == "object:molecule":
        n = cmd.count_atoms("%" + name)
        info["atoms"] = n
        info["states"] = cmd.count_states("%" + name)
        info["chains"] = cmd.get_chains("%" + name)
        try:
            info["title"] = cmd.get_title(name, 1)
        except Exception:
            pass
        if detail == "full" and n <= 400000:
            acc = {}
            rep_counts = Counter()
            het = Counter()
            total_res = set()
            ss = Counter()

            def collect(chain, resn, resi, resv, color, reps, ss_, typ_):
                key = chain
                d = acc.get(key)
                if d is None:
                    d = acc[key] = {"atoms": 0, "residues": set(), "colors": Counter(), "reps": 0,
                                    "resv_min": None, "resv_max": None, "polymer_atoms": 0, "het": Counter()}
                d["atoms"] += 1
                d["residues"].add(resi)
                total_res.add((chain, resi))
                d["colors"][color] += 1
                d["reps"] |= reps
                if typ_ == "HETATM":
                    d["het"][resn] += 1
                    het[resn] += 1
                else:
                    d["polymer_atoms"] += 1
                    if d["resv_min"] is None or resv < d["resv_min"]:
                        d["resv_min"] = resv
                    if d["resv_max"] is None or resv > d["resv_max"]:
                        d["resv_max"] = resv
                    ss[ss_ or "L"] += 1
                for bit, rname in REP_NAMES.items():
                    if reps & (1 << bit):
                        rep_counts[rname] += 1

            cmd.iterate("%" + name, "_collect(chain, resn, resi, resv, color, reps, ss, type)", space={"_collect": collect})
            chains = []
            for chain, d in sorted(acc.items()):
                top = d["colors"].most_common(3)
                chains.append({
                    "chain": chain,
                    "atoms": d["atoms"],
                    "residues": len(d["residues"]),
                    "polymer_residue_range": [d["resv_min"], d["resv_max"]] if d["resv_min"] is not None else None,
                    "hetero": dict(d["het"].most_common(8)),
                    "reps_shown": [REP_NAMES[b] for b in REP_NAMES if d["reps"] & (1 << b)],
                    "top_colors": [{"name": _decode_color_value(ci, color_names)[0],
                                    "rgb": _decode_color_value(ci, color_names)[1],
                                    "share": round(cnt / d["atoms"], 3)} for ci, cnt in top],
                })
            info["chain_details"] = chains
            info["residues"] = len(total_res)
            info["reps_atom_counts"] = dict(rep_counts)
            info["hetero_residues"] = dict(het.most_common(12))
            if ss:
                tot = sum(ss.values())
                info["secondary_structure_atoms"] = {k: round(v / tot, 3) for k, v in ss.items()}
        overrides = {}
        for s in REP_COLOR_SETTINGS + TRANSPARENCY_SETTINGS + ["stick_radius", "sphere_scale", "cartoon_transparency"]:
            try:
                vo = _setting_value(s, name)
                vg = _setting_value(s)
                if vo != vg:
                    overrides[s] = _setting_display(s, name)
            except Exception:
                pass
        if overrides:
            info["setting_overrides"] = overrides
    elif typ in ("object:map", "object:mesh", "object:surface", "object:slice", "object:volume", "object:cgo"):
        try:
            ci = cmd.get_object_color_index(name)
            if ci is not None and int(ci) >= 0:
                cname, rgb = _decode_color_value(ci, color_names)
                info["color"] = {"name": cname, "rgb": rgb}
        except Exception:
            pass
        if typ in ("object:mesh", "object:surface"):
            try:
                info["isolevel"] = round(float(cmd.isolevel(name, 0.0, query=1)), 4)
            except Exception:
                pass
        for s in ("mesh_color", "surface_color", "transparency", "mesh_width"):
            try:
                vo = _setting_value(s, name)
                vg = _setting_value(s)
                if vo != vg:
                    info.setdefault("setting_overrides", {})[s] = _setting_display(s, name)
            except Exception:
                pass
    return info


def op_scene(args):
    cmd = _cmd()
    detail = args.get("detail", "summary")
    only = args.get("objects")
    color_names = {i: n for n, i in cmd.get_color_indices()}
    names = cmd.get_names("public_objects")
    if only:
        names = [n for n in names if n in only]
    objects = []
    for n in names:
        try:
            objects.append(_object_summary(n, detail, color_names))
        except Exception as e:
            objects.append({"name": n, "error": "%s: %s" % (type(e).__name__, str(e).strip().splitlines()[0] if str(e).strip() else "")})
    sels = []
    for s in cmd.get_names("public_selections"):
        try:
            sels.append({"name": s, "atoms": cmd.count_atoms("%" + s)})
        except Exception:
            sels.append({"name": s})
    bg, bg_name = _background_rgb()
    settings = {}
    for s in INTERESTING_SETTINGS:
        try:
            settings[s] = _setting_display(s)
        except Exception:
            pass
    groups = cmd.get_names("group_objects") if hasattr(cmd, "get_names") else []
    res = {
        "app": "pymol",
        "gui": is_gui(),
        "viewport": list(cmd.get_viewport()),
        "objects": objects,
        "groups": groups,
        "selections": sels,
        "view": _view_dict(cmd.get_view()),
        "background": {"rgb": bg, "name": bg_name},
        "state": cmd.get_state(),
        "frames": cmd.count_frames(),
        "frame": cmd.get_frame(),
        "scenes": list(cmd.get_scene_list()),
        "wizard": str(cmd.get_wizard()) if cmd.get_wizard() else None,
        "settings": settings,
        "events_seq": _bridge.events.seq if _bridge else 0,
    }
    global _last_fp
    _last_fp = fingerprint()
    return res


def op_object_info(args):
    cmd = _cmd()
    name = args["name"]
    if name not in cmd.get_names("objects"):
        raise ValueError("no object named %r (have: %s)" % (name, ", ".join(cmd.get_names("objects"))))
    color_names = {i: n for n, i in cmd.get_color_indices()}
    return _object_summary(name, "full", color_names)


def _compact_ranges(values):
    vals = sorted(set(values))
    out = []
    start = prev = None
    for v in vals:
        if start is None:
            start = prev = v
        elif v == prev + 1:
            prev = v
        else:
            out.append("%d" % start if start == prev else "%d-%d" % (start, prev))
            start = prev = v
    if start is not None:
        out.append("%d" % start if start == prev else "%d-%d" % (start, prev))
    return out


def op_selection_info(args):
    cmd = _cmd()
    pymol = _pymol()
    sel = args["selection"]
    n = cmd.count_atoms(sel)
    out = {"selection": sel, "atoms": n}
    if n == 0:
        return out
    per_obj = {}
    data = []
    limit = int(args.get("max_atoms", 200000))
    if n <= limit:
        cmd.iterate(sel, "_data.append((model, chain, resn, resi, resv, name, elem, ss, color, reps))",
                    space={"_data": data})
        for model, chain, resn, resi, resv, name, elem, ss, color, reps in data:
            d = per_obj.setdefault(model, {}).setdefault(chain, {"atoms": 0, "residues": {}, "elems": Counter(), "ss": {}})
            d["atoms"] += 1
            d["residues"][(resi, resn)] = resv
            d["elems"][elem] += 1
            if ss:
                d["ss"][(resi, resn)] = ss
        objs = []
        for model, chains in per_obj.items():
            cl = []
            for chain, d in sorted(chains.items()):
                plain = [rv for (ri, _), rv in d["residues"].items() if ri.lstrip("-").isdigit()]
                with_icode = sorted({ri for (ri, _) in d["residues"] if not ri.lstrip("-").isdigit()},
                                    key=lambda r_: (int(re.match(r"-?\d+", r_).group()) if re.match(r"-?\d+", r_) else 0, r_))
                ranges = _compact_ranges(plain) + with_icode
                resnames = Counter(rn for (_, rn) in d["residues"].keys())
                entry = {"chain": chain, "atoms": d["atoms"], "residues": len(d["residues"]),
                         "residue_ranges": ranges[:40],
                         "residue_names": dict(resnames.most_common(10)),
                         "elements": dict(d["elems"].most_common(8)),
                         "ss_residues": dict(Counter(d["ss"].values()))}
                if len(ranges) > 40:
                    entry["residue_ranges_truncated"] = True
                    entry["residue_ranges_total"] = len(ranges)
                if with_icode:
                    entry["insertion_codes"] = with_icode[:40]
                cl.append(entry)
            objs.append({"object": model, "chains": cl})
        out["by_object"] = objs
        out["residues"] = sum(len(d["residues"]) for ch in per_obj.values() for d in ch.values())
    try:
        ext = cmd.get_extent(sel)
        out["extent"] = [[round(x, 2) for x in ext[0]], [round(x, 2) for x in ext[1]]]
        out["center"] = [round((ext[0][i] + ext[1][i]) / 2, 2) for i in range(3)]
    except Exception:
        pass
    return out


def op_get_view(args):
    return _view_dict(_cmd().get_view())


def op_set_view(args):
    cmd = _cmd()
    view = args.get("view")
    if not view or len(view) != 18:
        raise ValueError("view must be a list of 18 numbers (as returned by get_view)")
    import math
    vals = [float(x) for x in view]
    if any(math.isnan(v) or math.isinf(v) for v in vals):
        raise ValueError("view contains non-finite values")
    cmd.set_view(vals)
    if args.get("animate"):
        pass
    return _view_dict(cmd.get_view())


_LAST_PNG_FALLBACK = None


def _png(width, height, ray, dpi, transparent):
    """PNG bytes of the current view.  GUI: offscreen draw + "prior" image; when that yields nothing (no usable
    OpenGL: remote desktop, VM, CI runner) the ray tracer is used instead, which needs no OpenGL at all."""
    global _LAST_PNG_FALLBACK
    cmd = _cmd()
    _LAST_PNG_FALLBACK = None
    saved = {}
    for s in ("ray_opaque_background", "opaque_background"):
        saved[s] = _setting_value(s)
        cmd.set(s, 0 if transparent else 1)
    try:
        data = None
        if is_gui() and not ray:
            # In the Qt GUI an in-memory PNG at an explicit size is only available
            # as the "prior" image of an offscreen draw.
            try:
                cmd.draw(int(width or 0), int(height or 0), antialias=-1, quiet=1)
                data = cmd.png("", 0, 0, float(dpi or -1), 0, quiet=1, prior=1)
            except Exception as e:
                data = None
                _LAST_PNG_FALLBACK = "offscreen draw failed (%s)" % str(e).strip().splitlines()[0] if str(e).strip() else "offscreen draw failed"
            if not data:
                _LAST_PNG_FALLBACK = _LAST_PNG_FALLBACK or "offscreen draw returned no image (no usable OpenGL?)"
                data = cmd.png("", int(width or 0), int(height or 0), float(dpi or -1), 1, quiet=1)
                if data:
                    _LAST_PNG_FALLBACK += "; rendered with the ray tracer instead"
        else:
            data = cmd.png("", int(width or 0), int(height or 0), float(dpi or -1), int(ray), quiet=1)
    finally:
        for s, v in saved.items():
            cmd.set(s, v)
    if not data:
        raise RuntimeError("PyMOL returned no image data")
    return data


MAX_RENDER_PIXELS = 16_000_000


def _frame_size(args):
    """Explicit size, or the current viewport when 0 (PyMOL would otherwise hand back its cached image)."""
    cmd = _cmd()
    width = int(args.get("width") or 0)
    height = int(args.get("height") or 0)
    if (width and width < 16) or (height and height < 16) or width < 0 or height < 0:
        raise ValueError("width/height must be >= 16 (or 0 for the viewport size)")
    if not width or not height:
        try:
            vw, vh = (int(x) for x in cmd.get_viewport())
        except Exception:
            vw, vh = 0, 0
        if vw < 16 or vh < 16:
            vw, vh = 800, 600
        width, height = width or vw, height or vh
    return width, height


def op_render(args):
    cmd = _cmd()
    width, height = _frame_size(args)
    if width * height > MAX_RENDER_PIXELS:
        raise ValueError("frame too large (%dx%d > %d pixels)" % (width, height, MAX_RENDER_PIXELS))
    ray = int(bool(args.get("ray", False)))
    dpi = float(args.get("dpi") or -1)
    transparent = bool(args.get("transparent", False))
    path = args.get("path")
    t0 = time.time()
    data = _png(width, height, ray, dpi, transparent)
    if path:
        path = cmd.exp_path(path)
        if not path.lower().endswith(".png"):
            path += ".png"
        with open(path, "wb") as f:
            f.write(data)
    bg, bg_name = _background_rgb()
    if _bridge:
        _bridge.events.add("agent_render", width=width, height=height, ray=ray)
    out = {"png": data, "path": path, "ray": bool(ray) or bool(_LAST_PNG_FALLBACK), "background": {"rgb": bg, "name": bg_name},
           "transparent": transparent, "ms": round((time.time() - t0) * 1000, 1), "viewport": list(cmd.get_viewport()),
           "width": width, "height": height, "watermark": _unlicensed()}
    if _LAST_PNG_FALLBACK:
        out["fallback"] = _LAST_PNG_FALLBACK
    return out


def op_render_ids(args):
    """ID pass: draw every item in its own flat colour, restore everything afterwards."""
    cmd = _cmd()
    items = args.get("items") or []
    width, height = _frame_size(args)
    ray = int(bool(args.get("ray", False)))
    solo = bool(args.get("solo", False))
    if not items:
        raise ValueError("items required: [{label, selection, rgb}]")
    if width * height > MAX_RENDER_PIXELS:
        raise ValueError("bad frame size %dx%d" % (width, height))
    t_start = time.time()
    _undo_guard(None)            # headless: undo stays off (PyMOL 3.1 name-reuse bug, see _undo_guard)
    all_objects = cmd.get_names("objects")
    molecular = {o for o in all_objects if cmd.get_type(o) == "object:molecule"}

    def _bare_object(selection):
        """Object name when the selection is just one (non-molecular) object, else None."""
        name = selection.strip()
        while name.startswith("(") and name.endswith(")"):
            name = name[1:-1].strip()
        name = name.lstrip("%").strip()
        if name in all_objects and name not in molecular:
            return name
        return None

    errors = {}
    nonmol = {}                     # item index -> object name
    nonmol_colors = {}              # object name -> original colour index
    for i, it in enumerate(items):
        name = _bare_object(str(it.get("selection", "")))
        if name:
            nonmol[i] = name
            try:
                nonmol_colors[name] = cmd.get_object_color_index(name)
            except Exception:
                nonmol_colors[name] = None
    cmd.scene("_molmcp_idpass", "store", view=0, active=1, color=1, rep=1, frame=0, quiet=1)
    saved_global = {}
    obj_overrides = []           # (setting, object, value) to restore
    involved_objects = set()
    for it in items:
        try:
            involved_objects.update(cmd.get_object_list("(%s)" % it["selection"]) or [])
        except Exception:
            pass
    try:
        for s, v in FLAT_RENDER_SETTINGS.items():
            try:
                saved_global[s] = _setting_value(s)
                cmd.set(s, v, quiet=1)
            except Exception:
                saved_global.pop(s, None)
        saved_global["bg_rgb"] = _setting_value("bg_rgb")
        cmd.set("bg_rgb", [0.0, 0.0, 0.0], quiet=1)
        for s in TRANSPARENCY_SETTINGS:
            try:
                saved_global[s] = _setting_value(s)
                cmd.set(s, 0, quiet=1)
            except Exception:
                saved_global.pop(s, None)
        for obj in involved_objects:
            for s in REP_COLOR_SETTINGS + OBJ_COLOR_SETTINGS + TRANSPARENCY_SETTINGS:
                try:
                    vo = _setting_value(s, obj)
                    vg = saved_global.get(s, _setting_value(s))
                    if vo != vg:
                        obj_overrides.append((s, obj, vo))
                    if s in TRANSPARENCY_SETTINGS:
                        cmd.set(s, 0, obj, quiet=1)
                except Exception:
                    pass
        rep_overrides_present = {}
        for s in REP_COLOR_SETTINGS:
            try:
                rep_overrides_present[s] = (any(_setting_value(s, o) not in (None, -1, (-1,)) for o in involved_objects)
                                            or _setting_value(s) not in (None, -1, (-1,)))
            except Exception:
                rep_overrides_present[s] = False
        for i, it in enumerate(items):
            r, g, b = it["rgb"]
            cname = "_molmcp_id%d" % i
            cmd.set_color(cname, [r / 255.0, g / 255.0, b / 255.0], quiet=1)
            try:
                if i in nonmol:
                    # mesh / surface / map / cgo objects are coloured as a whole, by name
                    cmd.color(cname, nonmol[i], quiet=1)
                    for s in ("mesh_color", "surface_color", "dot_color"):
                        try:
                            cmd.set(s, cname, nonmol[i], quiet=1)
                        except Exception:
                            pass
                    continue
                sel = "(%s)" % it["selection"]
                cmd.color(cname, sel, quiet=1)
                # only override rep colours that are actually set somewhere (atom-level writes are O(N) each)
                for s in REP_COLOR_SETTINGS:
                    if rep_overrides_present.get(s):
                        try:
                            cmd.set(s, cname, sel, quiet=1)
                        except Exception:
                            pass
                for obj in (cmd.get_object_list(sel) or []):
                    for s in OBJ_COLOR_SETTINGS:
                        try:
                            cmd.set(s, cname, obj, quiet=1)
                        except Exception:
                            pass
            except Exception as e:
                errors[it.get("label", str(i))] = str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__
        composite = _png(width, height, ray, -1, False)
        solos = {}
        if solo:
            for i, it in enumerate(items):
                if it.get("label", str(i)) in errors:
                    continue
                sel = "(%s)" % it["selection"]
                cmd.scene("_molmcp_solo", "store", view=0, active=1, color=0, rep=1, frame=0, quiet=1)
                try:
                    if i in nonmol:
                        objs_keep = {nonmol[i]}
                        for o in cmd.get_names("objects", enabled_only=1):
                            if o not in objs_keep:
                                cmd.disable(o)
                    else:
                        cmd.hide("everything", "not %s" % sel)
                        objs_keep = set(cmd.get_object_list(sel) or [])
                        for o in cmd.get_names("objects", enabled_only=1):
                            if o not in objs_keep:
                                cmd.disable(o)
                    solos[it["label"]] = _png(width, height, ray, -1, False)
                except Exception as e:
                    errors[it.get("label", str(i))] = "solo pass: " + (str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__)
                finally:
                    cmd.scene("_molmcp_solo", "recall", animate=0, quiet=1)
                    cmd.scene("_molmcp_solo", "clear", quiet=1)
    finally:
        for i, it in enumerate(items):
            if i in nonmol:
                name = nonmol[i]
                for s in ("mesh_color", "surface_color", "dot_color"):
                    try:
                        cmd.unset(s, name, quiet=1)
                    except Exception:
                        pass
                ci = nonmol_colors.get(name)
                if ci is not None and int(ci) >= 0:
                    try:
                        restore = None
                        for n_, i_ in cmd.get_color_indices(all=1):
                            if i_ == ci:
                                restore = n_
                                break
                        if restore is None:
                            t = cmd.get_color_tuple(ci)
                            if t:
                                restore = "_molmcp_restore%d" % i
                                cmd.set_color(restore, list(t), quiet=1)
                        if restore:
                            cmd.color(restore, name, quiet=1)
                    except Exception:
                        pass
                continue
            sel = "(%s)" % it["selection"]
            for s in REP_COLOR_SETTINGS:
                try:
                    cmd.unset(s, sel, quiet=1)
                except Exception:
                    pass
        for obj in involved_objects:
            for s in TRANSPARENCY_SETTINGS + OBJ_COLOR_SETTINGS:
                try:
                    cmd.unset(s, obj, quiet=1)
                except Exception:
                    pass
        for s, obj, v in obj_overrides:
            try:
                cmd.set(s, v, obj, quiet=1)
            except Exception:
                pass
        for s, v in saved_global.items():
            try:
                if s == "bg_rgb" or s.endswith("color"):
                    cname, rgb = _decode_color_value(v)
                    if rgb is not None and cname == "rgb":
                        cmd.set(s, [c / 255.0 for c in rgb], quiet=1)
                    elif rgb is not None:
                        cmd.set(s, cname, quiet=1)
                    else:
                        cmd.set(s, v, quiet=1)
                else:
                    cmd.set(s, v, quiet=1)
            except Exception:
                pass
        cmd.scene("_molmcp_idpass", "recall", animate=0, quiet=1)
        cmd.scene("_molmcp_idpass", "clear", quiet=1)
    out = {"png": composite, "solo": solos, "legend": {"#%02x%02x%02x" % tuple(it["rgb"]): it["label"] for it in items},
           "errors": errors, "width": width, "height": height, "watermark": _unlicensed(),
           "ms": round((time.time() - t_start) * 1000, 1)}
    if _LAST_PNG_FALLBACK:
        out["fallback"] = _LAST_PNG_FALLBACK
    return out


def op_events(args):
    since = int(args.get("since", 0))
    global _last_fp
    fp = fingerprint()
    changes = diff_fingerprints(_last_fp, fp)
    _last_fp = fp
    if _bridge and changes:
        _bridge.events.add("state_change", changes=changes)
    limit = int(args.get("limit", 300))
    evs, truncated = _bridge.events.since(since, limit=limit) if _bridge else ([], False)
    out = {"seq": _bridge.events.seq if _bridge else 0, "events": evs, "changes_now": changes}
    if truncated:
        out["truncated"] = True
        out["next_since"] = evs[-1]["seq"] if evs else since
    return out


def op_log(args):
    n = int(args.get("n", 100))
    lines = list(_feedback)[-n:]
    return {"lines": [{"t": t, "text": s} for t, s in lines], "total": len(_feedback)}


def op_help(args):
    cmd = _cmd()
    name = args.get("command", "")
    kw = cmd.keyword.get(name)
    if not kw:
        import difflib
        close = difflib.get_close_matches(name, [k for k in cmd.keyword.keys() if not k.startswith("_")], n=8)
        return {"found": False, "suggestions": close}
    fn = kw[0]
    return {"found": True, "command": name, "doc": (fn.__doc__ or "").strip()}


def op_commands(args):
    cmd = _cmd()
    prefix = args.get("prefix", "")
    names = sorted(k for k in cmd.keyword.keys() if k.lower().startswith(prefix.lower()) and not k.startswith("_"))
    return {"commands": names, "count": len(names)}


def op_settings(args):
    names = args.get("names") or INTERESTING_SETTINGS
    obj = args.get("object")
    return {n: _setting_display(n, obj) for n in names}


def op_quit(args):
    """Ask PyMOL to exit (after this response has been sent)."""
    global _shutdown
    _shutdown = True
    cmd = _cmd()

    def later():
        time.sleep(0.3)
        try:
            if _bridge:
                _bridge.stop()
        finally:
            if is_gui():
                try:
                    on_main(lambda: cmd.quit())
                except Exception:
                    os._exit(0)
                time.sleep(8)
                os._exit(0)   # still alive: force it
    threading.Thread(target=later, daemon=True).start()
    return {"quitting": True, "pid": os.getpid()}


def shutdown_requested():
    return _shutdown


def op_agent_ask(args):
    """Ask Claude Code / Codex from inside PyMOL (same path as the `claude` / `codex` commands)."""
    from . import chatpanel
    backend = args.get("backend", "claude")
    prompt = args.get("prompt", "")
    wait = bool(args.get("wait", True))
    timeout = float(args.get("timeout", 600))
    res = on_main(lambda: chatpanel.ask(backend, prompt, wait=False)) if is_gui() else chatpanel.ask(backend, prompt, wait=False)
    if res is None:
        raise RuntimeError("could not start %s (CLI not found, or a run is still in progress)" % backend)
    if not wait:
        return {"started": True, "backend": backend}
    res.wait(timeout)
    return {"final_text": res.final_text, "session_id": res.session_id, "returncode": res.returncode, "backend": backend}


OPS = {
    "ping": op_ping,
    "quit": op_quit,
    "agent_ask": op_agent_ask,
    "run": op_run,
    "python": op_python,
    "scene": op_scene,
    "object_info": op_object_info,
    "selection_info": op_selection_info,
    "get_view": op_get_view,
    "set_view": op_set_view,
    "render": op_render,
    "render_ids": op_render_ids,
    "events": op_events,
    "log": op_log,
    "help": op_help,
    "commands": op_commands,
    "settings": op_settings,
}


def dispatch(op, args):
    fn = OPS.get(op)
    if fn is None:
        raise KeyError("unknown op %r; known: %s" % (op, ", ".join(sorted(OPS))))
    if op in ("ping", "log", "quit", "agent_ask"):
        return fn(args)
    with _lock:
        if not is_gui():
            _undo_guard(None)
        return on_main(lambda: fn(args))


# ---------------------------------------------------------------------------
# lifecycle / PyMOL integration
# ---------------------------------------------------------------------------

def _info():
    cmd = _cmd()
    try:
        v = cmd.get_version()[0]
    except Exception:
        v = "?"
    return {"app_version": v, "gui": is_gui()}


def start(port=None, quiet=0):
    """Start the bridge (idempotent). Returns connection info dict."""
    global _bridge
    if _bridge is not None and _bridge.running:      # fast path without locks (called on the GUI thread)
        _bridge.ensure_discoverable()
        if not int(quiet):
            _log(" Agent bridge already running on port %d" % _bridge.port)
        return _bridge.connection_info()
    with _lifecycle_lock:
        if _bridge is not None and _bridge.running:
            if not int(quiet):
                _log(" Agent bridge already running on port %d" % _bridge.port)
            return _bridge.connection_info()
        bridgecore.cleanup_stale_instance_files()
        _install_feedback_tee()
        cmd = _cmd()
        try:
            version = cmd.get_version()[0]
        except Exception:
            version = "?"
        _bridge = Bridge("pymol", version, dispatch, info=_info, port=int(port) if port else None, log=_log)
        _bridge.start()
        try:
            on_main(_start_focus_poll)
        except Exception:
            pass
        global _last_fp
        try:
            _last_fp = on_main(fingerprint)
        except Exception:
            _last_fp = None
        return _bridge.connection_info()


def stop():
    global _bridge
    with _lifecycle_lock:
        if _bridge is not None:
            _bridge.stop()
            _bridge = None
            _log(" Agent bridge stopped")


def status():
    if _bridge is None or not _bridge.running:
        _log(" Agent bridge: not running (use agent_start)")
        return None
    _bridge.ensure_discoverable()
    info = _bridge.connection_info()
    _log(" Agent bridge: running on http://%s:%d  pid %d  events %d  (connection file: %s)" % (
        info["host"], info["port"], info["pid"], _bridge.events.seq, _bridge.instance_file))
    return info


def connection_info():
    return _bridge.connection_info() if _bridge else None


def _register_commands():
    cmd = _cmd()
    cmd.extend("agent_start", lambda port=None, quiet=0: start(port, quiet))
    cmd.extend("agent_stop", stop)
    cmd.extend("agent_status", status)
    cmd.extend("agent_info", status)
    cmd.extend("agent_name", set_name)
    try:
        from . import chatpanel
        chatpanel.register_commands(cmd)
    except Exception as e:
        _log(" Agent chat commands unavailable: %s" % e)


def _register_menu():
    try:
        from pymol.plugins import addmenuitemqt
    except Exception:
        return
    try:
        addmenuitemqt("Agent Chat (Claude / Codex)", _show_chat)
        addmenuitemqt("Agent Bridge (MCP): Start", lambda: start())
        addmenuitemqt("Agent Bridge (MCP): Status", status)
        addmenuitemqt("Agent Bridge (MCP): Stop", stop)
    except Exception:
        pass


def _show_chat():
    from . import chatpanel
    return chatpanel.show_panel()


def _install_toolbar_button():
    try:
        from . import chatpanel
        if chatpanel.add_toolbar_button() is None:
            # the Qt window may not exist yet while plugins initialise; retry shortly on the GUI thread
            try:
                from pymol.Qt import QtCore
                QtCore.QTimer.singleShot(1500, lambda: chatpanel.add_toolbar_button())
            except Exception:
                pass
    except Exception as e:
        _log(" Agent toolbar button unavailable: %s" % e)


def __init_plugin__(app=None):
    _register_commands()
    _register_menu()
    _install_toolbar_button()
    if os.environ.get("MOLMCP_PYMOL_AUTOSTART", "1") != "0":
        try:
            start(quiet=1)
        except Exception as e:
            _log(" Agent bridge failed to start: %s" % e)


class _StdoutRecorder:
    """Headless PyMOL prints feedback straight to stdout; keep a copy for the `log` op."""

    def __init__(self, stream):
        self._stream = stream
        self._buf = ""

    def write(self, s):
        try:
            self._stream.write(s)
        except Exception:
            pass
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.strip():
                _feedback.append((time.time(), _strip_ansi(line)))

    def flush(self):
        try:
            self._stream.flush()
        except Exception:
            pass

    def __getattr__(self, name):
        return getattr(self._stream, name)


def launch(port=None):
    """Entry point used by the launcher script (works headless and in the GUI)."""
    _register_commands()
    if not is_gui():
        if not isinstance(sys.stdout, _StdoutRecorder):
            sys.stdout = _StdoutRecorder(sys.stdout)
        try:
            cmd = _cmd()
            if str(_setting_value("fetch_path") or ".") in (".", ""):
                fetch_dir = os.path.join(bridgecore.molmcp_home(), "fetch")
                os.makedirs(fetch_dir, exist_ok=True)
                cmd.set("fetch_path", fetch_dir, quiet=1)
        except Exception:
            pass
    return start(port)

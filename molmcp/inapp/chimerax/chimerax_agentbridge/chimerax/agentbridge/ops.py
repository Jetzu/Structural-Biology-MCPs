"""Operations executed inside ChimeraX for the molmcp bridge."""
from __future__ import annotations

import io
import os
import queue
import sys
import threading
import time
import traceback
from collections import Counter, deque

from . import bridgecore
from .bridgecore import Bridge, Tee

_bridge = None
_session = None
_lock = threading.RLock()            # serialises dispatched operations (held while waiting for the main thread)
_lifecycle_lock = threading.RLock()  # start/stop only; never taken while waiting for the main thread
_history = deque(maxlen=5000)   # (t, level, text)
_handlers = []
_history_log = None
_last_fp = None
_shutdown = False

LEVEL_NAMES = {0: "info", 1: "warning", 2: "error", 3: "bug"}
EVENT_TRIGGERS = ["command started", "command finished", "command failed", "add models", "remove models",
                  "selection changed"]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _log(msg):
    _history.append((time.time(), "info", msg))
    try:
        if _session is not None:
            _session.logger.info(msg)
        else:
            print(msg)
    except Exception:
        print(msg)


def _version():
    try:
        from chimerax.core import buildinfo
        return buildinfo.version
    except Exception:
        return "?"


def is_gui(session):
    return bool(getattr(session.ui, "is_gui", False))


def on_main(session, fn):
    """Run fn on the ChimeraX main (GUI) thread and wait for the result."""
    if threading.current_thread() is threading.main_thread():
        return fn()
    q = queue.Queue()

    def wrapper():
        try:
            q.put((True, fn()))
        except BaseException as e:  # noqa
            q.put((False, e))

    try:
        session.ui.thread_safe(wrapper)
    except Exception as e:
        raise RuntimeError("could not schedule work on the ChimeraX main thread: %s" % e)
    ok, val = q.get()
    if ok:
        return val
    raise val


_MD_LINK = None


def clean_log_text(s):
    """ChimeraX hands plain-text logs a markdown-ish rendering of its HTML; tidy it."""
    import re
    global _MD_LINK
    if _MD_LINK is None:
        _MD_LINK = re.compile(r"\[+([^\]]*)\]+\((?:help|cxcmd|http|https|file)[^)]*\)")
    s = _MD_LINK.sub(r"\1", s)
    s = s.replace("**", "")
    s = re.sub(r"(?m)^_([^_\n]+)_", r"\1", s)
    s = re.sub(r"(?m)^---\s*$\n?", "", s)
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _strip_html(s):
    import re
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    import html
    return html.unescape(s)


class _CaptureLog:
    """Temporary log that records plain text messages but lets other logs see them."""
    excludes_other_logs = False

    def __init__(self):
        self.msgs = []

    def log(self, level, msg):
        self.msgs.append((level, msg))
        return False

    def status(self, msg, color, secondary):
        return False


def _make_capture_log():
    from chimerax.core.logger import PlainTextLog

    class CaptureLog(PlainTextLog):
        excludes_other_logs = False

        def __init__(self):
            super().__init__()
            self.msgs = []

        def log(self, level, msg):
            self.msgs.append((level, msg))
            return False

        def status(self, msg, color, secondary):
            return False

    return CaptureLog()


def _make_history_log():
    from chimerax.core.logger import PlainTextLog

    class HistoryLog(PlainTextLog):
        excludes_other_logs = False

        def log(self, level, msg):
            text = clean_log_text(msg)
            if not text:
                return False
            _history.append((time.time(), LEVEL_NAMES.get(level, str(level)), text))
            if _bridge is not None and level >= 1:
                _bridge.events.add("log_" + LEVEL_NAMES.get(level, "msg"), text=text[:2000])
            return False

        def status(self, msg, color, secondary):
            return False

    return HistoryLog()


def _rgba255(c):
    try:
        return [int(round(float(x) * 255)) for x in c[:4]] if max(c[:3]) <= 1.0 and not isinstance(c[0], (int,)) else [int(x) for x in c[:4]]
    except Exception:
        return None


def _jsonable_value(v, depth=0):
    """Convert command return values into something small and JSON friendly."""
    from chimerax.core.models import Model
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, Model):
        return "#%s %s" % (v.id_string, v.name)
    if isinstance(v, (list, tuple)) and depth < 3:
        if len(v) > 50:
            return [_jsonable_value(x, depth + 1) for x in v[:50]] + ["... (%d more)" % (len(v) - 50)]
        return [_jsonable_value(x, depth + 1) for x in v]
    if isinstance(v, dict) and depth < 3:
        return {str(k): _jsonable_value(x, depth + 1) for k, x in list(v.items())[:50]}
    s = str(v)
    return s if len(s) < 500 else s[:500] + "..."


# ---------------------------------------------------------------------------
# fingerprint / diff
# ---------------------------------------------------------------------------

def fingerprint(session):
    v = session.main_view
    models = {}
    for m in session.models.list():
        try:
            d = {"name": m.name, "display": bool(m.display), "type": type(m).__name__}
            if hasattr(m, "num_atoms"):
                d["atoms"] = int(m.num_atoms)
                try:
                    d["shown_atoms"] = int(m.atoms.displays.sum())
                    d["shown_ribbons"] = int(m.residues.ribbon_displays.sum())
                    d["selected"] = int(m.atoms.selecteds.sum())
                    d["colour_hash"] = int(m.atoms.colors.sum()) * 7 + int(m.residues.ribbon_colors.sum())
                except Exception:
                    pass
            elif hasattr(m, "color") and m.color is not None:
                try:
                    d["colour_hash"] = int(sum(int(x) for x in m.color))
                except Exception:
                    pass
            models[m.id_string] = d
        except Exception:
            pass
    cam = v.camera
    try:
        pos = [round(float(x), 3) for x in cam.position.matrix.flatten()]
    except Exception:
        pos = []
    fov = getattr(cam, "field_of_view", None)
    fw = getattr(cam, "field_width", None)
    return {"models": models, "camera": pos, "fov": fov, "field_width": fw, "camera_name": getattr(cam, "name", ""),
            "window": list(v.window_size), "bg": [round(float(x), 3) for x in v.background_color]}


def diff_fingerprints(a, b):
    if a is None:
        return []
    ch = []
    added = [k for k in b["models"] if k not in a["models"]]
    removed = [k for k in a["models"] if k not in b["models"]]
    if added:
        ch.append({"change": "models_added", "ids": ["#%s %s" % (k, b["models"][k]["name"]) for k in added]})
    if removed:
        ch.append({"change": "models_removed", "ids": ["#%s %s" % (k, a["models"][k]["name"]) for k in removed]})
    for k, d in b["models"].items():
        if k not in a["models"]:
            continue
        o = a["models"][k]
        if o["display"] != d["display"]:
            ch.append({"change": "model_display", "id": "#" + k, "display": d["display"]})
        for f in ("atoms", "shown_atoms", "shown_ribbons", "selected"):
            if f in d and f in o and o[f] != d[f]:
                ch.append({"change": f, "id": "#" + k, "from": o[f], "to": d[f]})
        if "colour_hash" in d and "colour_hash" in o and o["colour_hash"] != d["colour_hash"]:
            ch.append({"change": "colours", "id": "#" + k, "detail": "atom/ribbon/model colours changed"})
    if a["camera"] != b["camera"] or a["fov"] != b["fov"] or a["field_width"] != b["field_width"]:
        ch.append({"change": "camera", "detail": "camera moved/zoomed"})
    if a["camera_name"] != b["camera_name"]:
        ch.append({"change": "camera_mode", "to": b["camera_name"]})
    if a["window"] != b["window"]:
        ch.append({"change": "window_size", "to": b["window"]})
    if a["bg"] != b["bg"]:
        ch.append({"change": "background", "to": b["bg"]})
    return ch


# ---------------------------------------------------------------------------
# ops
# ---------------------------------------------------------------------------

def op_ping(session, args):
    # runs on the bridge thread so that liveness checks never wait for a busy main thread
    out = {"app": "chimerax", "version": _version(), "pid": os.getpid(), "gui": is_gui(session),
           "events_seq": _bridge.events.seq if _bridge else 0, "cwd": os.getcwd(),
           "main_thread_busy": not _lock.acquire(blocking=False)}
    if not out["main_thread_busy"]:
        _lock.release()
    try:
        out["window"] = list(session.main_view.window_size)
        out["n_models"] = len(session.models.list())
    except Exception:
        pass
    return out


def _run_one(session, text, log):
    from chimerax.core.commands import run
    from chimerax.core.errors import UserError, NotABug
    cap = _make_capture_log()
    session.logger.add_log(cap)
    t0 = time.time()
    ok, err, tb, value = True, None, None, None
    try:
        value = run(session, text, log=log)
    except NotABug as e:          # UserError etc: user-facing message, no traceback
        ok, err = False, "%s: %s" % (type(e).__name__, e)
    except Exception as e:
        ok, err, tb = False, "%s: %s" % (type(e).__name__, e), traceback.format_exc()
    finally:
        session.logger.remove_log(cap)
    msgs = []
    for level, msg in cap.msgs:
        t = clean_log_text(msg)
        if not t or t == text:
            continue
        # drop the command echo lines ChimeraX logs itself
        lines = [ln for ln in t.splitlines() if ln.strip() and ln.strip() != text]
        if not lines:
            continue
        t = "\n".join(lines)
        msgs.append(t if level == 0 else "%s: %s" % (LEVEL_NAMES.get(level, level).upper(), t))
    return {"command": text, "ok": ok, "output": "\n".join(msgs), "error": err, "traceback": tb,
            "value": _jsonable_value(value), "ms": round((time.time() - t0) * 1000, 1)}


def op_run(session, args):
    cmds = args.get("commands")
    if isinstance(cmds, str):
        cmds = cmds.splitlines()
    cmds = [c.strip() for c in (cmds or []) if c and c.strip()]
    log = bool(args.get("log", True))
    stop_on_error = bool(args.get("stop_on_error", True))
    global _last_fp
    before = fingerprint(session)
    results = []
    for c in cmds:
        r = _run_one(session, c, log)
        results.append(r)
        if _bridge:
            _bridge.events.add("agent_command", command=c, ok=r["ok"])
        if not r["ok"] and stop_on_error:
            break
    after = fingerprint(session)
    _last_fp = after
    return {"results": results, "all_ok": all(r["ok"] for r in results), "changes": diff_fingerprints(before, after),
            "executed": len(results), "requested": len(cmds)}


def op_python(session, args):
    code = args.get("code", "")
    from chimerax.core.commands import run as _run
    ns = {"session": session, "run": lambda text, log=True: _run(session, text, log=log), "__name__": "__molmcp__"}
    cap = _make_capture_log()
    session.logger.add_log(cap)
    out_tee, err_tee = Tee(sys.stdout), Tee(sys.stderr)
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = out_tee, err_tee
    before = fingerprint(session)
    error = tb = None
    t0 = time.time()
    try:
        exec(compile(code, "<molmcp>", "exec"), ns, ns)
    except Exception as e:
        error = "%s: %s" % (type(e).__name__, e)
        tb = traceback.format_exc()
    finally:
        sys.stdout, sys.stderr = old_out, old_err
        session.logger.remove_log(cap)
    after = fingerprint(session)
    global _last_fp
    _last_fp = after
    if _bridge:
        _bridge.events.add("agent_python", ok=error is None, chars=len(code))
    logtext = "\n".join(clean_log_text(m) for _, m in cap.msgs)
    return {"ok": error is None, "stdout": out_tee.getvalue() + err_tee.getvalue() + logtext,
            "result": bridgecore.json_safe(ns.get("result")), "error": error, "traceback": tb,
            "changes": diff_fingerprints(before, after), "ms": round((time.time() - t0) * 1000, 1)}


def _color_summary(colors, k=3):
    """colors: (N,4) uint8 array -> top-k colours with shares."""
    try:
        import numpy as np
        if len(colors) == 0:
            return []
        keys = (colors[:, 0].astype(np.int64) << 16) | (colors[:, 1].astype(np.int64) << 8) | colors[:, 2].astype(np.int64)
        vals, counts = np.unique(keys, return_counts=True)
        order = counts.argsort()[::-1][:k]
        total = float(len(colors))
        out = []
        for i in order:
            key = int(vals[i])
            out.append({"rgb": [(key >> 16) & 255, (key >> 8) & 255, key & 255], "share": round(float(counts[i] / total), 3)})
        return out
    except Exception:
        return []


def _model_info(session, m, detail):
    info = {"id": "#" + m.id_string, "name": m.name, "type": type(m).__name__, "display": bool(m.display),
            "visible": bool(getattr(m, "visible", m.display)), "parent": ("#" + m.parent.id_string) if (m.parent is not None and m.parent.id) else None,
            "children": len(m.child_models())}
    try:
        info["selected"] = bool(m.selected)
    except Exception:
        pass
    try:
        b = m.bounds()
        if b is not None:
            info["bounds"] = {"min": [round(float(x), 2) for x in b.xyz_min], "max": [round(float(x), 2) for x in b.xyz_max],
                              "center": [round(float(x), 2) for x in b.center()], "size": [round(float(x), 2) for x in (b.xyz_max - b.xyz_min)]}
    except Exception:
        pass
    try:
        if not m.position.is_identity():
            info["positioned"] = True
    except Exception:
        pass
    if hasattr(m, "num_atoms") and hasattr(m, "atoms"):
        try:
            import numpy as np
            atoms, residues = m.atoms, m.residues
            info["atoms"] = int(m.num_atoms)
            info["residues"] = int(m.num_residues)
            info["num_chains"] = int(m.num_chains)
            info["coordsets"] = int(m.num_coordsets)
            if m.num_coordsets > 1:
                info["active_coordset"] = int(m.active_coordset_id)
            disp = atoms.displays
            info["shown_atoms"] = int(disp.sum())
            info["shown_ribbon_residues"] = int(residues.ribbon_displays.sum())
            dm = atoms.draw_modes[disp] if disp.any() else atoms.draw_modes[:0]
            info["atom_styles_shown"] = {name: int((dm == code).sum()) for code, name in ((0, "sphere"), (1, "ball"), (2, "stick")) if (dm == code).any()}
            info["selected_atoms"] = int(atoms.selecteds.sum())
            cats = atoms.structure_categories
            info["categories"] = {c: int((cats == c).sum()) for c in ("main", "ligand", "ions", "solvent") if (cats == c).any()}
            lig = residues[np.array([bool(x) for x in (residues.polymer_types == 0)])] if len(residues) else residues
            if len(lig):
                names = Counter(lig.names)
                info["non_polymer_residues"] = dict(names.most_common(12))
            surfs = [s for s in m.child_models() if type(s).__name__ == "MolecularSurface"]
            if surfs:
                info["surfaces"] = [{"id": "#" + s.id_string, "name": s.name, "display": bool(s.display)} for s in surfs[:20]]
            pbgs = [p for p in m.child_models() if type(p).__name__ == "PseudobondGroup"]
            if pbgs:
                info["pseudobond_groups"] = [{"id": "#" + p.id_string, "name": p.name, "count": int(p.num_pseudobonds), "display": bool(p.display)} for p in pbgs[:20]]
            if detail == "full" and m.num_atoms <= 400000:
                chains = []
                for c in m.chains:
                    try:
                        cres = c.existing_residues
                        catoms = cres.atoms
                        ptype = {1: "protein", 2: "nucleic"}.get(int(c.polymer_type), "other")
                        nums = cres.numbers
                        ss = cres.ss_types
                        d = {"chain": c.chain_id, "polymer": ptype, "residues": len(cres),
                             "residue_range": [int(nums.min()), int(nums.max())] if len(nums) else None,
                             "description": (c.description or "")[:80] if getattr(c, "description", None) else None,
                             "shown_atoms": int(catoms.displays.sum()), "shown_ribbon_residues": int(cres.ribbon_displays.sum()),
                             "ss_fraction": {"helix": round(float((ss == 1).mean()), 2), "strand": round(float((ss == 2).mean()), 2)} if len(ss) else None,
                             "atom_colors": _color_summary(catoms.colors), "ribbon_colors": _color_summary(cres.ribbon_colors)}
                        chains.append(d)
                    except Exception as e:
                        chains.append({"chain": getattr(c, "chain_id", "?"), "error": str(e)})
                info["chains"] = chains
                nonpoly = residues[residues.polymer_types == 0]
                if len(nonpoly):
                    info["ligand_like"] = sorted(set("%s:%s%d" % (r.chain_id, r.name, r.number) for r in nonpoly if r.name not in ("HOH", "WAT")))[:30]
        except Exception as e:
            info["error"] = "%s: %s" % (type(e).__name__, e)
    elif type(m).__name__ == "Volume":
        try:
            d = m.data
            info["grid_size"] = [int(x) for x in d.size]
            info["voxel_size"] = [round(float(x), 3) for x in d.step]
            info["origin"] = [round(float(x), 2) for x in d.origin]
            surfs = []
            for s in getattr(m, "surfaces", []):
                surfs.append({"level": round(float(s.level), 4), "rgba": _rgba255(s.rgba) if hasattr(s, "rgba") else None,
                              "mesh": bool(getattr(s, "show_mesh", False)), "display": bool(s.display)})
            info["isosurfaces"] = surfs
            info["image_shown"] = bool(getattr(m, "image_shown", False))
            try:
                info["value_range"] = [round(float(x), 4) for x in m.data.value_range()] if hasattr(m.data, "value_range") else None
            except Exception:
                pass
            try:
                st = m.matrix_value_statistics()
                info["stats"] = {"min": round(float(st.minimum), 4), "max": round(float(st.maximum), 4), "mean": round(float(st.mean), 4), "sd": round(float(st.standard_deviation), 4)}
            except Exception:
                pass
        except Exception as e:
            info["error"] = str(e)
    elif hasattr(m, "triangles") and getattr(m, "triangles", None) is not None:
        try:
            info["triangles"] = int(len(m.triangles))
            info["color"] = [int(x) for x in m.color] if m.color is not None else None
            info["vertex_colored"] = m.vertex_colors is not None
        except Exception:
            pass
    if type(m).__name__ == "PseudobondGroup" and "count" not in info:
        try:
            info["pseudobonds"] = int(m.num_pseudobonds)
        except Exception:
            pass
    return info


def _camera_info(session):
    v = session.main_view
    c = v.camera
    out = {"mode": getattr(c, "name", "?")}
    try:
        p = c.position
        out["position"] = [round(float(x), 3) for x in p.origin()]
        out["view_direction"] = [round(float(x), 4) for x in c.view_direction()]
        axes = p.axes()
        out["up"] = [round(float(x), 4) for x in axes[1]]
        out["matrix_3x4"] = [[round(float(x), 4) for x in row] for row in p.matrix]
    except Exception:
        pass
    for attr in ("field_of_view", "field_width", "eye_separation_scene"):
        if hasattr(c, attr):
            try:
                out[attr] = round(float(getattr(c, attr)), 3)
            except Exception:
                pass
    try:
        cor = v.center_of_rotation
        out["center_of_rotation"] = [round(float(x), 3) for x in cor]
        out["center_of_rotation_method"] = v.center_of_rotation_method
    except Exception:
        pass
    try:
        planes = []
        for pl in v.clip_planes.planes():
            planes.append({"name": pl.name, "normal": [round(float(x), 3) for x in pl.normal],
                           "point": [round(float(x), 3) for x in pl.plane_point]})
        out["clip_planes"] = planes
    except Exception:
        pass
    try:
        b = v.drawing_bounds()
        if b is not None:
            out["scene_bounds"] = {"center": [round(float(x), 2) for x in b.center()], "radius": round(float(b.radius()), 2)}
    except Exception:
        pass
    return out


def _lighting_info(session):
    v = session.main_view
    l = v.lighting
    keys = ["key_light_intensity", "fill_light_intensity", "ambient_light_intensity", "depth_cue", "shadows", "multishadow",
            "key_light_direction", "depth_cue_start", "depth_cue_end"]
    out = {}
    for k in keys:
        try:
            val = getattr(l, k)
            out[k] = [round(float(x), 3) for x in val] if hasattr(val, "__len__") else (round(float(val), 3) if isinstance(val, float) else val)
        except Exception:
            pass
    try:
        out["silhouettes"] = bool(v.silhouette.enabled)
    except Exception:
        pass
    try:
        m = v.material
        out["material"] = {"ambient": round(float(m.ambient_reflectivity), 2), "diffuse": round(float(m.diffuse_reflectivity), 2),
                           "specular": round(float(m.specular_reflectivity), 2), "exponent": round(float(m.specular_exponent), 1)}
    except Exception:
        pass
    return out


def op_scene(session, args):
    detail = args.get("detail", "summary")
    only = args.get("models")
    v = session.main_view
    models = []
    for m in session.models.list():
        if only and ("#" + m.id_string) not in only and m.id_string not in only:
            continue
        models.append(_model_info(session, m, detail))
    models.sort(key=lambda d: [int(x) for x in d["id"][1:].split(".")])
    sel = {}
    try:
        from chimerax.atomic import selected_atoms, selected_residues
        sa = selected_atoms(session)
        sel = {"atoms": len(sa), "residues": len(selected_residues(session)),
               "structures": sorted(set("#" + s.id_string for s in sa.unique_structures))}
        if 0 < len(sa) <= 100000:
            sel["chains"] = sorted(set("%s/%s" % ("#" + a.structure.id_string, a.residue.chain_id) for a in sa))[:40]
    except Exception:
        pass
    try:
        sel["models_selected"] = ["#" + m.id_string for m in session.models.list() if getattr(m, "selected", False)][:40]
    except Exception:
        pass
    bg = v.background_color
    res = {
        "app": "chimerax", "version": _version(), "gui": is_gui(session),
        "window": list(v.window_size),
        "models": models,
        "selection": sel,
        "camera": _camera_info(session),
        "lighting": _lighting_info(session),
        "background": {"rgb": [int(round(float(x) * 255)) for x in bg[:3]]},
        "events_seq": _bridge.events.seq if _bridge else 0,
    }
    global _last_fp
    _last_fp = fingerprint(session)
    return res


def _find_model(session, spec):
    spec = str(spec).strip()
    if spec.startswith("#"):
        spec = spec[1:]
    for m in session.models.list():
        if m.id_string == spec:
            return m
    raise ValueError("no model with id #%s" % spec)


def op_model_info(session, args):
    m = _find_model(session, args.get("model") or args.get("id"))
    return _model_info(session, m, "full")


def _evaluate_spec(session, spec):
    from chimerax.core.commands import atomspec
    parsed, text, rest = atomspec.AtomSpecArg.parse(spec, session)
    if rest.strip():
        raise ValueError("could not parse atom spec %r (unparsed: %r)" % (spec, rest))
    return parsed.evaluate(session)


def _compact_ranges(values):
    vals = sorted(set(int(v) for v in values))
    out, start, prev = [], None, None
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


def op_selection_info(session, args):
    spec = args.get("spec") or args.get("selection") or "sel"
    objs = _evaluate_spec(session, spec)
    atoms = objs.atoms
    out = {"spec": spec, "atoms": len(atoms), "residues": len(objs.residues), "bonds": objs.num_bonds,
           "models": ["#%s %s" % (m.id_string, m.name) for m in objs.models][:40]}
    if len(atoms) and len(atoms) <= int(args.get("max_atoms", 200000)):
        by = {}
        for s, satoms in atoms.by_structure:
            chains = []
            res = satoms.unique_residues
            for cid in sorted(set(res.chain_ids)):
                cres = res[res.chain_ids == cid]
                catoms = satoms[satoms.residues.chain_ids == cid]
                chains.append({"chain": cid, "atoms": len(catoms), "residues": len(cres),
                               "residue_ranges": _compact_ranges(cres.numbers)[:40],
                               "residue_names": dict(Counter(cres.names).most_common(10)),
                               "elements": dict(Counter(catoms.element_names).most_common(8)),
                               "shown_atoms": int(catoms.displays.sum()), "selected_atoms": int(catoms.selecteds.sum())})
            by["#" + s.id_string] = chains
        out["by_structure"] = by
        try:
            import numpy as np
            xyz = atoms.scene_coords
            out["center"] = [round(float(x), 2) for x in xyz.mean(axis=0)]
            out["extent"] = [[round(float(x), 2) for x in xyz.min(axis=0)], [round(float(x), 2) for x in xyz.max(axis=0)]]
        except Exception:
            pass
    return out


def op_get_view(session, args):
    return _camera_info(session)


def _render_png(session, width, height, supersample, transparent):
    v = session.main_view
    img = v.image(width=int(width) if width else None, height=int(height) if height else None,
                  supersample=int(supersample) if supersample else None, transparent_background=bool(transparent))
    if img is None:
        raise RuntimeError("ChimeraX returned no image (is the graphics window available? nogui mode cannot render without --offscreen)")
    return bridgecore.png_bytes(img)


def op_render(session, args):
    width = args.get("width")
    height = args.get("height")
    supersample = args.get("supersample", 3)
    transparent = bool(args.get("transparent", False))
    path = args.get("path")
    t0 = time.time()
    data = _render_png(session, width, height, supersample, transparent)
    if path:
        path = os.path.expanduser(path)
        if not path.lower().endswith(".png"):
            path += ".png"
        with open(path, "wb") as f:
            f.write(data)
    bg = session.main_view.background_color
    if _bridge:
        _bridge.events.add("agent_render", width=width, height=height)
    return {"png": data, "path": path, "background": {"rgb": [int(round(float(x) * 255)) for x in bg[:3]]},
            "transparent": transparent, "ms": round((time.time() - t0) * 1000, 1), "window": list(session.main_view.window_size)}


def op_render_ids(session, args):
    """ID pass: every item in its own flat colour; everything restored afterwards."""
    import numpy as np
    items = args.get("items") or []
    width, height = args.get("width"), args.get("height")
    solo = bool(args.get("solo", False))
    if not items:
        raise ValueError("items required: [{label, spec, rgb}]")
    v = session.main_view
    saved = []          # list of restore callables (executed in reverse)

    def save(fn):
        saved.append(fn)

    # --- lighting / material / background / silhouettes
    l = v.lighting
    light_state = {k: getattr(l, k) for k in ("key_light_intensity", "fill_light_intensity", "ambient_light_intensity",
                                              "shadows", "multishadow", "depth_cue")}
    mat = v.material
    mat_state = {k: getattr(mat, k) for k in ("ambient_reflectivity", "diffuse_reflectivity", "specular_reflectivity")}
    bg_state = tuple(v.background_color)
    sil_state = bool(v.silhouette.enabled)

    def restore_graphics():
        for k, val in light_state.items():
            setattr(l, k, val)
        for k, val in mat_state.items():
            setattr(mat, k, val)
        v.background_color = bg_state
        v.silhouette.enabled = sil_state
        v.update_lighting = True
    save(restore_graphics)

    # --- selection highlight off
    try:
        from chimerax.atomic import selected_atoms
        sel_atoms = selected_atoms(session)
        sel_models = [m for m in session.models.list() if getattr(m, "selected", False)]
        if len(sel_atoms) or sel_models:
            session.selection.clear()

            def restore_sel(sel_atoms=sel_atoms, sel_models=sel_models):
                try:
                    sel_atoms.selecteds = True
                except Exception:
                    pass
                for m in sel_models:
                    try:
                        m.selected = True
                    except Exception:
                        pass
            save(restore_sel)
    except Exception:
        pass

    evaluated = []
    involved = set()
    for it in items:
        objs = _evaluate_spec(session, it["spec"])
        evaluated.append(objs)
        for m in objs.models:
            involved.add(m)
            p = m.parent
            while p is not None:
                involved.add(p)
                p = p.parent
        for s in objs.atoms.unique_structures:
            involved.add(s)

    # --- hide models that are not part of any item (labels, other structures, ...)
    for m in session.models.list():
        if m in involved:
            continue
        if m.parent is not None and m.parent not in involved and m.parent.id:
            continue   # parent hidden already covers it
        if m.display:
            m.display = False
            save(lambda m=m: setattr(m, "display", True))
    # hide labels / pseudobond groups inside involved structures (own colours would pollute the ID pass)
    for m in session.models.list():
        if m in involved and type(m).__name__ in ("ObjectLabels", "PseudobondGroup", "Labels") and m.display and not any(
                m is o for objs in evaluated for o in objs.models):
            m.display = False
            save(lambda m=m: setattr(m, "display", True))

    # --- colours
    structures = set()
    for objs in evaluated:
        structures.update(objs.atoms.unique_structures)
        for m in objs.models:
            if hasattr(m, "atoms") and hasattr(m, "num_atoms"):
                structures.add(m)
    for s in structures:
        ac = s.atoms.colors.copy()
        rc = s.residues.ribbon_colors.copy()
        save(lambda s=s, ac=ac, rc=rc: (setattr(s.atoms, "colors", ac), setattr(s.residues, "ribbon_colors", rc)))
    surf_like = []
    for objs in evaluated:
        for m in objs.models:
            if hasattr(m, "vertex_colors") and hasattr(m, "color") and not hasattr(m, "num_atoms"):
                surf_like.append(m)
        for s in objs.atoms.unique_structures:
            for c in s.child_models():
                if hasattr(c, "vertex_colors") and hasattr(c, "color"):
                    surf_like.append(c)
    for m in set(surf_like):
        vc = m.vertex_colors
        vc = None if vc is None else vc.copy()
        col = tuple(int(x) for x in m.color) if m.color is not None else None
        auto = getattr(m, "auto_recolor_vertices", None)

        def restore_surface(m=m, vc=vc, col=col, auto=auto):
            try:
                if col is not None:
                    m.color = col
                m.vertex_colors = vc
                if auto is not None:
                    m.auto_recolor_vertices = auto
            except Exception:
                pass
        save(restore_surface)

    try:
        l.key_light_intensity = 0.0
        l.fill_light_intensity = 0.0
        l.ambient_light_intensity = 1.0
        l.shadows = False
        l.multishadow = 0
        l.depth_cue = False
        mat.ambient_reflectivity = 1.0
        mat.diffuse_reflectivity = 0.0
        mat.specular_reflectivity = 0.0
        v.update_lighting = True
        v.background_color = (0, 0, 0, 1)
        v.silhouette.enabled = False

        for it, objs in zip(items, evaluated):
            rgba = np.array(list(it["rgb"]) + [255], dtype=np.uint8)
            atoms = objs.atoms
            if len(atoms):
                atoms.colors = rgba
                atoms.residues.ribbon_colors = rgba
            for m in objs.models:
                if hasattr(m, "atoms") and hasattr(m, "num_atoms"):
                    m.atoms.colors = rgba
                    m.residues.ribbon_colors = rgba
                    for c in m.child_models():
                        if hasattr(c, "vertex_colors") and hasattr(c, "color"):
                            _flat_color_surface(c, rgba)
                elif hasattr(m, "vertex_colors") and hasattr(m, "color"):
                    _flat_color_surface(m, rgba)
            # molecular surfaces belonging to a chain-level item
            for s in atoms.unique_structures:
                for c in s.child_models():
                    if type(c).__name__ == "MolecularSurface" and hasattr(c, "atoms"):
                        try:
                            satoms = c.atoms
                            if len(satoms) and len(satoms.intersect(atoms)) * 2 > len(satoms):
                                _flat_color_surface(c, rgba)
                        except Exception:
                            pass
        composite = _render_png(session, width, height, 1, False)
        solos = {}
        if solo:
            for it, objs in zip(items, evaluated):
                hidden = []
                try:
                    keep_models = set(objs.models) | set(objs.atoms.unique_structures)
                    keep_parents = set()
                    for m in keep_models:
                        p = m.parent
                        while p is not None:
                            keep_parents.add(p)
                            p = p.parent
                    for m in session.models.list():
                        if m.display and m not in keep_models and m not in keep_parents and not any(
                                m.parent is k for k in keep_models) and m.id:
                            m.display = False
                            hidden.append(("model", m, None))
                    for s in objs.atoms.unique_structures:
                        mask = np.zeros(s.num_atoms, dtype=bool)
                        mask[s.atoms.indices(objs.atoms)] = True
                        if not mask.all():
                            ad = s.atoms.displays.copy()
                            rd = s.residues.ribbon_displays.copy()
                            hidden.append(("atoms", s, (ad, rd)))
                            nd = ad.copy()
                            nd[~mask] = False
                            s.atoms.displays = nd
                            rmask = np.zeros(s.num_residues, dtype=bool)
                            rmask[s.residues.indices(objs.atoms.unique_residues)] = True
                            nr = rd.copy()
                            nr[~rmask] = False
                            s.residues.ribbon_displays = nr
                            for c in s.child_models():
                                if c.display and type(c).__name__ == "MolecularSurface":
                                    satoms = c.atoms
                                    if not (len(satoms) and len(satoms.intersect(objs.atoms)) * 2 > len(satoms)):
                                        c.display = False
                                        hidden.append(("model", c, None))
                    solos[it["label"]] = _render_png(session, width, height, 1, False)
                finally:
                    for kind, m, data in reversed(hidden):
                        if kind == "model":
                            m.display = True
                        else:
                            m.atoms.displays, m.residues.ribbon_displays = data
    finally:
        for fn in reversed(saved):
            try:
                fn()
            except Exception:
                pass
        v.redraw_needed = True
    return {"png": composite, "solo": solos, "legend": {"#%02x%02x%02x" % tuple(it["rgb"]): it["label"] for it in items}}


def _flat_color_surface(m, rgba):
    try:
        if getattr(m, "auto_recolor_vertices", None) is not None:
            m.auto_recolor_vertices = None
    except Exception:
        pass
    try:
        m.vertex_colors = None
    except Exception:
        pass
    try:
        m.color = tuple(int(x) for x in rgba)
    except Exception:
        pass


def op_events(session, args):
    since = int(args.get("since", 0))
    global _last_fp
    fp = fingerprint(session)
    changes = diff_fingerprints(_last_fp, fp)
    _last_fp = fp
    if _bridge and changes:
        _bridge.events.add("state_change", changes=changes)
    evs = _bridge.events.since(since, limit=int(args.get("limit", 300))) if _bridge else []
    return {"seq": _bridge.events.seq if _bridge else 0, "events": evs, "changes_now": changes}


def op_log(session, args):
    n = int(args.get("n", 100))
    lines = list(_history)[-n:]
    return {"lines": [{"t": t, "level": lv, "text": s} for t, lv, s in lines], "total": len(_history)}


def op_help(session, args):
    try:
        from chimerax.core.commands.cli import usage
    except ImportError:
        from chimerax.core.commands import usage
    name = args.get("command", "")
    try:
        text = usage(session, name, show_subcommands=20)
        return {"found": True, "command": name, "usage": _strip_html(text).replace("\xa0", " ")}
    except Exception as e:
        from chimerax.core.commands import registered_commands
        import difflib
        names = registered_commands(multiword=True)
        return {"found": False, "error": str(e), "suggestions": difflib.get_close_matches(name, names, n=8)}


def op_commands(session, args):
    from chimerax.core.commands import registered_commands
    prefix = args.get("prefix", "")
    names = sorted(n for n in registered_commands(multiword=True) if n.startswith(prefix))
    return {"commands": names, "count": len(names)}


def op_quit(session, args):
    global _shutdown
    _shutdown = True

    def later():
        time.sleep(0.3)
        try:
            if _bridge:
                _bridge.stop()
        finally:
            def do_exit():
                try:
                    from chimerax.core.commands import run
                    run(session, "exit", log=False)
                except Exception:
                    try:
                        session.ui.quit()
                    except Exception:
                        os._exit(0)
            try:
                session.ui.thread_safe(do_exit)
            except Exception:
                os._exit(0)
            time.sleep(8)
            os._exit(0)   # still alive: force it
    threading.Thread(target=later, daemon=True).start()
    return {"quitting": True, "pid": os.getpid()}


def op_agent_ask(session, args):
    """Ask Claude Code / Codex from inside ChimeraX (same path as the `claude` / `codex` commands)."""
    from . import tool
    backend = args.get("backend", "claude")
    prompt = args.get("prompt", "")
    wait = bool(args.get("wait", True))
    timeout = float(args.get("timeout", 600))
    run = on_main(session, lambda: tool.ask(session, backend, prompt, wait=False))
    if run is None:
        raise RuntimeError("could not start %s (CLI not found?)" % backend)
    if not wait:
        return {"started": True, "backend": backend}
    run.wait(timeout)
    return {"final_text": run.final_text, "session_id": run.session_id, "returncode": run.returncode, "backend": backend}


OPS = {
    "ping": op_ping, "run": op_run, "agent_ask": op_agent_ask, "python": op_python, "scene": op_scene, "model_info": op_model_info,
    "object_info": op_model_info, "selection_info": op_selection_info, "get_view": op_get_view,
    "render": op_render, "render_ids": op_render_ids, "events": op_events, "log": op_log, "help": op_help,
    "commands": op_commands, "quit": op_quit,
}


def dispatch(op, args):
    fn = OPS.get(op)
    if fn is None:
        raise KeyError("unknown op %r; known: %s" % (op, ", ".join(sorted(OPS))))
    session = _session
    if op in ("ping", "log", "quit", "agent_ask"):
        return fn(session, args)
    with _lock:
        return on_main(session, lambda: fn(session, args))


# ---------------------------------------------------------------------------
# lifecycle
# ---------------------------------------------------------------------------

def _info():
    return {"app_version": _version(), "gui": is_gui(_session) if _session else False}


def _install_triggers(session):
    def handler(name, data):
        if _bridge is None:
            return
        try:
            if name.startswith("command"):
                _bridge.events.add(name.replace(" ", "_"), command=str(data)[:500])
            elif name in ("add models", "remove models"):
                _bridge.events.add(name.replace(" ", "_"), models=["#%s %s" % (m.id_string, m.name) for m in list(data)[:50]])
            else:
                _bridge.events.add(name.replace(" ", "_"))
        except Exception:
            pass
    for name in EVENT_TRIGGERS:
        try:
            h = session.triggers.add_handler(name, handler)
            _handlers.append((session.triggers, h))
        except Exception:
            pass


def start(session, port=None, quiet=False):
    global _bridge, _session, _history_log, _last_fp
    if _bridge is not None and _bridge.running:      # fast path, no locks (may be called on the main thread)
        if not quiet:
            _log("molmcp agent bridge already running on port %d" % _bridge.port)
        return _bridge.connection_info()
    with _lifecycle_lock:
        _session = session
        if _bridge is not None and _bridge.running:
            if not quiet:
                _log("molmcp agent bridge already running on port %d" % _bridge.port)
            return _bridge.connection_info()
        bridgecore.cleanup_stale_instance_files()
        _bridge = Bridge("chimerax", _version(), dispatch, info=_info, port=int(port) if port else None, log=_log)
        _bridge.start()
        if _history_log is None:
            _history_log = _make_history_log()
            session.logger.add_log(_history_log)
        _install_triggers(session)
        try:
            _last_fp = fingerprint(session)
        except Exception:
            _last_fp = None
        return _bridge.connection_info()


def stop(session=None):
    global _bridge, _history_log
    with _lifecycle_lock:
        for ts, h in _handlers:
            try:
                ts.remove_handler(h)
            except Exception:
                pass
        _handlers.clear()
        if _history_log is not None and _session is not None:
            try:
                _session.logger.remove_log(_history_log)
            except Exception:
                pass
            _history_log = None
        if _bridge is not None:
            _bridge.stop()
            _bridge = None


def status(session):
    if _bridge is None or not _bridge.running:
        _log("molmcp agent bridge: not running (use 'agent start')")
        return None
    info = _bridge.connection_info()
    _log("molmcp agent bridge: running on http://%s:%d  pid %d  events %d  (connection file: %s)" % (
        info["host"], info["port"], info["pid"], _bridge.events.seq, _bridge.instance_file))
    return info


def shutdown_requested():
    return _shutdown

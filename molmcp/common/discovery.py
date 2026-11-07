"""Finding and launching the viewer applications on any platform.

Order of precedence for executables:

1. ``PYMOL_EXE`` / ``CHIMERAX_EXE`` environment variables.
2. Anything on ``PATH`` (``pymol``, ``chimerax``, ``ChimeraX``).
3. Well-known install locations for macOS, Linux and Windows.
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import sys
import time
from typing import Dict, List, Optional


def molmcp_home() -> str:
    return os.environ.get("MOLMCP_HOME") or os.path.join(os.path.expanduser("~"), ".molmcp")


def instances_dir() -> str:
    d = os.path.join(molmcp_home(), "instances")
    os.makedirs(d, exist_ok=True)
    return d


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform.startswith("win"):
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not h:
            return False
        ctypes.windll.kernel32.CloseHandle(h)
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def pid_start_time(pid: int) -> Optional[float]:
    """Process creation time as a Unix timestamp (best effort, None when unknown)."""
    try:
        if sys.platform.startswith("win"):
            import ctypes
            from ctypes import wintypes
            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if not h:
                return None
            try:
                ct, et, kt, ut = (wintypes.FILETIME() for _ in range(4))
                if not ctypes.windll.kernel32.GetProcessTimes(h, ctypes.byref(ct), ctypes.byref(et), ctypes.byref(kt), ctypes.byref(ut)):
                    return None
                ticks = (ct.dwHighDateTime << 32) | ct.dwLowDateTime
                return ticks / 1e7 - 11644473600.0
            finally:
                ctypes.windll.kernel32.CloseHandle(h)
        if sys.platform.startswith("linux"):
            st = os.stat("/proc/%d" % pid)
            return float(st.st_ctime)
        out = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True, text=True, timeout=5).stdout.strip()
        if not out:
            return None
        return time.mktime(time.strptime(out, "%a %b %d %H:%M:%S %Y"))
    except Exception:
        return None


def pid_reused(pid: int, file_started: Optional[float]) -> bool:
    """True when the process behind ``pid`` started after the discovery file was written: the pid now
    belongs to an unrelated process and the file is stale."""
    if not file_started:
        return False
    t = pid_start_time(pid)
    return t is not None and t > float(file_started) + 5.0


def list_instances(app: str) -> List[dict]:
    """Discovery files of live bridges for ``app`` ("pymol" or "chimerax"), newest first."""
    out = []
    d = instances_dir()
    for path in glob.glob(os.path.join(d, "%s-*.json" % app)):
        try:
            with open(path) as f:
                info = json.load(f)
        except Exception:
            continue
        info["_file"] = path
        pid = int(info.get("pid", 0))
        if not pid_alive(pid) or pid_reused(pid, info.get("started")):
            try:
                os.remove(path)
            except OSError:
                pass
            continue
        out.append(info)
    out.sort(key=lambda i: i.get("started", 0), reverse=True)
    return out


# ---------------------------------------------------------------------------
# executables
# ---------------------------------------------------------------------------

def _first_existing(patterns: List[str]) -> Optional[str]:
    for pat in patterns:
        for hit in sorted(glob.glob(os.path.expandvars(os.path.expanduser(pat))), reverse=True):
            if os.path.isfile(hit) and os.access(hit, os.X_OK):
                return hit
    return None


def find_pymol() -> Optional[str]:
    env = os.environ.get("PYMOL_EXE")
    if env and os.path.exists(env):
        return env
    for name in ("pymol", "PyMOL", "pymol.exe", "PyMOLWin.exe"):
        p = shutil.which(name)
        if p:
            return p
    if sys.platform == "darwin":
        return _first_existing([
            "/Applications/PyMOL.app/Contents/bin/pymol",
            "/Applications/PyMOL*.app/Contents/bin/pymol",
            "~/Applications/PyMOL*.app/Contents/bin/pymol",
            "/Applications/PyMOL.app/Contents/MacOS/PyMOL",
            "/opt/homebrew/bin/pymol",
            "/usr/local/bin/pymol",
            "~/miniconda3/envs/*/bin/pymol", "~/anaconda3/envs/*/bin/pymol", "~/miniforge3/envs/*/bin/pymol",
            "/opt/anaconda3/envs/*/bin/pymol", "/opt/anaconda3/bin/pymol",
        ])
    if sys.platform.startswith("win"):
        return _first_existing([
            r"C:\Program Files\Schrodinger\PyMOL2\PyMOLWin.exe",
            r"C:\Program Files\Schrodinger\PyMOL*\PyMOLWin.exe",
            r"C:\Program Files\PyMOL\PyMOLWin.exe",
            r"C:\Program Files\PyMOL*\PyMOLWin.exe",
            r"%LOCALAPPDATA%\Programs\PyMOL*\PyMOLWin.exe",
            r"%LOCALAPPDATA%\Schrodinger\PyMOL*\PyMOLWin.exe",
            r"%USERPROFILE%\miniconda3\envs\*\Scripts\pymol.exe",
            r"%USERPROFILE%\anaconda3\envs\*\Scripts\pymol.exe",
            r"%USERPROFILE%\miniconda3\Scripts\pymol.exe",
        ])
    return _first_existing([
        "/usr/bin/pymol", "/usr/local/bin/pymol", "/opt/pymol/bin/pymol", "/opt/pymol*/pymol",
        "~/pymol/bin/pymol", "~/pymol/pymol",
        "~/miniconda3/envs/*/bin/pymol", "~/anaconda3/envs/*/bin/pymol", "~/miniforge3/envs/*/bin/pymol",
        "~/mambaforge/envs/*/bin/pymol", "/opt/conda/envs/*/bin/pymol", "/opt/conda/bin/pymol",
        "~/.local/bin/pymol", "/snap/bin/pymol", "/var/lib/flatpak/exports/bin/*pymol*",
    ])


def find_chimerax() -> Optional[str]:
    env = os.environ.get("CHIMERAX_EXE")
    if env and os.path.exists(env):
        return env
    for name in ("chimerax", "ChimeraX", "ChimeraX.exe", "chimerax-daily", "ChimeraX-daily"):
        p = shutil.which(name)
        if p:
            return p
    if sys.platform == "darwin":
        return _first_existing([
            "/Applications/ChimeraX.app/Contents/bin/ChimeraX",
            "/Applications/ChimeraX-*.app/Contents/bin/ChimeraX",
            "/Applications/ChimeraX*.app/Contents/bin/ChimeraX",
            "~/Applications/ChimeraX*.app/Contents/bin/ChimeraX",
        ])
    if sys.platform.startswith("win"):
        return _first_existing([
            r"C:\Program Files\ChimeraX\bin\ChimeraX.exe",
            r"C:\Program Files\ChimeraX*\bin\ChimeraX.exe",
            r"C:\Program Files\UCSF\ChimeraX*\bin\ChimeraX.exe",
            r"%LOCALAPPDATA%\Programs\ChimeraX*\bin\ChimeraX.exe",
            r"%USERPROFILE%\ChimeraX*\bin\ChimeraX.exe",
        ])
    return _first_existing([
        "/usr/bin/chimerax", "/usr/local/bin/chimerax", "/opt/UCSF/ChimeraX/bin/ChimeraX",
        "/opt/UCSF/ChimeraX*/bin/ChimeraX", "/opt/UCSF/ChimeraX*/bin/chimerax", "/opt/chimerax*/bin/ChimeraX",
        "~/chimerax*/bin/ChimeraX", "~/ChimeraX*/bin/ChimeraX", "~/.local/bin/chimerax",
        "/var/lib/flatpak/exports/bin/*ChimeraX*", "/snap/bin/chimerax",
    ])


def chimerax_console_exe(exe: Optional[str]) -> Optional[str]:
    """On Windows ChimeraX ships ``ChimeraX-console.exe`` next to the GUI binary; it attaches to the
    console so stdout can be captured for ``--nogui`` runs.  Returns ``exe`` unchanged elsewhere."""
    if not exe or not sys.platform.startswith("win"):
        return exe
    base = os.path.basename(exe).lower()
    if base.startswith("chimerax") and base.endswith(".exe") and "console" not in base:
        cand = os.path.join(os.path.dirname(exe), "ChimeraX-console.exe")
        if os.path.exists(cand):
            return cand
    return exe


def app_launch_env() -> Dict[str, str]:
    env = dict(os.environ)
    env.setdefault("MOLMCP_HOME", molmcp_home())
    return env


def popen_detached(argv: List[str], cwd: Optional[str] = None, extra_env: Optional[Dict[str, str]] = None) -> subprocess.Popen:
    """Start a GUI application that outlives the MCP server process."""
    env = app_launch_env()
    if extra_env:
        env.update(extra_env)
    kw = dict(cwd=cwd, env=env, stdin=subprocess.DEVNULL,
              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if sys.platform.startswith("win"):
        kw["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    return subprocess.Popen(argv, **kw)


def wait_for_instance(app: str, timeout: float = 60.0, not_pids=()) -> Optional[dict]:
    t0 = time.time()
    while time.time() - t0 < timeout:
        for inst in list_instances(app):
            if inst.get("pid") not in not_pids:
                return inst
        time.sleep(0.25)
    return None


# ---------------------------------------------------------------------------
# a Python interpreter that can ``import pymol`` (for headless library mode)
# ---------------------------------------------------------------------------

_pymol_python_cache: Dict[str, Optional[str]] = {}


def _python_imports_pymol(python: str) -> bool:
    try:
        r = subprocess.run([python, "-c", "import pymol, pymol2"], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=60, env=app_launch_env())
        return r.returncode == 0
    except Exception:
        return False


def find_pymol_python(pymol_exe: Optional[str] = None) -> Optional[str]:
    env = os.environ.get("PYMOL_PYTHON")
    if env and os.path.exists(env):
        return env
    pymol_exe = pymol_exe or find_pymol()
    key = pymol_exe or ""
    if key in _pymol_python_cache:
        return _pymol_python_cache[key]
    candidates: List[str] = []
    if pymol_exe:
        d = os.path.dirname(os.path.realpath(pymol_exe))
        exe = "python.exe" if sys.platform.startswith("win") else "python"
        candidates += [os.path.join(d, exe), os.path.join(d, "python3"), os.path.join(d, "..", "MacOS", "python"),
                       os.path.join(d, "..", exe), os.path.join(d, "..", "bin", exe)]
        # shebang of a Python launcher script (conda/distro installs)
        try:
            with open(pymol_exe, "rb") as f:
                first = f.readline().decode("utf-8", "ignore").strip()
            if first.startswith("#!") and "python" in first:
                candidates.insert(0, first[2:].split()[0] if not first[2:].startswith("/usr/bin/env") else "")
        except Exception:
            pass
    candidates += [sys.executable, shutil.which("python3") or "", shutil.which("python") or ""]
    for c in candidates:
        if c and os.path.exists(c) and _python_imports_pymol(c):
            _pymol_python_cache[key] = os.path.abspath(c)
            return _pymol_python_cache[key]
    _pymol_python_cache[key] = None
    return None

"""Start the molmcp bridge inside a PyMOL process.

Usage:  pymol -r molmcp_pymol_launch.py            (GUI)
        run /path/to/molmcp_pymol_launch.py        (from the PyMOL command line)
        pymol -cq -r molmcp_pymol_launch.py        (headless fallback; prefer molmcp_pymol_headless.py)

Environment:
    MOLMCP_PYMOL_PORT    fixed port (default: random free port)
    MOLMCP_KEEPALIVE=1   headless (pymol -c): keep the process alive serving the bridge
                         (otherwise the script returns immediately, so it is safe in a pymolrc)
"""
import inspect
import os
import re
import sys
import time

try:
    _this = inspect.getfile(inspect.currentframe())
except Exception:
    _this = __file__
_here = os.path.dirname(os.path.abspath(_this))
if _here not in sys.path:
    sys.path.insert(0, _here)

import molmcp_pymol_bridge  # noqa: E402

_info = molmcp_pymol_bridge.launch()
if _info:
    print(" molmcp: PyMOL agent bridge ready on port %d" % _info["port"])


def _keep_alive_headless():
    """Headless ``pymol -c``: the script runs while PyMOL holds its API lock, so
    release it for the duration of the wait and take it back before returning."""
    from pymol import cmd
    lock = cmd.lock_api
    depth = 0
    try:
        m = re.search(r"count=(\d+)", repr(lock))
        if m and getattr(lock, "_is_owned", lambda: False)():
            depth = int(m.group(1))
    except Exception:
        depth = 0
    for _ in range(depth):
        lock.release()
    try:
        while not molmcp_pymol_bridge.shutdown_requested() and molmcp_pymol_bridge.connection_info() is not None:
            time.sleep(0.25)
    except KeyboardInterrupt:
        pass
    finally:
        for _ in range(depth):
            lock.acquire()


if not molmcp_pymol_bridge.is_gui() and os.environ.get("MOLMCP_KEEPALIVE", "0") == "1":
    _keep_alive_headless()

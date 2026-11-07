"""Headless PyMOL with the molmcp bridge, using PyMOL as a library.

Run with a Python that can ``import pymol`` (the one bundled with PyMOL):

    python molmcp_pymol_headless.py [--port N]

The process stays alive until the bridge receives a ``quit`` operation or the
process is terminated.  No GUI, no busy loop, rendering via ray tracing.
"""
import os
import sys
import time

_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    port = None
    if "--port" in argv:
        port = int(argv[argv.index("--port") + 1])
    import pymol
    import pymol2
    pymol.invocation.parse_args(["pymol", "-cq"])
    p = pymol2.SingletonPyMOL()
    p.start()
    import molmcp_pymol_bridge
    info = molmcp_pymol_bridge.launch(port)
    print(" molmcp: headless PyMOL agent bridge ready on port %d (pid %d)" % (info["port"], os.getpid()), flush=True)
    # Drive PyMOL's command queue (cmd.do, scene animation, deferred work)
    # without the 100%-CPU keep-alive loop PyMOL uses for "pymol -K".
    try:
        while not molmcp_pymol_bridge.shutdown_requested():
            try:
                busy = p.idle()
            except Exception:
                busy = False
            time.sleep(0.01 if busy else 0.05)
    except KeyboardInterrupt:
        pass
    molmcp_pymol_bridge.stop()
    # p.stop() can block on PyMOL's shutdown in library mode; never leave an orphan behind
    import threading

    def _stop():
        try:
            p.stop()
        except Exception:
            pass
    t = threading.Thread(target=_stop, daemon=True)
    t.start()
    t.join(10)
    os._exit(0)


if __name__ == "__main__":
    main()

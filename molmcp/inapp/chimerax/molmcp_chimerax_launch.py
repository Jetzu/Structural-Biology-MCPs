"""Start the molmcp agent bridge inside ChimeraX without installing the bundle.

    chimerax --script /path/to/molmcp_chimerax_launch.py
    open /path/to/molmcp_chimerax_launch.py          (from the ChimeraX command line)
"""
import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
_pkgroot = os.path.join(_here, "chimerax_agentbridge")

import chimerax  # noqa: E402

_extra = os.path.join(_pkgroot, "chimerax")
if _extra not in chimerax.__path__:
    chimerax.__path__.append(_extra)

from chimerax.agentbridge import ops, cmd as _cmd  # noqa: E402

try:
    _cmd.register_commands(session.logger)  # noqa: F821  (session is injected by ChimeraX)
except Exception:
    pass
_info = ops.start(session)  # noqa: F821
session.logger.info("molmcp: ChimeraX agent bridge ready on port %d" % _info["port"])  # noqa: F821

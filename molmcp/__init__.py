"""molmcp: Model Context Protocol servers for PyMOL and ChimeraX.

Two independent MCP servers (``pymol-mcp`` and ``chimerax-mcp``) that talk to
a lightweight bridge running *inside* the respective application.  The bridge
gives the agent synchronous command execution, structured scene state,
events, and in-memory renders that are analysed numerically (no vision model
needed).
"""

__version__ = "0.1.0"

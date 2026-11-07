"""molmcp ChimeraX bundle: in-app bridge for MCP agents (Claude Code, Codex, ...).

Commands:  agent start [port N]   agent stop   agent status   agent chat   claude <text>   codex <text>
The bridge auto-starts when ChimeraX launches unless MOLMCP_CHIMERAX_AUTOSTART=0.
"""
__version__ = "0.1.0"

from chimerax.core.toolshed import BundleAPI


class _AgentBridgeAPI(BundleAPI):
    api_version = 1

    @staticmethod
    def initialize(session, bundle_info):
        import os
        if os.environ.get("MOLMCP_CHIMERAX_AUTOSTART", "1") == "0":
            return
        from . import ops

        def _start(*args):
            try:
                ops.start(session, quiet=True)
            except Exception as e:
                session.logger.warning("molmcp agent bridge failed to start: %s" % e)
            from chimerax.core.triggerset import DEREGISTER
            return DEREGISTER

        if getattr(session.ui, "is_gui", False):
            try:
                session.ui.triggers.add_handler("ready", _start)
                return
            except Exception:
                pass
        _start()

    @staticmethod
    def finish(session, bundle_info):
        from . import ops
        ops.stop(session)

    @staticmethod
    def register_command(bi, ci, logger):
        from . import cmd
        cmd.register_commands(logger)

    @staticmethod
    def start_tool(session, bi, ti):
        from . import tool
        return tool.get_tool(session, create=True)

    @staticmethod
    def run_provider(session, name, mgr, **kw):
        # toolbar button ("Agent" tab) -> open / raise the chat panel
        from . import tool
        t = tool.get_tool(session, create=True)
        if t is not None:
            try:
                t.tool_window.shown = True
            except Exception:
                pass
        return t


bundle_api = _AgentBridgeAPI()

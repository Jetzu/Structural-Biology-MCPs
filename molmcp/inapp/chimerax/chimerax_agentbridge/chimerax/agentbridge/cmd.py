from chimerax.core.commands import CmdDesc, register, IntArg, RestOfLine


def agent_start(session, port=None):
    from . import ops
    return ops.start(session, port=port)


def agent_stop(session):
    from . import ops
    ops.stop(session)


def agent_status(session):
    from . import ops
    return ops.status(session)


def agent_name(session, name=""):
    from . import ops
    return ops.set_name(session, name)


def agent_chat(session):
    from . import tool
    t = tool.get_tool(session, create=True)
    if t is None:
        session.logger.info("Agent Chat needs the ChimeraX GUI; use 'claude <text>' or 'codex <text>' instead.")
    return t


def claude(session, text):
    from . import tool
    tool.ask(session, "claude", text)


def codex(session, text):
    from . import tool
    tool.ask(session, "codex", text)


_registered = False


def register_commands(logger):
    global _registered
    if _registered:
        return
    _registered = True
    register("agent start", CmdDesc(keyword=[("port", IntArg)], synopsis="Start the molmcp agent bridge (MCP)"),
             agent_start, logger=logger)
    register("agent stop", CmdDesc(synopsis="Stop the molmcp agent bridge"), agent_stop, logger=logger)
    register("agent status", CmdDesc(synopsis="Show molmcp agent bridge connection info"), agent_status, logger=logger)
    register("agent info", CmdDesc(synopsis="Show molmcp agent bridge connection info"), agent_status, logger=logger)
    register("agent chat", CmdDesc(synopsis="Open the Agent Chat panel (Claude Code / Codex)"), agent_chat, logger=logger)
    register("agent name", CmdDesc(optional=[("name", RestOfLine)], synopsis="Name this window so an agent can pick it (MCP status tool)"), agent_name, logger=logger)
    register("claude", CmdDesc(required=[("text", RestOfLine)], synopsis="Ask Claude Code about this session (uses the chimerax MCP server)"),
             claude, logger=logger)
    register("codex", CmdDesc(required=[("text", RestOfLine)], synopsis="Ask Codex about this session (uses the chimerax MCP server)"),
             codex, logger=logger)

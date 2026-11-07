"""ChimeraX tool panel: Claude-Code-style chat with Claude Code / Codex about the current session."""
from __future__ import annotations

import os

from chimerax.core.tools import ToolInstance

from . import agentcli

BACKEND_LABELS = [("claude", "Claude Code"), ("codex", "Codex")]
_sessions = {"claude": None, "codex": None}


def get_tool(session, create=True):
    for t in session.tools.list():
        if isinstance(t, AgentChatTool):
            return t
    if not create or not getattr(session.ui, "is_gui", False):
        return None
    return AgentChatTool(session, "Agent Chat")


def start_run(session, backend, prompt, callback, allow_shell=False):
    session_id = _sessions.get(backend)

    def cb(kind, payload):
        if kind == "session":
            _sessions[backend] = payload
        callback(kind, payload)

    run = agentcli.AgentRun(backend, prompt, "chimerax", os.getpid(), cb, session_id=session_id,
                            cwd=os.getcwd(), allow_shell=allow_shell)
    return run.start()


def ask(session, backend, prompt, wait=False, timeout=600.0):
    """Shared by the `claude` / `codex` commands and the bridge op."""
    prompt = (prompt or "").strip()
    if not prompt:
        session.logger.warning("usage: %s <question or instruction>" % backend)
        return None
    tool = get_tool(session, create=True)
    if tool is not None:
        tool.chat.set_backend(backend)
        tool.chat.submit(prompt)
        run = tool.chat.run
        if run is None:
            return None
    else:
        label = dict(BACKEND_LABELS)[backend]

        def cb(kind, payload):
            if kind == "text":
                session.ui.thread_safe(session.logger.info, "%s: %s" % (label, payload))
            elif kind == "tool":
                session.ui.thread_safe(session.logger.info, "   -> " + payload)
            elif kind == "error":
                session.ui.thread_safe(session.logger.warning, "%s: %s" % (label, payload))
        try:
            run = start_run(session, backend, prompt, cb)
        except Exception as e:
            session.logger.error(str(e))
            return None
    if wait:
        run.wait(timeout)
        return {"final_text": run.final_text, "session_id": run.session_id, "returncode": run.returncode}
    return run


class AgentChatTool(ToolInstance):
    SESSION_ENDURING = True
    SESSION_SAVE = False
    help = None

    def __init__(self, session, tool_name="Agent Chat"):
        super().__init__(session, tool_name)
        from chimerax.ui import MainToolWindow
        from Qt import QtCore, QtGui, QtWidgets
        from . import agentchat_ui
        self.tool_window = MainToolWindow(self)
        self.display_name = "Agent Chat (Claude Code / Codex)"
        parent = self.tool_window.ui_area
        lay = QtWidgets.QVBoxLayout(parent)
        lay.setContentsMargins(0, 0, 0, 0)
        self.chat = agentchat_ui.make_chat_widget(
            QtWidgets, QtCore, QtGui, app="chimerax", pid=os.getpid(),
            start_run=lambda backend, prompt, cb: start_run(session, backend, prompt, cb),
            sessions=_sessions, cwd=os.getcwd(), find_backend=agentcli.find_backend, title="Agent Chat for ChimeraX")
        lay.addWidget(self.chat)
        self.tool_window.manage("side")

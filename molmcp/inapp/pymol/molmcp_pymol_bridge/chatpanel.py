"""In-PyMOL Claude-Code-style chat (Qt dock) plus the `claude` / `codex` / `agent_chat` commands."""
from __future__ import annotations

import os

from . import agentcli

_dock = None
_sessions = {"claude": None, "codex": None}


def _gui_window():
    try:
        from pymol import gui
        return gui.get_qtwindow()
    except Exception:
        return None


def start_run(backend, prompt, callback, allow_shell=False):
    """Start a CLI run bound to this PyMOL process; callback(kind, payload) is called from a worker thread."""
    session_id = _sessions.get(backend)

    def cb(kind, payload):
        if kind == "session":
            _sessions[backend] = payload
        callback(kind, payload)

    run = agentcli.AgentRun(backend, prompt, "pymol", os.getpid(), cb, session_id=session_id,
                            cwd=os.getcwd(), allow_shell=allow_shell)
    return run.start()


def show_panel():
    """Create (once) and show the dock; returns it, or None without a GUI."""
    global _dock
    window = _gui_window()
    if window is None:
        return None
    if _dock is None:
        from pymol.Qt import QtCore, QtGui, QtWidgets
        from . import agentchat_ui
        widget = agentchat_ui.make_chat_widget(QtWidgets, QtCore, QtGui, app="pymol", pid=os.getpid(),
                                               start_run=start_run, sessions=_sessions, cwd=os.getcwd(),
                                               find_backend=agentcli.find_backend, title="Agent Chat for PyMOL")
        _dock = QtWidgets.QDockWidget("Agent Chat (Claude Code / Codex)", window)
        _dock.setObjectName("molmcp_agent_chat")
        _dock.setWidget(widget)
        _dock.chat = widget
        area = getattr(QtCore.Qt, "RightDockWidgetArea", None) or QtCore.Qt.DockWidgetArea.RightDockWidgetArea
        window.addDockWidget(area, _dock)
        _dock.resize(560, 700)
    _dock.show()
    _dock.raise_()
    return _dock


def ask(backend, prompt, wait=False, timeout=600.0):
    """`claude ...` / `codex ...`.  GUI: goes through the panel.  Headless: prints events to the log."""
    prompt = (prompt or "").strip()
    if not prompt:
        print(" usage: %s <question or instruction>" % backend)
        return None
    dock = show_panel()
    if dock is not None:
        chat = dock.chat
        chat.set_backend(backend)
        chat.submit(prompt)
        run = chat.run
        if run is None:
            return None
    else:
        events = []

        def cb(kind, payload):
            events.append((kind, payload))
            if kind == "text":
                print(" %s: %s" % (backend, payload))
            elif kind == "tool":
                print("    -> " + payload)
            elif kind == "error":
                print(" %s error: %s" % (backend, payload))
        try:
            run = start_run(backend, prompt, cb)
        except Exception as e:
            print(" Error: %s" % e)
            return None
    if wait:
        run.wait(timeout)
        return {"final_text": run.final_text, "session_id": run.session_id, "returncode": run.returncode}
    return run


def register_commands(cmd):
    def _mk(backend):
        def f(*args, **kw):
            return ask(backend, ", ".join(str(a) for a in args))
        f.__name__ = backend
        f.__doc__ = ("DESCRIPTION\n\n    Ask %s about (or to change) the current PyMOL session.  The agent uses the\n"
                     "    pymol MCP server bound to this process.\n\nUSAGE\n\n    %s what is shown? colour chain A red\n"
                     % ({"claude": "Claude Code", "codex": "Codex"}[backend], backend))
        return f
    cmd.extend("claude", _mk("claude"))
    cmd.extend("codex", _mk("codex"))
    cmd.extend("agent_chat", lambda: show_panel())

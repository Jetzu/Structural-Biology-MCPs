"""Claude-Code-style chat widget shared by the PyMOL plugin and the ChimeraX bundle.

Pure Qt (works with PyQt5/PyQt6/PySide via the module objects passed in) so the same file is used inside both
viewers.  The host supplies ``start_run(backend, prompt, callback)`` (see agentcli.AgentRun); events reach the
widget through a queued Qt signal so they may come from any thread.

Look & feel mirrors the Claude Code terminal UI: dark monospace transcript, ``>`` user prompts, ``⏺`` lines
for assistant text and tool calls, ``⎿`` result previews, an animated status line while the agent works, a
bordered ``>`` input box with slash commands (/clear /claude /codex /stop /help) and a shortcuts footer.
"""
from __future__ import annotations

import html
import json
import os
import re
import time

ORANGE = "#D97757"      # Claude's accent
BG = "#1F1F1F"
BG_INPUT = "#262626"
FG = "#E6E6E6"
DIM = "#8B8B8B"
GREEN = "#5FB369"
RED = "#E5484D"
BORDER = "#3A3A3A"
CODE_BG = "#2B2B2B"
SPINNER = "·✢✳✶✻✽✻✶✳✢"
VERBS = ["Thinking", "Pondering", "Working", "Inspecting", "Rendering", "Reasoning", "Composing"]
BACKENDS = [("claude", "Claude Code"), ("codex", "Codex")]
HELP = ("/clear  new conversation    /claude  /codex  switch agent    /stop  interrupt    /help  this list\n"
        "Enter sends · Shift+Enter newline · Esc interrupts · ↑/↓ history")


def _enum(ns, group, name):
    """PyQt5 exposes Qt.Key_Return; PyQt6 exposes Qt.Key.Key_Return."""
    v = getattr(ns, name, None)
    if v is None:
        v = getattr(getattr(ns, group), name)
    return v


def _esc(s):
    return html.escape(str(s), quote=False)


def _md_inline(s):
    """Tiny markdown: code spans, bold, italics; newlines kept."""
    s = _esc(s)
    s = re.sub(r"`([^`\n]+)`", r'<code style="background:%s;padding:0 3px;border-radius:3px">\1</code>' % CODE_BG, s)
    s = re.sub(r"\*\*([^*\n]+)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<i>\1</i>", s)
    return s


def _md_block(text):
    """Fenced code blocks + paragraphs/lines."""
    out = []
    parts = re.split(r"```[a-zA-Z0-9_+-]*\n?", text)
    for i, part in enumerate(parts):
        if i % 2 == 1:   # inside a fence
            out.append('<pre style="background:%s;padding:6px 8px;border-radius:4px;margin:4px 0 4px 14px;white-space:pre-wrap">%s</pre>'
                       % (CODE_BG, _esc(part.rstrip("\n"))))
        else:
            lines = [_md_inline(l) for l in part.strip("\n").split("\n")]
            if lines and any(lines):
                out.append("<br/>".join(lines))
    return "".join(out)


def _preview(text, max_lines=2, width=110):
    text = str(text)
    stripped = text.strip()
    if stripped[:1] in "{[":          # JSON result: one compact line, like a collapsed tool result
        try:
            obj = json.loads(stripped)
            compact = json.dumps(obj, ensure_ascii=False)
            total = len(text.splitlines())
            return ([compact if len(compact) <= width else compact[:width - 1] + "…"], max(0, total - 1))
        except Exception:
            pass
    lines = [l for l in text.splitlines() if l.strip()]
    shown = []
    for l in lines[:max_lines]:
        shown.append(l if len(l) <= width else l[:width - 1] + "…")
    more = len(lines) - len(shown)
    return shown, more


def make_chat_widget(QtWidgets, QtCore, QtGui, *, app, pid, start_run, sessions, cwd=None,
                     find_backend=None, title="Agent Chat"):
    """Return a QWidget with .submit(text), .on_event(kind, payload), .set_backend(key), .relay (signal source)."""
    Signal = getattr(QtCore, "Signal", None) or getattr(QtCore, "pyqtSignal")
    Qt = QtCore.Qt
    K_RETURN, K_ENTER = _enum(Qt, "Key", "Key_Return"), _enum(Qt, "Key", "Key_Enter")
    K_ESC, K_UP, K_DOWN = _enum(Qt, "Key", "Key_Escape"), _enum(Qt, "Key", "Key_Up"), _enum(Qt, "Key", "Key_Down")
    SHIFT = _enum(Qt, "KeyboardModifier", "ShiftModifier")
    mono = "Menlo, 'SF Mono', Consolas, 'DejaVu Sans Mono', monospace"

    class Relay(QtCore.QObject):
        event = Signal(str, str)

    class PromptEdit(QtWidgets.QPlainTextEdit):
        submitted = Signal()
        interrupted = Signal()
        history_prev = Signal()
        history_next = Signal()

        def keyPressEvent(self, ev):
            k = ev.key()
            if k in (K_RETURN, K_ENTER) and not (ev.modifiers() & SHIFT):
                self.submitted.emit()
                return
            if k == K_ESC:
                self.interrupted.emit()
                return
            if k == K_UP and self.textCursor().blockNumber() == 0:
                self.history_prev.emit()
                return
            if k == K_DOWN and self.textCursor().blockNumber() == self.document().blockCount() - 1:
                self.history_next.emit()
                return
            super().keyPressEvent(ev)

    class ChatWidget(QtWidgets.QWidget):
        def __init__(self):
            super().__init__()
            self.app, self.pid = app, pid
            self.backend = "claude"
            self.blocks = []            # rendered transcript blocks (html strings)
            self.draft = None           # index of the block receiving streamed deltas
            self.draft_text = ""
            self.run = None
            self.t0 = None
            self.history, self.hist_pos = [], 0
            self.relay = Relay()
            self.relay.event.connect(self.on_event)
            self.spin = 0
            self.verb = VERBS[0]
            self._last_stats = None
            self.timer = QtCore.QTimer(self)
            self.timer.timeout.connect(self._tick)
            self.render_timer = QtCore.QTimer(self)
            self.render_timer.setSingleShot(True)
            self.render_timer.timeout.connect(self._render)
            self._build()
            self._welcome()

        # ---- layout ------------------------------------------------------
        def _build(self):
            self.setMinimumSize(500, 440)
            self.setStyleSheet(
                "QWidget{background:%s;color:%s;font-family:%s;font-size:12.5px}"
                "QTextBrowser{background:%s;border:none;padding:6px 10px}"
                "QPlainTextEdit{background:%s;border:1px solid %s;border-radius:4px;padding:4px 6px;color:%s;"
                "selection-background-color:%s}"
                "QLabel{color:%s}" % (BG, FG, mono, BG, BG_INPUT, BORDER, FG, ORANGE, DIM))
            lay = QtWidgets.QVBoxLayout(self)
            lay.setContentsMargins(6, 6, 6, 6)
            lay.setSpacing(4)
            self.view = QtWidgets.QTextBrowser()
            self.view.setOpenExternalLinks(False)
            self.view.setReadOnly(True)
            lay.addWidget(self.view, 1)
            self.status = QtWidgets.QLabel("")
            self.status.setStyleSheet("color:%s;padding-left:4px" % ORANGE)
            self.status.hide()
            lay.addWidget(self.status)
            row = QtWidgets.QHBoxLayout()
            row.setSpacing(6)
            caret = QtWidgets.QLabel(">")
            caret.setStyleSheet("color:%s;font-weight:bold;padding-top:4px" % FG)
            caret.setAlignment(_enum(Qt, "AlignmentFlag", "AlignTop"))
            row.addWidget(caret)
            self.prompt = PromptEdit()
            self.prompt.setPlaceholderText('Try "what is shown and how is it coloured?" or "colour chain A red and zoom on it"')
            self.prompt.setFixedHeight(54)
            self.prompt.submitted.connect(self._on_submit)
            self.prompt.interrupted.connect(self.stop)
            self.prompt.history_prev.connect(lambda: self._history(-1))
            self.prompt.history_next.connect(lambda: self._history(+1))
            row.addWidget(self.prompt, 1)
            lay.addLayout(row)
            foot = QtWidgets.QHBoxLayout()
            self.foot_left = QtWidgets.QLabel("? for shortcuts")
            self.foot_right = QtWidgets.QLabel("")
            self.foot_right.setAlignment(_enum(Qt, "AlignmentFlag", "AlignRight"))
            foot.addWidget(self.foot_left)
            foot.addWidget(self.foot_right, 1)
            lay.addLayout(foot)
            self._update_footer()

        def _update_footer(self):
            label = dict(BACKENDS)[self.backend]
            exe = find_backend(self.backend) if find_backend else None
            miss = "" if exe or not find_backend else "  (CLI not found)"
            self.foot_right.setText('<span style="color:%s">%s</span><span style="color:%s">%s · %s pid %d</span>'
                                    % (ORANGE, label.lower(), DIM, miss, self.app, self.pid))

        # ---- transcript blocks ----------------------------------------------
        def _welcome(self):
            where = cwd or os.getcwd()
            # Qt rich text has no CSS borders on divs; a one-cell table draws the Claude-Code-style box
            box = ('<table width="100%%" cellpadding="7" cellspacing="0" style="border:1px solid %s;margin:2px 0 8px 0">'
                   '<tr><td style="border:1px solid %s">'
                   '<span style="color:%s">✻</span> <b>Welcome to %s</b><br/><br/>'
                   '<span style="color:%s">%s is connected to this %s window (pid %d).<br/>'
                   'cwd: %s<br/>Type a request below · /help for shortcuts</span></td></tr></table>'
                   % (BORDER, BORDER, ORANGE, _esc(title), DIM, dict(BACKENDS)[self.backend], self.app, self.pid, _esc(where)))
            self._add(box)

        def _add(self, html_block):
            self.blocks.append(html_block)
            self._schedule_render()
            return len(self.blocks) - 1

        def _schedule_render(self):
            if not self.render_timer.isActive():
                self.render_timer.start(30)

        def _render(self):
            doc = '<div style="font-family:%s;font-size:12.5px;color:%s;line-height:1.35">%s</div>' % (
                mono, FG, '<div style="margin:0 0 6px 0"></div>'.join(self.blocks))
            self.view.setHtml(doc)
            self._scroll_bottom()
            QtCore.QTimer.singleShot(0, self._scroll_bottom)   # again once the document is laid out

        def _scroll_bottom(self):
            try:
                cur = self.view.textCursor()
                cur.movePosition(_enum(QtGui.QTextCursor, "MoveOperation", "End"))
                self.view.setTextCursor(cur)
                self.view.ensureCursorVisible()
            except Exception:
                pass
            sb = self.view.verticalScrollBar()
            sb.setValue(sb.maximum())

        def add_user(self, text):
            self._add('<div style="color:%s;margin:6px 0 4px 0"><span style="color:%s">&gt;</span> %s</div>'
                      % (DIM, FG, _md_inline(text).replace("\n", "<br/>")))

        def add_assistant(self, text):
            self.draft = None
            self.draft_text = ""
            self._add('<div><span style="color:%s">⏺</span> %s</div>' % (ORANGE, _md_block(text)))

        def add_delta(self, delta):
            if self.draft is None:
                self.draft_text = ""
                self.draft = self._add("")
            self.draft_text += delta
            self.blocks[self.draft] = '<div><span style="color:%s">⏺</span> %s<span style="color:%s">▌</span></div>' % (
                ORANGE, _md_block(self.draft_text), DIM)
            self._schedule_render()

        def finalize_draft(self, text):
            if self.draft is not None:
                self.blocks[self.draft] = '<div><span style="color:%s">⏺</span> %s</div>' % (ORANGE, _md_block(text))
                self.draft = None
                self.draft_text = ""
                self._schedule_render()
            else:
                self.add_assistant(text)

        def add_tool(self, text):
            self.draft = None
            name, _, args = text.partition(" ")
            self._add('<div><span style="color:%s">⏺</span> <b>%s</b><span style="color:%s">(%s)</span></div>'
                      % (GREEN, _esc(name), DIM, _esc(args[:400])))

        def add_tool_result(self, text):
            shown, more = _preview(text)
            tail = ('<br/>&nbsp;&nbsp;&nbsp;… +%d lines' % more) if more > 0 else ""
            self._add('<div style="color:%s;margin-left:14px">⎿&nbsp; %s%s</div>'
                      % (DIM, "<br/>&nbsp;&nbsp;&nbsp;".join(_esc(l) for l in shown) or "(no output)", tail))

        def add_note(self, text, color=DIM):
            self._add('<div style="color:%s">%s</div>' % (color, _esc(text).replace("\n", "<br/>")))

        # ---- running -----------------------------------------------------------
        def set_backend(self, key):
            if key in dict(BACKENDS):
                self.backend = key
                self._update_footer()

        def submit(self, text):
            text = (text or "").strip()
            if not text:
                return
            if text.startswith("/"):
                return self._slash(text)
            if self.run is not None:
                self.add_note("(still working — Esc to interrupt)")
                return
            self.history.append(text)
            self.hist_pos = len(self.history)
            self.add_user(text)
            try:
                self.run = start_run(self.backend, text, lambda k, p: self.relay.event.emit(k, p if isinstance(p, str) else json.dumps(p)))
            except Exception as e:
                self.add_note("! %s" % e, RED)
                self.run = None
                return
            self.t0 = time.time()
            self.verb = VERBS[len(self.history) % len(VERBS)]
            self.status.show()
            self.timer.start(120)
            self.prompt.setEnabled(True)
            self.prompt.setFocus()

        def _slash(self, text):
            cmd, _, rest = text.partition(" ")
            cmd = cmd.lower()
            if cmd == "/clear":
                sessions[self.backend] = None
                self.blocks = []
                self._welcome()
                self.add_note("conversation cleared")
            elif cmd in ("/claude", "/codex"):
                self.set_backend(cmd[1:])
                self.add_note("agent: %s" % dict(BACKENDS)[self.backend])
                if rest.strip():
                    self.submit(rest)
            elif cmd == "/stop":
                self.stop()
            elif cmd in ("/help", "/?"):
                self.add_note(HELP)
            else:
                self.add_note("unknown command %s — /help" % cmd, RED)

        def _on_submit(self):
            text = self.prompt.toPlainText()
            self.prompt.clear()
            self.submit(text)

        def _history(self, step):
            if not self.history:
                return
            self.hist_pos = max(0, min(len(self.history), self.hist_pos + step))
            self.prompt.setPlainText(self.history[self.hist_pos] if self.hist_pos < len(self.history) else "")
            self.prompt.moveCursor(_enum(QtGui.QTextCursor, "MoveOperation", "End"))

        def stop(self):
            if self.run is not None:
                self.run.cancel()
                self.add_note("interrupted", RED)

        def _tick(self):
            self.spin = (self.spin + 1) % len(SPINNER)
            secs = int(time.time() - self.t0) if self.t0 else 0
            self.status.setText('<span style="color:%s">%s %s…</span> <span style="color:%s">(esc to interrupt · %ds)</span>'
                                % (ORANGE, SPINNER[self.spin], self.verb, DIM, secs))

        def _finish(self, stats=None):
            self.timer.stop()
            self.status.hide()
            secs = time.time() - self.t0 if self.t0 else 0
            extra = ""
            if stats:
                cost = stats.get("total_cost_usd")
                usage = stats.get("usage") or {}
                toks = usage.get("output_tokens") or stats.get("output_tokens")
                if cost is not None:
                    extra += " · $%.2f" % cost
                if toks:
                    extra += " · %s output tokens" % toks
            self.add_note("✓ %s · %.1fs%s" % (dict(BACKENDS)[self.backend].lower(), secs, extra))
            self.run = None
            self.t0 = None
            self.prompt.setFocus()

        # ---- events from the worker thread (via queued signal) ---------------
        def on_event(self, kind, payload):
            if kind == "delta":
                self.add_delta(payload)
            elif kind == "text":
                self.finalize_draft(payload)
            elif kind == "tool":
                self.add_tool(payload)
            elif kind == "tool_result":
                self.add_tool_result(payload)
            elif kind == "error":
                self.add_note("! " + payload, RED)
            elif kind == "stats":
                try:
                    self._last_stats = json.loads(payload)
                except Exception:
                    self._last_stats = None
            elif kind == "done":
                if self.draft is not None and payload:
                    self.finalize_draft(payload)
                self._finish(getattr(self, "_last_stats", None))
                self._last_stats = None

    return ChatWidget()

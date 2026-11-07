"""Tests for the in-app agent CLI driver (no real CLI needed)."""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "molmcp", "inapp", "shared"))
import agentcli  # noqa: E402


class TestDiscovery(unittest.TestCase):
    def test_env_override(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            exe = f.name
        try:
            with mock.patch.dict(os.environ, {"MOLMCP_CLAUDE_EXE": exe, "MOLMCP_CODEX_EXE": exe}):
                self.assertEqual(agentcli.find_claude(), exe)
                self.assertEqual(agentcli.find_codex(), exe)
        finally:
            os.remove(exe)

    def test_no_crash_without_cli(self):
        env = {k: v for k, v in os.environ.items() if k not in ("MOLMCP_CLAUDE_EXE", "CLAUDE_CLI", "MOLMCP_CODEX_EXE", "CODEX_CLI")}
        env["PATH"] = ""
        for plat in ("win32", "linux", "darwin"):
            with mock.patch.object(sys, "platform", plat), mock.patch.dict(os.environ, env, clear=True):
                agentcli.find_claude()
                agentcli.find_codex()


class TestCleanEnv(unittest.TestCase):
    def test_strips_interpreter_vars_and_keeps_others(self):
        with mock.patch.dict(os.environ, {"PYTHONHOME": "/app/py", "PYTHONEXECUTABLE": "/app/py/bin/python",
                                          "PYTHONPATH": "/app/lib", "DYLD_LIBRARY_PATH": "/app/lib", "KEEP_ME": "1",
                                          "PATH": "/usr/bin"}):
            env = agentcli.clean_env()
        for k in ("PYTHONHOME", "PYTHONEXECUTABLE", "PYTHONPATH", "DYLD_LIBRARY_PATH"):
            self.assertNotIn(k, env)
        self.assertEqual(env["KEEP_ME"], "1")
        if not sys.platform.startswith("win"):
            self.assertIn("/usr/local/bin", env["PATH"].split(os.pathsep))
            self.assertEqual(env["PATH"].split(os.pathsep)[0], "/usr/bin")


class TestArgv(unittest.TestCase):
    def test_claude_argv(self):
        argv = agentcli.build_argv("claude", "/x/claude", "colour chain A red", "pymol", 123)
        self.assertEqual(argv[:3], ["/x/claude", "-p", "colour chain A red"])
        self.assertIn("stream-json", argv)
        self.assertEqual(argv[argv.index("--allowedTools") + 1], "mcp__pymol")
        self.assertIn("process id 123", argv[argv.index("--append-system-prompt") + 1])
        self.assertNotIn("--resume", argv)
        argv = agentcli.build_argv("claude", "/x/claude", "again", "chimerax", 5, session_id="abc", allow_shell=True)
        self.assertEqual(argv[argv.index("--resume") + 1], "abc")
        self.assertIn("Bash", argv[argv.index("--allowedTools") + 1])

    def test_codex_argv(self):
        argv = agentcli.build_argv("codex", "/x/codex", "what is shown?", "chimerax", 7)
        self.assertEqual(argv[:2], ["/x/codex", "exec"])
        self.assertIn("--json", argv)
        self.assertIn("--approve-for-me", argv)
        self.assertTrue(argv[-1].startswith("You are embedded in ChimeraX (process id 7)"))
        self.assertTrue(argv[-1].endswith("User request: what is shown?"))
        argv = agentcli.build_argv("codex", "/x/codex", "more", "pymol", 7, session_id="thread-1")
        self.assertEqual(argv[2], "resume")
        self.assertEqual(argv[-2:], ["thread-1", "more"])

    def test_unknown_backend(self):
        with self.assertRaises(ValueError):
            agentcli.build_argv("gpt", "/x", "p", "pymol", 1)


class TestParsers(unittest.TestCase):
    def test_claude_events(self):
        got = []
        cb = lambda k, p: got.append((k, p))  # noqa: E731
        agentcli._parse_claude({"type": "system", "subtype": "init", "session_id": "s1"}, cb)
        agentcli._parse_claude({"type": "assistant", "message": {"content": [
            {"type": "text", "text": "Looking."}, {"type": "tool_use", "name": "mcp__pymol__render", "input": {"width": 320}}]}}, cb)
        agentcli._parse_claude({"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Do"}}}, cb)
        agentcli._parse_claude({"type": "user", "message": {"content": [{"type": "tool_result", "content": [{"type": "text", "text": "{\"result\": \"{\\\"ok\\\": true}\"}"}]}]}}, cb)
        agentcli._parse_claude({"type": "result", "subtype": "success", "result": "Done.", "session_id": "s1", "total_cost_usd": 0.01}, cb)
        self.assertEqual(got[0], ("session", "s1"))
        self.assertEqual(got[1], ("text", "Looking."))
        self.assertTrue(got[2][0] == "tool" and got[2][1].startswith("pymol/render"))
        self.assertEqual(got[3], ("delta", "Do"))
        self.assertEqual(got[4], ("tool_result", '{"ok": true}'))
        self.assertEqual(got[5][0], "stats")
        self.assertEqual(got[-1], ("done", "Done."))

    def test_codex_events(self):
        got = []
        cb = lambda k, p: got.append((k, p))  # noqa: E731
        agentcli._parse_codex({"type": "thread.started", "thread_id": "t1"}, cb)
        agentcli._parse_codex({"type": "item.started", "item": {"type": "mcp_tool_call", "server": "chimerax", "tool": "run", "status": "in_progress", "arguments": {"commands": ["color red"]}}}, cb)
        agentcli._parse_codex({"type": "item.completed", "item": {"type": "mcp_tool_call", "server": "chimerax", "tool": "run", "status": "completed", "result": "{\"all_ok\": true}"}}, cb)
        agentcli._parse_codex({"type": "item.completed", "item": {"type": "agent_message", "text": "Coloured."}}, cb)
        agentcli._parse_codex({"type": "turn.completed", "usage": {"output_tokens": 5}}, cb)
        self.assertEqual(got[0], ("session", "t1"))
        self.assertEqual(got[1], ("tool", 'chimerax/run {"commands": ["color red"]}'))
        self.assertEqual(got[2], ("tool_result", '{"all_ok": true}'))
        self.assertEqual(got[3], ("text", "Coloured."))
        self.assertEqual(got[4][0], "stats")
        self.assertEqual(got[5], ("done", ""))


class TestRun(unittest.TestCase):
    def test_run_with_fake_cli(self):
        """A fake 'codex' script that prints JSONL events exercises the whole streaming path."""
        with tempfile.TemporaryDirectory() as d:
            fake = os.path.join(d, "codex")
            with open(fake, "w") as f:
                f.write("#!/bin/sh\n"
                        "echo '{\"type\":\"thread.started\",\"thread_id\":\"T\"}'\n"
                        "echo '{\"type\":\"item.completed\",\"item\":{\"type\":\"agent_message\",\"text\":\"hello from fake\"}}'\n"
                        "echo '{\"type\":\"turn.completed\",\"usage\":{}}'\n")
            os.chmod(fake, 0o755)
            if sys.platform.startswith("win"):
                self.skipTest("shell script fake not runnable on Windows")
            got = []
            run = agentcli.AgentRun("codex", "hi", "pymol", 42, lambda k, p: got.append((k, p)), exe=fake).start()
            run.wait(30)
            self.assertEqual(run.session_id, "T")
            self.assertEqual(run.final_text, "hello from fake")
            self.assertIn(("done", ""), got)
            self.assertEqual(run.env["MOLMCP_PYMOL_PID"], "42")


if __name__ == "__main__":
    unittest.main()


class TestModelSettings(unittest.TestCase):
    def test_model_and_effort_flags(self):
        argv = agentcli.build_argv("claude", "/x/claude", "hi", "pymol", 1, model="opus", effort="high")
        self.assertEqual(argv[argv.index("--model") + 1], "opus")
        self.assertEqual(argv[argv.index("--effort") + 1], "high")
        argv = agentcli.build_argv("codex", "/x/codex", "hi", "pymol", 1, model="gpt-5-codex", effort="low")
        self.assertEqual(argv[argv.index("-m") + 1], "gpt-5-codex")
        self.assertIn('model_reasoning_effort="low"', argv)
        self.assertEqual(argv[1:3], ["exec", "--json"])
        argv = agentcli.build_argv("codex", "/x/codex", "more", "pymol", 1, session_id="t1", model="o3")
        self.assertEqual(argv[:3], ["/x/codex", "exec", "resume"])
        self.assertEqual(argv[-2:], ["t1", "more"])
        self.assertIn("o3", argv)

    def test_settings_persist(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"MOLMCP_AGENT_SETTINGS": os.path.join(d, "s.json")}):
            self.assertEqual(agentcli.backend_settings("claude"), {"model": "", "effort": ""})
            agentcli.set_backend_settings("claude", model="sonnet")
            agentcli.set_backend_settings("claude", effort="xhigh")
            self.assertEqual(agentcli.backend_settings("claude"), {"model": "sonnet", "effort": "xhigh"})
            agentcli.set_default_backend("codex")
            self.assertEqual(agentcli.load_settings()["default_backend"], "codex")
            with mock.patch.object(agentcli, "available_backends", return_value=["claude"]):
                self.assertEqual(agentcli.default_backend(), "claude")   # codex not installed -> fall back
            with mock.patch.object(agentcli, "available_backends", return_value=[]):
                self.assertEqual(agentcli.default_backend(), "claude")

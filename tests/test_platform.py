"""Platform-independence checks that run on any OS: discovery under simulated platforms, installer config
edits in a temporary HOME, wheel building, launcher argv construction."""
import json
import os
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

from molmcp import install as inst
from molmcp.common import discovery, server_common
from molmcp.pymol_server import server as pymol_server
from molmcp.chimerax_server import server as chimerax_server


class TestDiscovery(unittest.TestCase):
    def test_env_override_wins_on_every_platform(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            exe = f.name
        try:
            for plat in ("win32", "linux", "darwin"):
                with mock.patch.object(sys, "platform", plat), mock.patch.dict(os.environ, {"PYMOL_EXE": exe, "CHIMERAX_EXE": exe}):
                    self.assertEqual(discovery.find_pymol(), exe)
                    self.assertEqual(discovery.find_chimerax(), exe)
        finally:
            os.remove(exe)

    def test_search_does_not_crash_on_foreign_platform(self):
        env = {k: v for k, v in os.environ.items() if k not in ("PYMOL_EXE", "CHIMERAX_EXE")}
        env["PATH"] = ""
        for plat in ("win32", "linux"):
            with mock.patch.object(sys, "platform", plat), mock.patch.dict(os.environ, env, clear=True):
                discovery.find_pymol()      # may be None here; must not raise
                discovery.find_chimerax()

    def test_instance_files_roundtrip(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.dict(os.environ, {"MOLMCP_HOME": home}):
            d = discovery.instances_dir()
            import time
            alive = {"app": "pymol", "pid": os.getpid(), "port": 1, "host": "127.0.0.1", "token": "t", "started": time.time()}
            dead = dict(alive, pid=2 ** 22 - 1, started=1)
            reused = dict(alive, started=2)   # live pid, but the file predates the process: pid was reused
            for name, info in (("pymol-1.json", alive), ("pymol-2.json", dead), ("pymol-3.json", reused)):
                with open(os.path.join(d, name), "w") as f:
                    json.dump(info, f)
            found = discovery.list_instances("pymol")
            self.assertEqual([i["pid"] for i in found], [os.getpid()])
            self.assertFalse(os.path.exists(os.path.join(d, "pymol-2.json")))  # stale file removed
            if discovery.pid_start_time(os.getpid()) is not None:
                self.assertFalse(os.path.exists(os.path.join(d, "pymol-3.json")))  # reused pid: file removed


class TestWindowsChimeraXConsole(unittest.TestCase):
    def test_console_variant_preferred_on_windows_only(self):
        with tempfile.TemporaryDirectory() as d:
            gui = os.path.join(d, "ChimeraX.exe")
            con = os.path.join(d, "ChimeraX-console.exe")
            for f in (gui, con):
                open(f, "w").close()
            with mock.patch.object(sys, "platform", "win32"):
                self.assertEqual(discovery.chimerax_console_exe(gui), con)
                self.assertEqual(discovery.chimerax_console_exe(con), con)
                with mock.patch.object(discovery, "find_chimerax", return_value=gui):
                    self.assertEqual(chimerax_server._launcher("nogui")[0], con)
                    self.assertEqual(chimerax_server._launcher("gui")[0], gui)
            with mock.patch.object(sys, "platform", "linux"):
                self.assertEqual(discovery.chimerax_console_exe(gui), gui)
            os.remove(con)
            with mock.patch.object(sys, "platform", "win32"):
                self.assertEqual(discovery.chimerax_console_exe(gui), gui)


class TestLaunchers(unittest.TestCase):
    def test_pymol_launcher_argv(self):
        with mock.patch.object(discovery, "find_pymol", return_value="/x/pymol"), \
             mock.patch.object(discovery, "find_pymol_python", return_value="/x/python"):
            argv = pymol_server._launcher("gui")
            self.assertEqual(argv[0], "/x/pymol")
            self.assertEqual(argv[1], "-r")
            self.assertTrue(argv[2].endswith("molmcp_pymol_launch.py"))
            self.assertTrue(os.path.exists(argv[2]))
            argv = pymol_server._launcher("headless")
            self.assertEqual(argv[0], "/x/python")
            self.assertTrue(argv[1].endswith("molmcp_pymol_headless.py"))
        with mock.patch.object(discovery, "find_pymol", return_value="/x/pymol"), \
             mock.patch.object(discovery, "find_pymol_python", return_value=None):
            argv, env = pymol_server._launcher("headless")
            self.assertEqual(argv[:2], ["/x/pymol", "-cq"])
            self.assertEqual(env, {"MOLMCP_KEEPALIVE": "1"})

    def test_chimerax_launcher_argv(self):
        with mock.patch.object(discovery, "find_chimerax", return_value="/x/ChimeraX"):
            self.assertEqual(chimerax_server._launcher("gui")[:2], ["/x/ChimeraX", "--script"])
            with mock.patch.object(sys, "platform", "linux"):
                self.assertIn("--offscreen", chimerax_server._launcher("nogui"))
            with mock.patch.object(sys, "platform", "win32"):
                self.assertNotIn("--offscreen", chimerax_server._launcher("nogui"))
            self.assertTrue(os.path.exists(chimerax_server._launcher("gui")[-1]))


class TestInstaller(unittest.TestCase):
    def _home(self):
        return tempfile.TemporaryDirectory()

    def test_server_entry_windows_naming(self):
        with mock.patch.object(sys, "platform", "win32"):
            with mock.patch.object(inst, "venv_bin_dir", return_value="C:\\venv\\Scripts"):
                cmd, args = inst.server_entry("pymol")
                self.assertTrue(cmd == "" or cmd.endswith("pymol-mcp.exe") or args)  # falls back to -m when exe missing
                self.assertEqual(inst.server_command("pymol"), "")  # not present on this machine

    def test_claude_and_codex_registration_roundtrip(self):
        with self._home() as home, mock.patch.dict(os.environ, {"HOME": home, "USERPROFILE": home}):
            with mock.patch.object(os.path, "expanduser", lambda p: p.replace("~", home)):
                codex = inst.codex_config_path()
                os.makedirs(os.path.dirname(codex))
                with open(codex, "w") as f:
                    f.write('model = "x"\n\n[mcp_servers.other]\ncommand = "o"\nargs = []\n')
                inst.register_codex(dry=False)
                def rd(path):
                    with open(path, encoding="utf-8") as f:
                        return f.read()
                text = rd(codex)
                self.assertIn("[mcp_servers.pymol]", text)
                self.assertIn("[mcp_servers.chimerax]", text)
                self.assertIn("[mcp_servers.other]", text)
                inst.register_codex(dry=False)           # idempotent
                self.assertEqual(rd(codex).count("[mcp_servers.pymol]"), 1)
                inst.register_codex(dry=False, remove=True)
                self.assertNotIn("[mcp_servers.pymol]", rd(codex))
                self.assertIn("[mcp_servers.other]", rd(codex))
                try:
                    import tomllib
                    with open(codex, "rb") as f:
                        tomllib.load(f)
                except ImportError:
                    pass
                claude = inst.claude_config_path()
                with open(claude, "w") as f:
                    json.dump({"mcpServers": {"keep": {"command": "k"}}, "other": 1}, f)
                inst.register_claude(dry=False)
                with open(claude) as f:
                    d = json.load(f)
                self.assertEqual(set(d["mcpServers"]), {"keep", "pymol", "chimerax"})
                self.assertEqual(d["other"], 1)
                self.assertTrue(os.path.exists(claude + ".molmcp-backup"))
                inst.register_claude(dry=False, remove=True)
                with open(claude) as f:
                    self.assertEqual(set(json.load(f)["mcpServers"]), {"keep"})

    def test_claude_desktop_keeps_foreign_entry(self):
        with self._home() as home:
            cfg = os.path.join(home, "claude_desktop_config.json")
            with open(cfg, "w") as f:
                json.dump({"mcpServers": {"pymol": {"command": "/old/venv/bin/python", "args": ["/old/pymol_mcp_server.py"]}}}, f)
            with mock.patch.object(inst, "claude_desktop_config_path", return_value=cfg):
                inst.register_claude_desktop(dry=False)
            with open(cfg) as f:
                d = json.load(f)["mcpServers"]
            self.assertEqual(d["pymol"]["args"], ["/old/pymol_mcp_server.py"])   # untouched
            self.assertIn("pymol-molmcp", d)
            self.assertIn("chimerax", d)

    def test_pymolrc_block_replace(self):
        text = "set x, 1\n%s\nrun old\n%s\n" % (inst.MARK_BEGIN, inst.MARK_END)
        new = inst._replace_block(text, "%s\nrun new\n%s\n" % (inst.MARK_BEGIN, inst.MARK_END))
        self.assertIn("run new", new)
        self.assertNotIn("run old", new)
        self.assertTrue(new.startswith("set x, 1\n"))
        self.assertNotIn(inst.MARK_BEGIN, inst._replace_block(new, None))

    def test_pymolrc_path_platforms(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.object(os.path, "expanduser", lambda p: p.replace("~", home)):
            with mock.patch.object(sys, "platform", "win32"):
                self.assertTrue(inst.pymolrc_path().endswith("pymolrc.pml"))
            with mock.patch.object(sys, "platform", "linux"):
                self.assertTrue(inst.pymolrc_path().endswith(".pymolrc"))

    def test_chimerax_wheel_is_valid(self):
        with tempfile.TemporaryDirectory() as d:
            whl = inst.build_chimerax_wheel(d)
            with zipfile.ZipFile(whl) as zf:
                names = zf.namelist()
                self.assertIn("chimerax/agentbridge/__init__.py", names)
                self.assertIn("chimerax/agentbridge/ops.py", names)
                meta = zf.read([n for n in names if n.endswith("METADATA")][0]).decode()
                self.assertIn("ChimeraX :: Bundle :: General :: 1,1 :: chimerax.agentbridge :: :: true", meta)
                self.assertIn("ChimeraX :: Command :: agent start", meta)
                record = zf.read([n for n in names if n.endswith("RECORD")][0]).decode()
                self.assertEqual(len([l for l in record.splitlines() if l]), len(names))
                self.assertIsNone(zf.testzip())


class TestServerCommon(unittest.TestCase):
    def test_renders_dir_env(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"MOLMCP_OUTPUT_DIR": d}):
            self.assertEqual(server_common.renders_dir(), d)

    def test_bridgecore_copies_in_sync(self):
        def read(*parts):
            with open(os.path.join(server_common.INAPP_DIR, *parts), encoding="utf-8") as f:
                return f.read()
        shared = read("shared", "bridgecore.py")
        for sub in (("pymol", "molmcp_pymol_bridge"), ("chimerax", "chimerax_agentbridge", "chimerax", "agentbridge")):
            self.assertEqual(read(*sub, "bridgecore.py"), shared, "bridgecore.py copy out of sync: %s" % "/".join(sub))


if __name__ == "__main__":
    unittest.main()

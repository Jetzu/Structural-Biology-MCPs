"""Installer planning: defaults follow what is installed; flags narrow or extend it."""
import json
import os
import tempfile
import unittest
from unittest import mock

from molmcp import install as inst


def _run(argv, apps_found, clients_found, tmp):
    """Run the installer's main() with fake detection, fake app installs and config files under tmp."""
    calls = []
    paths = {"claude": os.path.join(tmp, "claude.json"), "codex": os.path.join(tmp, "codex", "config.toml"),
             "desktop": os.path.join(tmp, "desktop", "claude_desktop_config.json")}
    with mock.patch.object(inst, "detect_apps", return_value=apps_found), \
         mock.patch.object(inst, "detect_clients", return_value=clients_found), \
         mock.patch.object(inst, "install_pymol", side_effect=lambda dry: calls.append("install_pymol")), \
         mock.patch.object(inst, "install_chimerax", side_effect=lambda dry: calls.append("install_chimerax")), \
         mock.patch.object(inst, "uninstall_pymol", side_effect=lambda dry: calls.append("uninstall_pymol")), \
         mock.patch.object(inst, "uninstall_chimerax", side_effect=lambda dry: calls.append("uninstall_chimerax")), \
         mock.patch.object(inst, "claude_config_path", return_value=paths["claude"]), \
         mock.patch.object(inst, "codex_config_path", return_value=paths["codex"]), \
         mock.patch.object(inst, "_claude_desktop_config_file", return_value=paths["desktop"]), \
         mock.patch.object(inst, "log"):
        rc = inst.main(argv)
    return rc, calls, paths


def _claude_servers(paths):
    if not os.path.exists(paths["claude"]):
        return []
    with open(paths["claude"]) as f:
        return sorted(json.load(f)["mcpServers"])


def _codex_servers(paths):
    if not os.path.exists(paths["codex"]):
        return []
    with open(paths["codex"]) as f:
        text = f.read()
    return sorted(a for a in ("pymol", "chimerax") if "[mcp_servers.%s]" % a in text)


ALL_APPS = {"pymol": "/x/pymol", "chimerax": "/x/ChimeraX"}
ALL_CLIENTS = {"claude": "/x/claude", "codex": "/x/codex", "claude_desktop": None}


class TestDefaultsFollowWhatIsInstalled(unittest.TestCase):
    def test_everything_installed(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, calls, paths = _run([], ALL_APPS, ALL_CLIENTS, tmp)
            self.assertEqual(rc, 0)
            self.assertEqual(calls, ["install_pymol", "install_chimerax"])
            self.assertEqual(_claude_servers(paths), ["chimerax", "pymol"])
            self.assertEqual(_codex_servers(paths), ["chimerax", "pymol"])
            self.assertFalse(os.path.exists(paths["desktop"]))       # Claude Desktop not installed: untouched

    def test_only_pymol_installed(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, calls, paths = _run([], {"pymol": "/x/pymol", "chimerax": None}, ALL_CLIENTS, tmp)
            self.assertEqual(calls, ["install_pymol"])
            self.assertEqual(_claude_servers(paths), ["pymol"])
            self.assertEqual(_codex_servers(paths), ["pymol"])

    def test_only_chimerax_installed(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, calls, paths = _run([], {"pymol": None, "chimerax": "/x/ChimeraX"}, ALL_CLIENTS, tmp)
            self.assertEqual(calls, ["install_chimerax"])
            self.assertEqual(_claude_servers(paths), ["chimerax"])
            self.assertEqual(_codex_servers(paths), ["chimerax"])

    def test_only_claude_code_installed(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, calls, paths = _run([], ALL_APPS, {"claude": "/x/claude", "codex": None, "claude_desktop": None}, tmp)
            self.assertEqual(_claude_servers(paths), ["chimerax", "pymol"])
            self.assertEqual(_codex_servers(paths), [])
            self.assertFalse(os.path.exists(paths["codex"]))

    def test_only_codex_installed(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, calls, paths = _run([], ALL_APPS, {"claude": None, "codex": "/x/codex", "claude_desktop": None}, tmp)
            self.assertEqual(_codex_servers(paths), ["chimerax", "pymol"])
            self.assertFalse(os.path.exists(paths["claude"]))

    def test_claude_desktop_app_without_config_gets_a_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, calls, paths = _run([], ALL_APPS, {"claude": None, "codex": None, "claude_desktop": "Claude Desktop app"}, tmp)
            with open(paths["desktop"]) as f:
                self.assertEqual(sorted(json.load(f)["mcpServers"]), ["chimerax", "pymol"])

    def test_no_viewer_installed(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, calls, paths = _run([], {"pymol": None, "chimerax": None}, ALL_CLIENTS, tmp)
            self.assertEqual(rc, 1)
            self.assertEqual(calls, [])
            self.assertFalse(os.path.exists(paths["claude"]))

    def test_no_client_installed_still_sets_up_viewers(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, calls, paths = _run([], ALL_APPS, {"claude": None, "codex": None, "claude_desktop": None}, tmp)
            self.assertEqual(rc, 0)
            self.assertEqual(calls, ["install_pymol", "install_chimerax"])
            self.assertFalse(os.path.exists(paths["claude"]) or os.path.exists(paths["codex"]))


class TestFlags(unittest.TestCase):
    def test_only_flags_narrow_the_choice(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, calls, paths = _run(["--pymol", "--codex"], ALL_APPS, ALL_CLIENTS, tmp)
            self.assertEqual(calls, ["install_pymol"])
            self.assertEqual(_codex_servers(paths), ["pymol"])
            self.assertFalse(os.path.exists(paths["claude"]))

    def test_named_client_is_set_up_even_if_not_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, calls, paths = _run(["--claude"], ALL_APPS, {"claude": None, "codex": None, "claude_desktop": None}, tmp)
            self.assertEqual(_claude_servers(paths), ["chimerax", "pymol"])

    def test_no_flags_skip_installed_things(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, calls, paths = _run(["--no-chimerax", "--no-claude"], ALL_APPS, ALL_CLIENTS, tmp)
            self.assertEqual(calls, ["install_pymol"])
            self.assertEqual(_codex_servers(paths), ["pymol"])
            self.assertFalse(os.path.exists(paths["claude"]))

    def test_uninstall_one_client_keeps_plugins_and_other_client(self):
        with tempfile.TemporaryDirectory() as tmp:
            _run([], ALL_APPS, ALL_CLIENTS, tmp)
            rc, calls, paths = _run(["--uninstall", "--codex"], ALL_APPS, ALL_CLIENTS, tmp)
            self.assertEqual(calls, [])                       # plugins stay for Claude Code
            self.assertEqual(_codex_servers(paths), [])
            self.assertEqual(_claude_servers(paths), ["chimerax", "pymol"])

    def test_uninstall_one_viewer_removes_it_everywhere(self):
        with tempfile.TemporaryDirectory() as tmp:
            _run([], ALL_APPS, ALL_CLIENTS, tmp)
            rc, calls, paths = _run(["--uninstall", "--chimerax"], ALL_APPS, ALL_CLIENTS, tmp)
            self.assertEqual(calls, ["uninstall_chimerax"])
            self.assertEqual(_claude_servers(paths), ["pymol"])
            self.assertEqual(_codex_servers(paths), ["pymol"])

    def test_uninstall_everything(self):
        with tempfile.TemporaryDirectory() as tmp:
            _run([], ALL_APPS, ALL_CLIENTS, tmp)
            rc, calls, paths = _run(["--uninstall"], ALL_APPS, ALL_CLIENTS, tmp)
            self.assertEqual(calls, ["uninstall_pymol", "uninstall_chimerax"])
            self.assertEqual(_claude_servers(paths), [])
            self.assertEqual(_codex_servers(paths), [])


if __name__ == "__main__":
    unittest.main()

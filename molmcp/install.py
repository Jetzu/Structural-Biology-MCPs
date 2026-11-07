"""molmcp installer: set up the in-app bridges and register the MCP servers.

Run through the repository's ``install.py`` (which creates the virtualenv) or,
inside the virtualenv, ``molmcp-install``.  Works on macOS, Linux and Windows.

Steps (all idempotent; choose with flags, default = everything that applies):
  --pymol            install the PyMOL plugin (auto-starts the bridge in PyMOL)
  --chimerax         build + install the ChimeraX bundle (auto-starts the bridge)
  --claude           register pymol/chimerax servers with Claude Code (user scope)
  --codex            register with Codex CLI (~/.codex/config.toml)
  --claude-desktop   register with Claude Desktop (if its config file exists)
  --uninstall        remove the plugin/bundle and the registrations
  --dry-run          show what would be done
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from typing import List, Optional, Tuple

from molmcp import __version__
from molmcp.common import discovery

HERE = os.path.dirname(os.path.abspath(__file__))
INAPP = os.path.join(HERE, "inapp")
BUNDLE_NAME = "ChimeraX-AgentBridge"
BUNDLE_MODULE = "chimerax.agentbridge"
PLUGIN_NAME = "molmcp_pymol_bridge"
SERVER_NAMES = {"pymol": "pymol-mcp", "chimerax": "chimerax-mcp"}


def log(msg: str):
    print(msg, flush=True)


def venv_bin_dir() -> str:
    return os.path.dirname(os.path.abspath(sys.executable))


def server_command(app: str) -> str:
    name = SERVER_NAMES[app] + (".exe" if sys.platform.startswith("win") else "")
    path = os.path.join(venv_bin_dir(), name)
    if not os.path.exists(path):
        # fall back to running the module with this interpreter
        return ""
    return path


def server_entry(app: str) -> Tuple[str, List[str]]:
    cmd = server_command(app)
    if cmd:
        return cmd, []
    return sys.executable, ["-m", "molmcp.%s_server.server" % app]


# ---------------------------------------------------------------------------
# PyMOL plugin
# ---------------------------------------------------------------------------

PYMOL_INSTALL_SCRIPT = r'''
import os, shutil, sys
SRC = {src!r}
NAME = {name!r}
from pymol import plugins
from pymol.plugins import installation
try:
    plugins.initialize(-2)
except Exception as e:
    print("MOLMCP_WARN plugin init: %s" % e)
plugdir = None
for d in plugins.get_startup_path(True):
    if os.path.isdir(d) and os.access(d, os.W_OK):
        plugdir = d
        break
if plugdir is None:
    plugdir = installation.get_default_user_plugin_path()
    os.makedirs(plugdir, exist_ok=True)
dst = os.path.join(plugdir, NAME)
if os.path.isdir(dst):
    shutil.rmtree(dst)
elif os.path.exists(dst):
    os.remove(dst)
shutil.copytree(SRC, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
if plugdir not in plugins.get_startup_path(True):
    plugins.set_startup_path([plugdir] + plugins.get_startup_path(True), False)
plugins.autoload[NAME] = True
plugins.pref_save()
print("MOLMCP_INSTALLED " + dst)
'''

PYMOL_UNINSTALL_SCRIPT = r'''
import os, shutil
NAME = {name!r}
from pymol import plugins
try:
    plugins.initialize(-2)
except Exception:
    pass
removed = []
for d in list(plugins.get_startup_path()):
    p = os.path.join(d, NAME)
    if os.path.isdir(p):
        shutil.rmtree(p); removed.append(p)
plugins.autoload.pop(NAME, None)
plugins.pref_save()
print("MOLMCP_REMOVED " + ";".join(removed))
'''


def pymolrc_path() -> str:
    home = os.path.expanduser("~")
    for name in (".pymolrc", ".pymolrc.pml", "pymolrc.pml", "pymolrc"):
        p = os.path.join(home, name)
        if os.path.exists(p):
            return p
    return os.path.join(home, ".pymolrc" if not sys.platform.startswith("win") else "pymolrc.pml")


MARK_BEGIN = "# >>> molmcp bridge >>>"
MARK_END = "# <<< molmcp bridge <<<"


def _replace_block(text: str, block: Optional[str]) -> str:
    pat = re.compile(re.escape(MARK_BEGIN) + r".*?" + re.escape(MARK_END) + r"\n?", re.S)
    text = pat.sub("", text)
    if block:
        if text and not text.endswith("\n"):
            text += "\n"
        text += block
    return text


def install_pymol(dry: bool) -> bool:
    exe = discovery.find_pymol()
    src = os.path.join(INAPP, "pymol", PLUGIN_NAME)
    launcher = os.path.join(INAPP, "pymol", "molmcp_pymol_launch.py")
    log("\n== PyMOL plugin ==")
    for shared in ("bridgecore.py", "agentcli.py", "agentchat_ui.py"):
        shutil.copy(os.path.join(INAPP, "shared", shared), os.path.join(src, shared))
    if exe:
        log("PyMOL executable: %s" % exe)
        script = PYMOL_INSTALL_SCRIPT.format(src=src, name=PLUGIN_NAME)
        if dry:
            log("would run headless PyMOL to install the plugin into its user plugin directory")
            return True
        out = _run_pymol_script(exe, script)
        m = re.search(r"MOLMCP_INSTALLED (.+)", out or "")
        if m:
            log("installed plugin: %s" % m.group(1).strip())
            log("PyMOL will start the bridge automatically (Plugin menu: 'Agent Bridge (MCP)'; commands: agent_status, agent_start, agent_stop)")
            return True
        log("headless PyMOL plugin install failed; output was:\n%s" % (out or "(none)"))
    else:
        log("PyMOL executable not found (set PYMOL_EXE to its path).")
    # fallback: pymolrc
    rc = pymolrc_path()
    block = "%s\nrun %s\n%s\n" % (MARK_BEGIN, launcher, MARK_END)
    log("falling back to a 'run' line in %s" % rc)
    if dry:
        return True
    text = open(rc).read() if os.path.exists(rc) else ""
    with open(rc, "w") as f:
        f.write(_replace_block(text, block))
    return True


def uninstall_pymol(dry: bool):
    log("\n== PyMOL plugin (remove) ==")
    exe = discovery.find_pymol()
    if exe and not dry:
        out = _run_pymol_script(exe, PYMOL_UNINSTALL_SCRIPT.format(name=PLUGIN_NAME))
        log(out.strip() or "(no output)")
    rc = pymolrc_path()
    if os.path.exists(rc):
        text = open(rc).read()
        new = _replace_block(text, None)
        if new != text and not dry:
            with open(rc, "w") as f:
                f.write(new)
            log("removed molmcp block from %s" % rc)


def _run_pymol_script(exe: str, script: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".py", prefix="molmcp_pymol_")
    with os.fdopen(fd, "w") as f:
        f.write(script)
    try:
        env = dict(os.environ)
        env["MOLMCP_PYMOL_AUTOSTART"] = "0"
        py = discovery.find_pymol_python(exe)
        if py:
            argv = [py, "-m", "pymol", "-cq", "-k", path]
        else:
            argv = [exe, "-cq", "-k", path]
        r = subprocess.run(argv, capture_output=True, text=True, timeout=300, env=env)
        out = (r.stdout or "") + (r.stderr or "")
        if "MOLMCP_" not in out and py and exe != py:
            # e.g. a Python that imports pymol but cannot run it headless; retry with the executable
            r = subprocess.run([exe, "-cq", "-k", path], capture_output=True, text=True, timeout=300, env=env)
            out = (r.stdout or "") + (r.stderr or "")
        return out
    except Exception as e:
        return "ERROR: %s" % e
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# ChimeraX bundle
# ---------------------------------------------------------------------------

def _wheel_record_line(name: str, data: bytes) -> str:
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode("ascii")
    return "%s,sha256=%s,%d" % (name, digest, len(data))


def build_chimerax_wheel(dist_dir: str) -> str:
    """Create a ChimeraX bundle wheel without any build tooling."""
    root = os.path.join(INAPP, "chimerax", "chimerax_agentbridge")
    pkg_dir = os.path.join(root, "chimerax", "agentbridge")
    # keep the shared bridge core in sync
    for shared in ("bridgecore.py", "agentcli.py", "agentchat_ui.py"):
        shutil.copy(os.path.join(INAPP, "shared", shared), os.path.join(pkg_dir, shared))
        shutil.copy(os.path.join(INAPP, "shared", shared), os.path.join(INAPP, "pymol", PLUGIN_NAME, shared))
    version = __version__
    dist_name = BUNDLE_NAME.replace("-", "_")
    wheel_name = "%s-%s-py3-none-any.whl" % (dist_name, version)
    os.makedirs(dist_dir, exist_ok=True)
    wheel_path = os.path.join(dist_dir, wheel_name)
    dist_info = "%s-%s.dist-info" % (dist_name, version)
    metadata = "\n".join([
        "Metadata-Version: 2.1",
        "Name: %s" % BUNDLE_NAME,
        "Version: %s" % version,
        "Summary: molmcp agent bridge: lets MCP agents (Claude Code, Codex) drive ChimeraX",
        "Home-page: https://github.com/",
        "Author: molmcp",
        "License: MIT",
        "Classifier: Framework :: ChimeraX",
        "Classifier: Intended Audience :: Science/Research",
        "Classifier: Programming Language :: Python :: 3",
        "Classifier: Topic :: Scientific/Engineering :: Visualization",
        "Classifier: ChimeraX :: Bundle :: General :: 1,1 :: %s :: :: true" % BUNDLE_MODULE,
        "Classifier: ChimeraX :: Command :: agent start :: General :: Start the molmcp agent bridge (MCP)",
        "Classifier: ChimeraX :: Command :: agent stop :: General :: Stop the molmcp agent bridge",
        "Classifier: ChimeraX :: Command :: agent status :: General :: Show molmcp agent bridge connection info",
        "Classifier: ChimeraX :: Command :: agent info :: General :: Show molmcp agent bridge connection info",
        "Classifier: ChimeraX :: Command :: agent chat :: General :: Open the Agent Chat panel (Claude Code / Codex)",
        "Classifier: ChimeraX :: Command :: agent name :: General :: Name this ChimeraX window for the agent",
        "Classifier: ChimeraX :: Command :: claude :: General :: Ask Claude Code about this session",
        "Classifier: ChimeraX :: Command :: codex :: General :: Ask Codex about this session",
        "Classifier: ChimeraX :: Tool :: Agent Chat :: General :: Chat with Claude Code or Codex about this ChimeraX session",
        "Classifier: ChimeraX :: Provider :: agent-tab :: toolbar :: tab:Agent :: after:Markers",
        "Classifier: ChimeraX :: Provider :: agent-section :: toolbar :: tab:Agent :: section:\"Claude / Codex\"",
        "Classifier: ChimeraX :: Provider :: agent-chat-button :: toolbar :: tab:Agent :: section:\"Claude / Codex\" :: display_name:\"Agent Chat\" :: icon:agent_chat.png :: description:\"Chat with Claude Code or Codex about this session\"",
        "Requires-Python: >=3.7",
        "Requires-Dist: ChimeraX-Core",
        "",
        "In-app bridge for the molmcp MCP servers (pymol-mcp / chimerax-mcp).",
        "",
    ])
    wheel_meta = "Wheel-Version: 1.0\nGenerator: molmcp\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
    records = []
    with zipfile.ZipFile(wheel_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in sorted(os.listdir(pkg_dir)):
            if not (fn.endswith(".py") or fn.endswith(".png")):
                continue
            with open(os.path.join(pkg_dir, fn), "rb") as f:
                data = f.read()
            arc = "chimerax/agentbridge/" + fn
            zf.writestr(arc, data)
            records.append(_wheel_record_line(arc, data))
        for arc, text in ((dist_info + "/METADATA", metadata), (dist_info + "/WHEEL", wheel_meta),
                          (dist_info + "/top_level.txt", "chimerax\n")):
            zf.writestr(arc, text)
            records.append(_wheel_record_line(arc, text.encode("utf-8")))
        records.append("%s/RECORD,," % dist_info)
        zf.writestr(dist_info + "/RECORD", "\n".join(records) + "\n")
    return wheel_path


CHIMERAX_INSTALL_SCRIPT = r'''
import sys
from chimerax.core.commands import run
wheel = {wheel!r}
try:
    run(session, 'toolshed uninstall "{bundle}"', log=False)
except Exception as e:
    print("MOLMCP_NOTE no previous bundle: %s" % e)
try:
    run(session, 'toolshed install "%s" reinstall true' % wheel, log=False)
    print("MOLMCP_INSTALLED")
except Exception as e:
    print("MOLMCP_FAILED %s" % e)
'''

CHIMERAX_UNINSTALL_SCRIPT = r'''
from chimerax.core.commands import run
try:
    run(session, 'toolshed uninstall "{bundle}"', log=False)
    print("MOLMCP_REMOVED")
except Exception as e:
    print("MOLMCP_FAILED %s" % e)
'''


def _run_chimerax_script(exe: str, script: str, timeout: int = 600) -> str:
    fd, path = tempfile.mkstemp(suffix=".py", prefix="molmcp_cx_")
    with os.fdopen(fd, "w") as f:
        f.write(script)
    try:
        env = dict(os.environ)
        env["MOLMCP_CHIMERAX_AUTOSTART"] = "0"
        r = subprocess.run([discovery.chimerax_console_exe(exe), "--nogui", "--exit", "--silent", "--script", path],
                           capture_output=True, text=True, timeout=timeout, env=env)
        return (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return "ERROR: %s" % e
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def install_chimerax(dry: bool) -> bool:
    log("\n== ChimeraX bundle ==")
    exe = discovery.find_chimerax()
    if not exe:
        log("ChimeraX executable not found (set CHIMERAX_EXE). You can still start the bridge inside ChimeraX with:\n"
            "   open %s" % os.path.join(INAPP, "chimerax", "molmcp_chimerax_launch.py"))
        return False
    log("ChimeraX executable: %s" % exe)
    dist_dir = os.path.join(discovery.molmcp_home(), "build")
    if dry:
        log("would build %s wheel in %s and run 'toolshed install' in ChimeraX" % (BUNDLE_NAME, dist_dir))
        return True
    wheel = build_chimerax_wheel(dist_dir)
    log("built %s" % wheel)
    out = _run_chimerax_script(exe, CHIMERAX_INSTALL_SCRIPT.format(wheel=wheel, bundle=BUNDLE_NAME))
    if "MOLMCP_INSTALLED" in out:
        log("installed bundle %s (ChimeraX starts the bridge automatically; commands: agent status, agent start, agent stop)" % BUNDLE_NAME)
        return True
    log("bundle install failed; ChimeraX output:\n%s" % out.strip())
    return False


def uninstall_chimerax(dry: bool):
    log("\n== ChimeraX bundle (remove) ==")
    exe = discovery.find_chimerax()
    if not exe or dry:
        return
    out = _run_chimerax_script(exe, CHIMERAX_UNINSTALL_SCRIPT.format(bundle=BUNDLE_NAME))
    log(out.strip() or "(no output)")


# ---------------------------------------------------------------------------
# MCP client registration
# ---------------------------------------------------------------------------

def _backup(path: str):
    if os.path.exists(path):
        shutil.copy(path, path + ".molmcp-backup")


def claude_config_path() -> str:
    return os.path.join(os.path.expanduser("~"), ".claude.json")


def register_claude(dry: bool, remove: bool = False):
    log("\n== Claude Code (user scope, %s) ==" % claude_config_path())
    path = claude_config_path()
    data = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            log("cannot parse %s (%s); not touching it" % (path, e))
            return
    servers = data.setdefault("mcpServers", {})
    for app in ("pymol", "chimerax"):
        if remove:
            if app in servers and _is_ours(servers[app]):
                servers.pop(app)
                log("removed %s" % app)
            continue
        cmd, args = server_entry(app)
        servers[app] = {"type": "stdio", "command": cmd, "args": args, "env": {}}
        log("%s -> %s %s" % (app, cmd, " ".join(args)))
    if dry:
        return
    _backup(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    log("saved. In Claude Code run /mcp to see the servers (restart running sessions).")


def _is_ours(entry: dict) -> bool:
    cmd = ((entry or {}).get("command", "") or "").replace("\\", "/")
    base = cmd.rsplit("/", 1)[-1]
    args = " ".join((entry or {}).get("args", []) or [])
    return base in ("pymol-mcp", "chimerax-mcp", "pymol-mcp.exe", "chimerax-mcp.exe") or "molmcp." in args


def codex_config_path() -> str:
    return os.path.join(os.path.expanduser("~"), ".codex", "config.toml")


def _toml_str(s: str) -> str:
    return json.dumps(s)  # valid TOML basic string


def register_codex(dry: bool, remove: bool = False):
    path = codex_config_path()
    log("\n== Codex CLI (%s) ==" % path)
    text = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            text = f.read()
    for app in ("pymol", "chimerax"):
        header = "[mcp_servers.%s]" % app
        pat = re.compile(r"(?ms)^\[mcp_servers\.%s\]\n.*?(?=^\[|\Z)" % re.escape(app))
        if remove:
            if pat.search(text):
                text = pat.sub("", text)
                log("removed %s" % app)
            continue
        cmd, args = server_entry(app)
        block = "%s\ncommand = %s\nargs = [%s]\n\n" % (header, _toml_str(cmd), ", ".join(_toml_str(a) for a in args))
        if pat.search(text):
            text = pat.sub(block, text)
        else:
            if text and not text.endswith("\n"):
                text += "\n"
            if text and not text.endswith("\n\n"):
                text += "\n"
            text += block
        log("%s -> %s %s" % (app, cmd, " ".join(args)))
    if dry:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    _backup(path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    try:
        import tomllib  # py3.11+
        with open(path, "rb") as f:
            tomllib.load(f)
    except ImportError:
        pass
    except Exception as e:
        log("WARNING: %s does not parse as TOML after edit: %s (backup at %s.molmcp-backup)" % (path, e, path))
        return
    log("saved. In Codex run `codex mcp list` to verify.")


def claude_desktop_config_path() -> Optional[str]:
    if sys.platform == "darwin":
        p = os.path.expanduser("~/Library/Application Support/Claude/claude_desktop_config.json")
    elif sys.platform.startswith("win"):
        p = os.path.join(os.environ.get("APPDATA", ""), "Claude", "claude_desktop_config.json")
    else:
        p = os.path.expanduser("~/.config/Claude/claude_desktop_config.json")
    return p if os.path.exists(p) else None


def register_claude_desktop(dry: bool, remove: bool = False):
    path = claude_desktop_config_path()
    if not path:
        return
    log("\n== Claude Desktop (%s) ==" % path)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        log("cannot parse config (%s); skipping" % e)
        return
    servers = data.setdefault("mcpServers", {})
    for app in ("pymol", "chimerax"):
        name = app
        if remove:
            for n in (app, app + "-molmcp"):
                if n in servers and _is_ours(servers[n]):
                    servers.pop(n)
                    log("removed %s" % n)
            continue
        if name in servers and not _is_ours(servers[name]):
            name = app + "-molmcp"   # keep the user's existing server untouched
        cmd, args = server_entry(app)
        servers[name] = {"command": cmd, "args": args}
        log("%s -> %s %s" % (name, cmd, " ".join(args)))
    if dry:
        return
    _backup(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    log("saved (restart Claude Desktop).")


# ---------------------------------------------------------------------------

def check():
    log("== molmcp %s ==" % __version__)
    log("python:   %s" % sys.executable)
    log("pymol:    %s" % (discovery.find_pymol() or "NOT FOUND (set PYMOL_EXE)"))
    log("chimerax: %s" % (discovery.find_chimerax() or "NOT FOUND (set CHIMERAX_EXE)"))
    for app in ("pymol", "chimerax"):
        cmd, args = server_entry(app)
        log("%-9s server: %s %s" % (app, cmd, " ".join(args)))
    log("home:     %s" % discovery.molmcp_home())


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pymol", action="store_true")
    ap.add_argument("--chimerax", action="store_true")
    ap.add_argument("--claude", action="store_true")
    ap.add_argument("--codex", action="store_true")
    ap.add_argument("--claude-desktop", action="store_true")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check", action="store_true", help="only report what was found")
    a = ap.parse_args(argv)
    check()
    if a.check:
        return 0
    chosen = any([a.pymol, a.chimerax, a.claude, a.codex, a.claude_desktop])
    do = lambda flag: (flag or not chosen)  # noqa: E731
    dry = a.dry_run
    if a.uninstall:
        if do(a.pymol):
            uninstall_pymol(dry)
        if do(a.chimerax):
            uninstall_chimerax(dry)
        if do(a.claude):
            register_claude(dry, remove=True)
        if do(a.codex):
            register_codex(dry, remove=True)
        if do(a.claude_desktop):
            register_claude_desktop(dry, remove=True)
        return 0
    if do(a.pymol):
        install_pymol(dry)
    if do(a.chimerax):
        install_chimerax(dry)
    if do(a.claude):
        register_claude(dry)
    if do(a.codex):
        register_codex(dry)
    if do(a.claude_desktop):
        register_claude_desktop(dry)
    log("\nDone. Restart PyMOL / ChimeraX so their bridges start, then use the `status` tool from Claude Code or Codex.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Bootstrap installer for molmcp (PyMOL + ChimeraX MCP servers).

    python install.py            # create .venv, install molmcp, set up PyMOL/ChimeraX, register with Claude Code & Codex
    python install.py --check    # only report what is found
    python install.py --help     # all options

Works on macOS, Linux and Windows with Python 3.10+ (uses `uv` when available).
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VENV = os.path.join(HERE, ".venv")
WIN = sys.platform.startswith("win")
VENV_PY = os.path.join(VENV, "Scripts" if WIN else "bin", "python.exe" if WIN else "python")


def run(cmd, **kw):
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=True, **kw)


def ensure_venv():
    if os.path.exists(VENV_PY):
        return
    uv = shutil.which("uv")
    if uv:
        run([uv, "venv", "--python", ">=3.10", VENV])
        return
    if sys.version_info < (3, 10):
        sys.exit("Python 3.10+ is required (found %s). Install a newer Python or `pip install uv` and rerun." % sys.version.split()[0])
    run([sys.executable, "-m", "venv", VENV])


def install_package():
    uv = shutil.which("uv")
    if uv:
        run([uv, "pip", "install", "--python", VENV_PY, "-e", HERE])
    else:
        run([VENV_PY, "-m", "pip", "install", "--upgrade", "pip", "-q"])
        run([VENV_PY, "-m", "pip", "install", "-e", HERE])


def main():
    args = sys.argv[1:]
    if "--help" in args or "-h" in args:
        print(__doc__)
        subprocess.run([VENV_PY, "-m", "molmcp.install", "--help"]) if os.path.exists(VENV_PY) else None
        return
    ensure_venv()
    install_package()
    sys.exit(subprocess.call([VENV_PY, "-m", "molmcp.install"] + args))


if __name__ == "__main__":
    main()

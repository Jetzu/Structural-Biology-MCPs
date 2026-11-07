#!/usr/bin/env bash
# Inside the Wine container: Windows Python runs the installer (venv + plugin + Claude/Codex config on Windows
# paths) and the MCP end-to-end test with a headless Windows PyMOL (library mode).
set -u
cd /work/mol-mcp
WPY='C:\Py311\python.exe'
WREPO="Z:$(pwd | sed 's|/|\\|g')"
echo "== windows python: $(wine "$WPY" -c 'import sys,platform; print(sys.version.split()[0], sys.platform, platform.system())' 2>/dev/null)"
PYMOL_SCRIPTS_EXE='C:\Py311\Scripts\pymol.exe'
if wine cmd /c "if exist $PYMOL_SCRIPTS_EXE echo yes" 2>/dev/null | grep -q yes; then export PYMOL_EXE="$PYMOL_SCRIPTS_EXE"; echo "== pymol.exe found at $PYMOL_EXE"; else echo "== no pymol.exe console script; headless path uses PYMOL_PYTHON"; fi
echo "== 1. bootstrap installer (python install.py) on win32"
rm -rf .venv
wine "$WPY" install.py --pymol --claude --codex 2>&1 | tr -d '\r' | grep -vE "^\s*$" | tail -14
echo "-- venv scripts:"; ls .venv/Scripts 2>/dev/null | grep -iE "pymol-mcp|chimerax-mcp|python" | head -5
WUSER="$(wine cmd /c 'echo %USERPROFILE%' 2>/dev/null | tr -d '\r')"; echo "-- windows user profile: $WUSER"
UNIXUSER="$(winepath -u "$WUSER" 2>/dev/null)"
echo "-- claude.json servers:"; wine "$WPY" -c "import json,os; d=json.load(open(os.path.expanduser('~/.claude.json'))); print({k:v['command'] for k,v in d['mcpServers'].items()})" 2>/dev/null | tr -d '\r'
echo "-- codex toml:"; grep -A2 "mcp_servers.pymol" "$UNIXUSER/.codex/config.toml" 2>/dev/null | tr -d '\r'
echo "-- pymol plugin dir (%APPDATA%\\pymol\\startup):"; ls "$UNIXUSER/AppData/Roaming/pymol/startup" 2>/dev/null; cat "$UNIXUSER/.pymolpluginsrc.py" 2>/dev/null | grep -E "startup_path|molmcp" | tr -d '\r'
echo "== 2. unit tests under Windows Python"
wine .venv/Scripts/python.exe -m unittest discover -s tests -p "test_*.py" 2>&1 | tr -d '\r' | grep -vE "^\s*$|rosetta error" | tail -12
echo "== 3. MCP e2e, headless PyMOL (library mode) launched by the server on win32"
MOLMCP_PYMOL_LAUNCH_MODE=headless wine .venv/Scripts/python.exe -u tests/e2e_mcp_client.py pymol --launch 2>&1 | tr -d '\r' | grep -vE "^\s+\"(rgb|hex|px|frac|ascii)\"|^\s+[0-9.,-]+$|^\s+\],?$|^\s+\"[^\"]*\",?$|rosetta error" | tail -80
echo "== 4. quit"
wine .venv/Scripts/python.exe - <<'PY' 2>&1 | tr -d '\r' | tail -2
import asyncio, os, sys
sys.path.insert(0, "tests")
from e2e_mcp_client import stdio_client, StdioServerParameters, ClientSession, text_of
async def q():
    p = StdioServerParameters(command=os.path.abspath(".venv/Scripts/pymol-mcp.exe"), args=[], env=dict(os.environ))
    async with stdio_client(p) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize(); print("quit:", text_of(await s.call_tool("quit_pymol", {}))[:60].replace("\n", " "))
asyncio.run(q())
PY

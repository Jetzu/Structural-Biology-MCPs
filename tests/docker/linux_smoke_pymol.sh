#!/usr/bin/env bash
# Runs inside the Linux container: installer + headless PyMOL bridge + MCP e2e (headless launch).
set -u
cd "$(dirname "$0")/../.."
echo "== platform: $(uname -sm), python: $(.venv/bin/python --version), pymol: $(which pymol)"
echo "== 1. installer --check / --pymol / --claude / --codex (Linux paths)"
.venv/bin/python -m molmcp.install --pymol --claude --codex 2>&1 | grep -vE "^$" | tail -12
echo "-- plugin dir:"; ls ~/.pymol/startup/ 2>/dev/null; echo "-- pluginsrc:"; cat ~/.pymolpluginsrc.py 2>/dev/null | head -8
echo "-- claude.json:"; python3 -c "import json; print(json.load(open('/root/.claude.json'))['mcpServers'].keys())"
echo "-- codex toml:"; grep -A2 "mcp_servers.pymol" ~/.codex/config.toml
echo "== 2. unit tests"
.venv/bin/python -m unittest discover -s tests -p "test_*.py" 2>&1 | tail -1
echo "== 3. MCP e2e with headless launch (PyMOL as a library in the conda python)"
MOLMCP_PYMOL_LAUNCH_MODE=headless .venv/bin/python tests/e2e_mcp_client.py pymol --launch 2>&1 | python3 -c "
import sys
for line in sys.stdin.read().splitlines():
    if line.startswith('server:'): continue
    if line.startswith(' ' * 2) and not any(k in line for k in ('\"summary\"','\"error\"','\"all_ok\"','\"pid\"','\"mode\"','\"gui\"')): continue
    print(line[:160])
" | head -400
echo "== 4. quit"
.venv/bin/python - <<'PY'
import asyncio, os, sys
sys.path.insert(0, "tests")
from e2e_mcp_client import stdio_client, StdioServerParameters, ClientSession, text_of
async def q():
    p = StdioServerParameters(command=os.path.abspath(".venv/bin/pymol-mcp"), args=[], env=dict(os.environ))
    async with stdio_client(p) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize(); print("quit:", text_of(await s.call_tool("quit_pymol", {"confirm": True}))[:60].replace("\n", " "))
asyncio.run(q())
PY
sleep 2; echo "pymol processes left: $(ps aux | grep -c "[m]olmcp_pymol_headless" || true)"

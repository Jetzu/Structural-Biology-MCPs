#!/usr/bin/env bash
# Runs inside the Linux container: bundle install + headless ChimeraX bridge (offscreen rendering) + MCP e2e.
set -u
cd "$(dirname "$0")/../.."
echo "== platform: $(uname -sm), chimerax: $(which ChimeraX chimerax 2>/dev/null | head -1)"
echo "== 1. installer --chimerax --claude --codex"
.venv/bin/python -m molmcp.install --chimerax --claude --codex 2>&1 | grep -vE "^$" | tail -8
echo "== 2. MCP e2e with nogui/offscreen launch"
MOLMCP_CHIMERAX_LAUNCH_MODE=nogui .venv/bin/python tests/e2e_mcp_client.py chimerax --launch 2>&1 | python3 -c "
import sys
for line in sys.stdin.read().splitlines():
    if line.startswith('server:'): continue
    if line.startswith(' ' * 2) and not any(k in line for k in ('\"summary\"','\"error\"','\"all_ok\"','\"pid\"','\"mode\"','\"gui\"')): continue
    print(line[:160])
" | head -400
echo "== 3. quit"
.venv/bin/python - <<'PY'
import asyncio, os, sys
sys.path.insert(0, "tests")
from e2e_mcp_client import stdio_client, StdioServerParameters, ClientSession, text_of
async def q():
    p = StdioServerParameters(command=os.path.abspath(".venv/bin/chimerax-mcp"), args=[], env=dict(os.environ))
    async with stdio_client(p) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize(); print("quit:", text_of(await s.call_tool("quit_chimerax", {}))[:60].replace("\n", " "))
asyncio.run(q())
PY

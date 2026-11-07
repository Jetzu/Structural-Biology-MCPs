"""QA helper: drive the real MCP servers from the command line, optionally against an isolated headless PyMOL.

    python tests/qa_client.py start pymol            # headless PyMOL under $MOLMCP_HOME (isolated per agent)
    python tests/qa_client.py call pymol run '{"commands": ["fragment ala"]}'
    python tests/qa_client.py call chimerax scene '{}'
    python tests/qa_client.py tools pymol
    python tests/qa_client.py stop pymol

Each `call` spawns a fresh pymol-mcp / chimerax-mcp server process (stdio MCP), connects it to the running
bridge found under $MOLMCP_HOME (default ~/.molmcp), calls one tool and prints the JSON/text result.
Set MOLMCP_HOME to a private directory to get your own PyMOL instance; ChimeraX GUI windows are shared.
"""
import asyncio
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
VENV_BIN = os.path.join(REPO, ".venv", "Scripts" if sys.platform.startswith("win") else "bin")
sys.path.insert(0, REPO)


def _server_cmd(app):
    exe = os.path.join(VENV_BIN, app + "-mcp" + (".exe" if sys.platform.startswith("win") else ""))
    return exe


def _text(result):
    parts = []
    for c in getattr(result, "content", []) or []:
        t = getattr(c, "text", None)
        if t is not None:
            parts.append(t)
        elif getattr(c, "data", None) is not None:
            parts.append("<image %d b64 chars>" % len(c.data))
    return "\n".join(parts)


async def _call(app, tool, args):
    from mcp.client.stdio import stdio_client, StdioServerParameters
    from mcp.client.session import ClientSession
    params = StdioServerParameters(command=_server_cmd(app), args=[], env=dict(os.environ))
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            if tool == "__tools__":
                tl = await s.list_tools()
                return "\n".join("%s: %s" % (t.name, (t.description or "").strip().splitlines()[0][:110]) for t in tl.tools)
            res = await s.call_tool(tool, args)
            return _text(res)


def start_pymol():
    from molmcp.common import discovery
    py = discovery.find_pymol_python()
    if not py:
        sys.exit("no Python with pymol found (set PYMOL_PYTHON)")
    env = dict(os.environ)
    env.setdefault("MOLMCP_HOME", os.path.join(os.path.expanduser("~"), ".molmcp"))
    known = {i["pid"] for i in discovery.list_instances("pymol")}
    subprocess.Popen([py, os.path.join(REPO, "molmcp", "inapp", "pymol", "molmcp_pymol_headless.py")], env=env,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    inst = discovery.wait_for_instance("pymol", timeout=90, not_pids=known)
    print(json.dumps({"ok": inst is not None, "pid": inst and inst.get("pid"), "home": env["MOLMCP_HOME"]}))


def stop(app):
    print(asyncio.run(_call(app, "quit_" + app, {"confirm": True})))


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    verb, app = sys.argv[1], sys.argv[2]
    if verb == "start" and app == "pymol":
        return start_pymol()
    if verb == "stop":
        return stop(app)
    if verb == "tools":
        return print(asyncio.run(_call(app, "__tools__", {})))
    if verb == "call":
        tool = sys.argv[3]
        args = json.loads(sys.argv[4]) if len(sys.argv) > 4 else {}
        t0 = time.time()
        out = asyncio.run(_call(app, tool, args))
        print(out)
        print("[%s %s: %.1fs]" % (app, tool, time.time() - t0), file=sys.stderr)
        return
    print(__doc__)
    sys.exit(2)


if __name__ == "__main__":
    main()

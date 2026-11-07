"""End-to-end check: talk to pymol-mcp / chimerax-mcp over stdio with the official MCP client.

    python tests/e2e_mcp_client.py pymol|chimerax [--launch]
"""
import asyncio
import json
import os
import sys
import time

try:
    from mcp.client.stdio import stdio_client, StdioServerParameters
    from mcp.client.session import ClientSession
except ImportError:  # older layouts
    from mcp import ClientSession, StdioServerParameters  # type: ignore
    from mcp.client.stdio import stdio_client  # type: ignore


def text_of(result):
    parts = []
    for c in getattr(result, "content", []) or []:
        t = getattr(c, "text", None)
        if t is not None:
            parts.append(t)
        elif getattr(c, "data", None) is not None:
            parts.append("<image %d b64 chars>" % len(c.data))
    return "\n".join(parts)


async def main(app, launch=False):
    here = os.path.dirname(os.path.abspath(__file__))
    win = sys.platform.startswith("win")
    exe = os.path.join(here, "..", ".venv", "Scripts" if win else "bin", app + "-mcp" + (".exe" if win else ""))
    params = StdioServerParameters(command=os.path.abspath(exe), args=[], env=dict(os.environ))
    errlog = open(os.environ["MOLMCP_E2E_ERRLOG"], "w") if os.environ.get("MOLMCP_E2E_ERRLOG") else sys.stderr
    async with stdio_client(params, errlog=errlog) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print("server:", init.serverInfo.name if hasattr(init, "serverInfo") else init)
            tools = await session.list_tools()
            print("tools:", [t.name for t in tools.tools])

            async def call(name, **args):
                t0 = time.time()
                r = await session.call_tool(name, args)
                txt = text_of(r)
                print("\n### %s %s  (%.0f ms, %d chars)" % (name, json.dumps(args)[:80], (time.time() - t0) * 1000, len(txt)))
                return txt

            st = await call("status")
            print(st[:600])
            if launch and '"connected": false' in st:
                mode = os.environ.get("MOLMCP_%s_LAUNCH_MODE" % app.upper(), "gui")
                print((await call("launch", mode=mode))[:300])
            if app == "pymol":
                print((await call("run", commands=["delete all", "fetch 1ubq, async=0", "show cartoon", "color marine", "orient"]))[:900])
                print((await call("scene"))[:700])
                r = await call("render", width=640, height=480)
                d = json.loads(r); print(d["path"]); print(d["analysis"]["summary"]); print("\n".join(d["analysis"]["ascii"][6:12]))
                print((await call("run", commands=["turn y, 90", "zoom 1ubq, -10"]))[:400])
                r2 = await call("render", width=640, height=480); d2 = json.loads(r2); print(d2["analysis"]["summary"])
                print((await call("compare_renders"))[:300])
                print((await call("layout", by="chain", occlusion=True))[:900])
                print((await call("events"))[:600])
                print((await call("selection_info", selection="resi 1-5"))[:300])
                print((await call("help", command="orient"))[:200])
            else:
                print((await call("run", commands=["close", "open 1ubq", "cartoon", "hide atoms", "color bychain", "view"]))[:900])
                print((await call("scene"))[:700])
                r = await call("render", width=640, height=480, supersample=1)
                d = json.loads(r); print(d["path"]); print(d["analysis"]["summary"]); print("\n".join(d["analysis"]["ascii"][6:12]))
                print((await call("run", commands=["turn y 90", "zoom 0.7"]))[:400])
                r2 = await call("render", width=640, height=480, supersample=1); d2 = json.loads(r2); print(d2["analysis"]["summary"])
                print((await call("compare_renders"))[:300])
                print((await call("layout", by="chain", occlusion=True))[:900])
                print((await call("events"))[:600])
                print((await call("selection_info", spec="#1/A:1-5"))[:300])
                print((await call("help", command="cartoon"))[:200])
            r = await call("render", width=320, height=240, return_image=True)
            print(r[-120:])


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], "--launch" in sys.argv))

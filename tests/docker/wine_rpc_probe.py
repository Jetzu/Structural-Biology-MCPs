"""Raw JSON-RPC probe for the stdio MCP server (run with the venv's Python): initialize -> initialized -> tools/list.
Prints the server's raw stdout lines and its stderr so crashes are visible."""
import json, os, subprocess, sys, threading, time

exe = sys.argv[1] if len(sys.argv) > 1 else os.path.join(".venv", "Scripts" if sys.platform.startswith("win") else "bin",
                                                          "pymol-mcp" + (".exe" if sys.platform.startswith("win") else ""))
p = subprocess.Popen([exe], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
err_lines = []
threading.Thread(target=lambda: err_lines.extend(l.rstrip() for l in p.stderr), daemon=True).start()


def send(obj):
    p.stdin.write(json.dumps(obj) + "\n")
    p.stdin.flush()


def recv(timeout=60):
    out = []
    t0 = time.time()
    while time.time() - t0 < timeout:
        line = p.stdout.readline()
        if not line:
            if p.poll() is not None:
                return out, "EXITED rc=%s" % p.returncode
            time.sleep(0.05)
            continue
        out.append(line.rstrip())
        return out, "ok"
    return out, "timeout"


send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                                                                   "clientInfo": {"name": "probe", "version": "0"}}})
lines, st = recv(); print("initialize ->", st, (lines[0][:160] if lines else ""), flush=True)
send({"jsonrpc": "2.0", "method": "notifications/initialized"})
time.sleep(0.5)
send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
lines, st = recv(90); print("tools/list ->", st, ("%d chars" % len(lines[0]) if lines else ""), flush=True)
if lines and st == "ok":
    try:
        d = json.loads(lines[0]); print("tools:", [t["name"] for t in d["result"]["tools"]][:25], flush=True)
    except Exception as e:
        print("parse error:", e, lines[0][:300], flush=True)
_id = [3]


def call(name, args, timeout=300):
    _id[0] += 1
    send({"jsonrpc": "2.0", "id": _id[0], "method": "tools/call", "params": {"name": name, "arguments": args}})
    lines, st = recv(timeout)
    if st != "ok" or not lines:
        print("tools/call %s -> %s" % (name, st), flush=True)
        return None
    try:
        d = json.loads(lines[0])
        text = "".join(c.get("text", "") for c in d["result"]["content"] if c.get("type") == "text")
        try:
            return json.loads(text)
        except Exception:
            return text
    except Exception as e:
        print("tools/call %s -> parse error %s: %s" % (name, e, lines[0][:200]), flush=True)
        return None


r = call("status", {}); print("status -> connected=%s executable=%s" % (r.get("connected"), r.get("executable")), flush=True)
mode = os.environ.get("MOLMCP_PYMOL_LAUNCH_MODE", "headless")
r = call("launch", {"mode": mode}); print("launch(%s) -> %s" % (mode, json.dumps(r)[:200]), flush=True)
r = call("run", {"commands": ["fragment ala", "show sticks", "fetch 1ubq, async=0", "show cartoon", "color marine", "orient"]})
print("run -> all_ok=%s changes=%s" % (r.get("all_ok"), json.dumps(r.get("changes"))[:160]), flush=True)
r = call("scene", {}); print("scene -> objects=%s viewport=%s" % ([o["name"] for o in r.get("objects", [])], r.get("viewport")), flush=True)
r = call("render", {"width": 320, "height": 240}); a = (r or {}).get("analysis", {})
print("render -> path=%s\n          %s" % (r.get("path"), a.get("summary")), flush=True)
r = call("run", {"commands": ["turn y, 90"]}); r = call("render", {"width": 320, "height": 240}); print("render2 ->", (r or {}).get("analysis", {}).get("summary"), flush=True)
r = call("compare_renders", {}); print("compare ->", (r or {}).get("summary"), flush=True)
r = call("layout", {"by": "object", "occlusion": True}); print("layout ->", (r or {}).get("layout", {}).get("summary"), "occlusion:", json.dumps((r or {}).get("occlusion"))[:160], flush=True)
r = call("events", {}); print("events -> seq=%s kinds=%s" % ((r or {}).get("seq"), [e["kind"] for e in (r or {}).get("events", [])][-6:]), flush=True)
r = call("quit_pymol", {"confirm": True}); print("quit ->", json.dumps(r)[:120], flush=True)
time.sleep(1)
print("server alive:", p.poll() is None, flush=True)
print("--- server stderr (tail):"); print("\n".join(err_lines[-25:]), flush=True)
try:
    p.kill()
except Exception:
    pass

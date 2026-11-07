#!/usr/bin/env bash
# Diagnostic: headless ChimeraX launch (bundle autostart + --script) and step-by-step bridge probes.
set -u
cd "$(dirname "$0")/../.."
.venv/bin/python -m molmcp.install --chimerax 2>&1 | grep -E "installed|failed"
rm -f "$MOLMCP_HOME"/instances/chimerax-*.json
echo "== launching ChimeraX --nogui --offscreen --script (log -> /tmp/cx.log)"
( ChimeraX --nogui --offscreen --script "$PWD/molmcp/inapp/chimerax/molmcp_chimerax_launch.py" > /tmp/cx.log 2>&1 & )
for i in $(seq 1 120); do ls "$MOLMCP_HOME"/instances/chimerax-*.json >/dev/null 2>&1 && break; sleep 0.5; done
echo "== instance files: $(ls "$MOLMCP_HOME"/instances/ 2>/dev/null)"
.venv/bin/python -u - <<'PY'
import time, json, sys
from molmcp.common.bridge_client import BridgeClient, BridgeError, NotConnected
c = BridgeClient("chimerax", default_timeout=40)
try:
    info = c.connect(); print("connected pid", info["pid"], "port", info["port"], flush=True)
except Exception as e:
    print("CONNECT FAILED:", e, flush=True); sys.exit(1)
for op, args in [("ping", {}), ("log", {"n": 6}), ("run", {"commands": ["version"]}), ("scene", {}), ("render", {"width": 160, "height": 120, "supersample": 1})]:
    t = time.time()
    try:
        r = c.call(op, **args)
        s = json.dumps(r)[:300]
        print("OK  %-7s %5.0f ms  %s" % (op, (time.time()-t)*1000, s if op != "render" else "png %d chars" % len(r.get("png",""))), flush=True)
    except (BridgeError, NotConnected) as e:
        print("ERR %-7s %5.0f ms  %s" % (op, (time.time()-t)*1000, str(e)[:300]), flush=True)
        if getattr(e, "traceback_text", None): print(e.traceback_text[-800:], flush=True)
try:
    print("quit:", c.call("quit", timeout=10), flush=True)
except Exception as e:
    print("quit err:", e, flush=True)
PY
sleep 3
echo "== ChimeraX log tail:"; tail -25 /tmp/cx.log

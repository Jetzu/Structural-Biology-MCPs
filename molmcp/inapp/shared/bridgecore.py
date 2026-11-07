"""In-application bridge core shared by the PyMOL plugin and the ChimeraX bundle.

Pure standard library so it runs inside any bundled Python (3.7+).  The
application-specific module supplies a *dispatcher* that executes an operation
on the right thread and returns a JSON-serialisable result.

Wire protocol (localhost only):

    GET  /ping                      -> {"ok": true, "app": ..., "pid": ..., "version": ...}
    POST /call   {"op": str, "args": {...}}
         header  Authorization: Bearer <token>
         ->      {"ok": true, "result": ...}  |  {"ok": false, "error": str, "traceback": str}

Every bridge writes a discovery file ``<home>/instances/<app>-<pid>.json``
holding host, port and token so that the MCP server can find it without any
configuration.  ``<home>`` is ``$MOLMCP_HOME`` or ``~/.molmcp``.
"""
from __future__ import annotations

import base64
import io
import json
import os
import secrets
import socket
import sys
import threading
import time
import traceback
from collections import deque
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

BRIDGE_PROTOCOL_VERSION = 1


def molmcp_home() -> str:
    home = os.environ.get("MOLMCP_HOME")
    if not home:
        home = os.path.join(os.path.expanduser("~"), ".molmcp")
    return home


def instances_dir() -> str:
    d = os.path.join(molmcp_home(), "instances")
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        pass
    return d


def json_safe(obj, _depth=0):
    """Convert numpy scalars/arrays, bytes, sets, tuples into JSON-friendly types."""
    if _depth > 40:
        return str(obj)
    if obj is None or isinstance(obj, (bool, int, float, str)):
        if isinstance(obj, float) and (obj != obj or obj in (float("inf"), float("-inf"))):
            return None
        return obj
    if isinstance(obj, (bytes, bytearray)):
        return base64.b64encode(bytes(obj)).decode("ascii")
    if isinstance(obj, dict):
        return {str(k): json_safe(v, _depth + 1) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset, deque)):
        return [json_safe(v, _depth + 1) for v in obj]
    # numpy without importing numpy
    tolist = getattr(obj, "tolist", None)
    if callable(tolist):
        try:
            return json_safe(tolist(), _depth + 1)
        except Exception:
            pass
    item = getattr(obj, "item", None)
    if callable(item):
        try:
            return json_safe(item(), _depth + 1)
        except Exception:
            pass
    return str(obj)


def png_bytes(pil_image) -> bytes:
    buf = io.BytesIO()
    pil_image.save(buf, format="PNG")
    return buf.getvalue()


class EventLog:
    """Ring buffer of timestamped events with monotonically increasing ids."""

    def __init__(self, maxlen: int = 2000):
        self._events = deque(maxlen=maxlen)
        self._seq = 0
        self._lock = threading.Lock()

    def add(self, kind: str, **data) -> int:
        with self._lock:
            self._seq += 1
            ev = {"seq": self._seq, "t": time.time(), "kind": kind}
            ev.update(data)
            self._events.append(ev)
            return self._seq

    @property
    def seq(self) -> int:
        return self._seq

    def since(self, seq: int, limit: int = 500, kinds=None):
        with self._lock:
            out = [e for e in self._events if e["seq"] > seq and (not kinds or e["kind"] in kinds)]
        return out[-limit:]


class Tee:
    """File-like object that writes to the wrapped stream and records text."""

    def __init__(self, stream):
        self._stream = stream
        self._buf = []
        self.lock = threading.Lock()

    def write(self, s):
        with self.lock:
            self._buf.append(s)
        try:
            if self._stream is not None:
                self._stream.write(s)
        except Exception:
            pass

    def flush(self):
        try:
            if self._stream is not None:
                self._stream.flush()
        except Exception:
            pass

    def getvalue(self) -> str:
        with self.lock:
            return "".join(self._buf)

    def __getattr__(self, name):
        return getattr(self._stream, name)


class _ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "molmcp-bridge/1"

    def log_message(self, fmt, *args):  # silence default stderr logging
        pass

    def _send(self, code: int, payload: dict):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self) -> bool:
        token = self.server.bridge.token
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer ") and secrets.compare_digest(auth[7:].strip(), token):
            return True
        x = self.headers.get("X-MolMCP-Token", "")
        return bool(x) and secrets.compare_digest(x.strip(), token)

    def do_GET(self):
        bridge = self.server.bridge
        if self.path.split("?")[0] == "/ping":
            self._send(200, {"ok": True, "app": bridge.app, "pid": os.getpid(),
                             "version": bridge.version, "protocol": BRIDGE_PROTOCOL_VERSION,
                             "uptime_s": round(time.time() - bridge.started, 1)})
            return
        self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        bridge = self.server.bridge
        if self.path.split("?")[0] != "/call":
            self._send(404, {"ok": False, "error": "not found"})
            return
        if not self._authorized():
            self._send(401, {"ok": False, "error": "bad or missing token"})
            return
        try:
            n = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            op = body.get("op")
            args = body.get("args") or {}
            if not isinstance(op, str):
                raise ValueError("'op' must be a string")
        except Exception as e:
            self._send(400, {"ok": False, "error": "bad request: %s" % e})
            return
        t0 = time.time()
        try:
            result = bridge.dispatch(op, args)
            payload = {"ok": True, "result": json_safe(result), "ms": round((time.time() - t0) * 1000, 1)}
            self._send(200, payload)
        except Exception as e:
            self._send(200, {"ok": False, "error": "%s: %s" % (type(e).__name__, e),
                             "traceback": traceback.format_exc(),
                             "ms": round((time.time() - t0) * 1000, 1)})


class Bridge:
    """HTTP bridge living inside the host application."""

    def __init__(self, app: str, version: str, dispatcher, info=None, host: str = "127.0.0.1",
                 port=None, log=None):
        self.app = app
        self.version = version
        self._dispatcher = dispatcher
        self._info = info or (lambda: {})
        self.host = host
        self.port = port
        self.token = secrets.token_urlsafe(24)
        self.started = time.time()
        self.events = EventLog()
        self._server = None
        self._thread = None
        self._log = log or (lambda msg: None)
        self.instance_file = None

    # -- lifecycle -------------------------------------------------------
    @property
    def running(self) -> bool:
        return self._server is not None

    def start(self):
        if self._server is not None:
            return self.host, self._server.server_address[1]
        port = self.port
        if port is None:
            env = os.environ.get("MOLMCP_%s_PORT" % self.app.upper())
            port = int(env) if env else 0
        server = None
        last_err = None
        for candidate in ([port] if port == 0 else [port] + list(range(port + 1, port + 20))):
            try:
                server = _ThreadingHTTPServer((self.host, candidate), _Handler)
                break
            except OSError as e:
                last_err = e
        if server is None:
            raise RuntimeError("could not bind bridge port: %s" % last_err)
        server.bridge = self
        self._server = server
        self._thread = threading.Thread(target=server.serve_forever, name="molmcp-bridge", daemon=True)
        self._thread.start()
        self.port = server.server_address[1]
        self._write_instance_file()
        self.events.add("bridge_started", port=self.port)
        self._log("molmcp bridge for %s listening on http://%s:%d (pid %d)" % (self.app, self.host, self.port, os.getpid()))
        return self.host, self.port

    def stop(self):
        if self._server is None:
            return
        srv = self._server
        self._server = None
        try:
            srv.shutdown()
            srv.server_close()
        except Exception:
            pass
        self._remove_instance_file()
        self._log("molmcp bridge for %s stopped" % self.app)

    def dispatch(self, op: str, args: dict):
        return self._dispatcher(op, args)

    # -- discovery file --------------------------------------------------
    def connection_info(self) -> dict:
        info = {
            "app": self.app,
            "version": self.version,
            "protocol": BRIDGE_PROTOCOL_VERSION,
            "pid": os.getpid(),
            "host": self.host,
            "port": self.port,
            "token": self.token,
            "started": self.started,
            "python": sys.version.split()[0],
            "executable": sys.executable,
            "cwd": os.getcwd(),
            "hostname": socket.gethostname(),
        }
        try:
            info.update(self._info() or {})
        except Exception:
            pass
        return info

    def _write_instance_file(self):
        path = os.path.join(instances_dir(), "%s-%d.json" % (self.app, os.getpid()))
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.connection_info(), f, indent=1)
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, path)
        self.instance_file = path

    def _remove_instance_file(self):
        if self.instance_file and os.path.exists(self.instance_file):
            try:
                os.remove(self.instance_file)
            except OSError:
                pass
        self.instance_file = None


def cleanup_stale_instance_files():
    """Remove discovery files whose process no longer exists."""
    d = instances_dir()
    try:
        names = os.listdir(d)
    except OSError:
        return
    for name in names:
        if not name.endswith(".json"):
            continue
        path = os.path.join(d, name)
        try:
            with open(path) as f:
                info = json.load(f)
            pid = int(info.get("pid", 0))
        except Exception:
            continue
        if pid and not _pid_alive(pid):
            try:
                os.remove(path)
            except OSError:
                pass


def _pid_alive(pid: int) -> bool:
    if sys.platform.startswith("win"):
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return False
        ctypes.windll.kernel32.CloseHandle(h)
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True

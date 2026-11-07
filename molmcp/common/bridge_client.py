"""HTTP client for an in-app molmcp bridge (persistent keep-alive connection)."""
from __future__ import annotations

import base64
import http.client
import json
import socket
import threading
import time
from typing import Any, Optional

from . import discovery


class BridgeError(RuntimeError):
    """Raised when the bridge reports an error for an operation."""

    def __init__(self, message: str, traceback_text: Optional[str] = None):
        super().__init__(message)
        self.traceback_text = traceback_text


class NotConnected(RuntimeError):
    pass


class BridgeClient:
    def __init__(self, app: str, default_timeout: float = 120.0):
        self.app = app
        self.info: Optional[dict] = None
        self._conn: Optional[http.client.HTTPConnection] = None
        self._lock = threading.Lock()
        self.default_timeout = default_timeout
        self.stats = {"calls": 0, "errors": 0, "total_ms": 0.0}

    # -- connection management -------------------------------------------
    def connect(self, info: Optional[dict] = None, pid: Optional[int] = None, port: Optional[int] = None) -> dict:
        """Attach to a live bridge; picks the newest one when nothing is specified."""
        if info is None:
            candidates = discovery.list_instances(self.app)
            if pid is not None:
                candidates = [c for c in candidates if int(c.get("pid", 0)) == int(pid)]
            if port is not None:
                candidates = [c for c in candidates if int(c.get("port", 0)) == int(port)]
            for c in candidates:
                if self._ping(c):
                    info = c
                    break
            if info is None:
                raise NotConnected("no running %s bridge found" % self.app)
        with self._lock:
            self._close()
            self.info = info
        return info

    def ensure(self) -> dict:
        if self.info and self._ping(self.info):
            return self.info
        return self.connect()

    @property
    def connected(self) -> bool:
        return self.info is not None

    def _close(self):
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def _ping(self, info: dict, timeout: float = 2.0) -> bool:
        try:
            conn = http.client.HTTPConnection(info["host"], int(info["port"]), timeout=timeout)
            conn.request("GET", "/ping")
            resp = conn.getresponse()
            data = json.loads(resp.read().decode("utf-8"))
            conn.close()
            return bool(data.get("ok")) and data.get("app") == self.app
        except Exception:
            return False

    # -- calls --------------------------------------------------------------
    def call(self, op: str, timeout: Optional[float] = None, **args) -> Any:
        if self.info is None:
            self.connect()
        assert self.info is not None
        body = json.dumps({"op": op, "args": args}).encode("utf-8")
        headers = {"Content-Type": "application/json", "Authorization": "Bearer " + self.info["token"],
                   "Content-Length": str(len(body))}
        timeout = timeout or self.default_timeout
        t0 = time.time()
        with self._lock:
            last_exc = None
            for attempt in range(2):
                try:
                    if self._conn is None:
                        self._conn = http.client.HTTPConnection(self.info["host"], int(self.info["port"]), timeout=timeout)
                    else:
                        self._conn.sock and self._conn.sock.settimeout(timeout)
                    self._conn.request("POST", "/call", body=body, headers=headers)
                    resp = self._conn.getresponse()
                    raw = resp.read()
                    break
                except (http.client.HTTPException, ConnectionError, socket.timeout, OSError) as e:
                    last_exc = e
                    self._close()
                    if isinstance(e, socket.timeout):
                        raise BridgeError("%s bridge timed out after %.0fs on op %r (is the app busy or showing a dialog?)" % (self.app, timeout, op))
            else:
                self.info = None
                raise NotConnected("lost connection to %s bridge: %s" % (self.app, last_exc))
        self.stats["calls"] += 1
        self.stats["total_ms"] += (time.time() - t0) * 1000
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            raise BridgeError("bad response from bridge: %r" % raw[:200])
        if resp.status == 401:
            self.info = None
            raise NotConnected("bridge rejected token; reconnecting on next call")
        if not data.get("ok"):
            self.stats["errors"] += 1
            raise BridgeError(data.get("error", "unknown error"), data.get("traceback"))
        return data.get("result")

    @staticmethod
    def b64_to_bytes(s: str) -> bytes:
        return base64.b64decode(s)

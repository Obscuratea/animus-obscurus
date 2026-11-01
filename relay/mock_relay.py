#!/usr/bin/env python3
"""Local stand-in for the Cloudflare relay (same protocol as worker.js), for testing. Usage: mock_relay.py [port]
PUT /r/<id> (X-Key header) claims or updates a list, GET /r/<id> reads it, DELETE /r/<id> (X-Key) removes it."""
import hashlib, re, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ID_RE = re.compile(r"^[A-Za-z0-9_-]{20,40}$")
MAX = 256 * 1024
store = {}   # id -> (sha256 of key, body)


class H(BaseHTTPRequestHandler):
    def reply(self, code, body=b""):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def rid(self):
        m = re.fullmatch(r"/r/([^/]+)", self.path)
        return m.group(1) if m and ID_RE.match(m.group(1)) else None

    def key_ok(self, rid):
        k = hashlib.sha256(self.headers.get("X-Key", "").encode()).hexdigest()
        return rid not in store or store[rid][0] == k, k

    def do_GET(self):
        rid = self.rid()
        if not rid:
            return self.reply(400)
        self.reply(200, store[rid][1]) if rid in store else self.reply(404)

    def do_PUT(self):
        rid = self.rid()
        if not rid or not self.headers.get("X-Key"):
            return self.reply(400)
        n = int(self.headers.get("Content-Length", 0))
        if n > MAX:
            return self.reply(413)
        ok, k = self.key_ok(rid)
        if not ok:
            return self.reply(403)
        store[rid] = (k, self.rfile.read(n))
        self.reply(200, b"{}")

    def do_DELETE(self):
        rid = self.rid()
        if not rid:
            return self.reply(400)
        ok, _ = self.key_ok(rid)
        if not ok:
            return self.reply(403)
        store.pop(rid, None)
        self.reply(200, b"{}")

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8790
    print(f"mock relay on http://127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()

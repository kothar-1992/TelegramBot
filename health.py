"""Keep the free-tier instance alive and answer health checks.

Free web-service plans (Render et al.) shut an app down after ~15 minutes
without *inbound* traffic.  A long-polling bot only ever makes outbound
connections, so it would sleep forever.  Two small pieces solve that:

* a tiny HTTP server that answers ``GET /health`` (Render needs a bound port)
* a periodic ping to our own public URL (counts as inbound traffic)

Nothing here is required for local or VPS use — both are simply inactive
unless ``SELF_URL`` / ``PORT`` are configured.
"""

from __future__ import annotations

import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger(__name__)


class _HealthHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # BaseHTTPRequestHandler API — do_GET, not get
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path in {"/", "/health", "/healthz"}:
            body = b'{"status":"ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def log_message(self, *args: object) -> None:  # silence per-request logging
        pass


def start_health_server() -> ThreadingHTTPServer | None:
    """Bind ``PORT`` in a background thread. Returns None if it cannot bind."""
    port = int(os.getenv("PORT", "8080"))
    try:
        server = ThreadingHTTPServer(("0.0.0.0", port), _HealthHandler)
    except OSError as err:
        log.warning("Health server not started on port %s (%s) — fine locally", port, err)
        return None

    thread = threading.Thread(target=server.serve_forever, name="health", daemon=True)
    thread.start()
    log.info("Health endpoint listening on :%s/health", port)
    return server


def ping(url: str) -> bool:
    """Hit our own URL so the platform sees inbound traffic. Blocking — call in a thread."""
    import httpx

    target = _normalise(url)
    try:
        response = httpx.get(target, timeout=15.0, follow_redirects=True)
        return response.status_code == 200
    except Exception as exc:  # a failed keep-alive must never kill the bot
        log.warning("Keep-alive ping failed: %s (%s)", target, type(exc).__name__)
        return False


def _normalise(url: str) -> str:
    """Accept `host`, `host:port` or a full URL; always end at /health."""
    url = url.strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        host = url.split("/", 1)[0]
        scheme = "http" if host.startswith(("localhost", "127.0.0.1", "[::1]")) else "https"
        url = f"{scheme}://{url}"
    if not url.endswith(("/health", "/healthz")):
        url = f"{url}/health"
    return url
"""Tiny HTTP server for the chat UI. Standard library only.

  GET  /              -> the chat page (web/static/index.html)
  POST /api/respond   -> {"mode": "strict"|"lax", "message": "..."}
                         returns {"agent": "...", "reply": "..."}

Binds to 127.0.0.1 only; it's a local demo, not a production service.
Run with: python -m web.server   (PORT env var, default 8000)
"""

import json
import os
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.mock_voice_agent import MockVoiceAgent

INDEX_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")
AGENT_MODES = ("strict", "lax")
MAX_MESSAGE_LENGTH = 1000
MAX_BODY_BYTES = 16 * 1024
DEFAULT_PORT = 8000


class ValidationError(ValueError):
    """Client sent a request the API can't accept (maps to HTTP 400)."""


def parse_request(raw):
    """Validate a /api/respond body. Returns (mode, message) or raises."""
    try:
        body = json.loads(raw)
    except ValueError:
        raise ValidationError("body must be valid JSON")
    if not isinstance(body, dict):
        raise ValidationError("body must be a JSON object")
    mode = body.get("mode")
    if mode not in AGENT_MODES:
        raise ValidationError("mode must be 'strict' or 'lax'")
    message = body.get("message")
    if not isinstance(message, str):
        raise ValidationError("message must be a string")
    if not message.strip():
        raise ValidationError("message must not be empty")
    if len(message) > MAX_MESSAGE_LENGTH:
        raise ValidationError("message is too long")
    return mode, message


class AgentRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        with open(INDEX_PATH, "rb") as f:
            self._send(HTTPStatus.OK, "text/html; charset=utf-8", f.read())

    def do_POST(self):
        if self.path != "/api/respond":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid Content-Length"})
            return
        if length > MAX_BODY_BYTES:
            self._send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "body too large"})
            return
        try:
            mode, message = parse_request(self.rfile.read(length))
        except ValidationError as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return
        agent = MockVoiceAgent(mode=mode)
        self._send_json(HTTPStatus.OK, {"agent": agent.name, "reply": agent.respond(message)})

    def _send_json(self, status, payload):
        self._send(status, "application/json", json.dumps(payload).encode())

    def _send(self, status, content_type, body):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)


def make_server(host, port):
    return ThreadingHTTPServer((host, port), AgentRequestHandler)


def main():
    port = int(os.environ.get("PORT", DEFAULT_PORT))
    server = make_server("127.0.0.1", port)
    print("Chat UI on http://127.0.0.1:%d" % port, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

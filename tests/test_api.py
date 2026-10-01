"""Tests for the gateway API client against a mock that mimics the real gateway.

The mock enforces what the ESP32 gateway does: HTTP Digest authentication
(realm "Login Required", qop=auth, MD5) and a Content-Length header on POST.
The client module is loaded directly so Home Assistant is not needed.
"""

import asyncio
import hashlib
import importlib.util
import json
import re
import secrets
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

spec = importlib.util.spec_from_file_location(
    "api", Path(__file__).parent.parent / "custom_components" / "steinel_mesh" / "api.py"
)
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)

USER, PASSWORD = "admin", "12345678"
NODES = {
    "configured": True,
    "network": "BV47",
    "count": 1,
    "nodes": [
        {
            "address": "0x0010",
            "name": "Durchgang",
            "product": "L 810 SC",
            "roles": ["light", "light_control", "sensor"],
            "state": {
                "reachable": True,
                "on": True,
                "brightness": 40,
                "auto": False,
                "sensors": [{"element": 3, "property": "0x004E", "raw": "400D03", "lux": 2000.0}],
            },
        }
    ],
}


def _md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


class Gateway(BaseHTTPRequestHandler):
    received: list = []

    def log_message(self, *args):
        pass

    def _auth_ok(self) -> bool:
        header = self.headers.get("Authorization", "")
        if not header.startswith("Digest "):
            return False
        params = {k: a or b for k, a, b in re.findall(r'(\w+)=(?:"([^"]*)"|([^,\s]+))', header)}
        if params.get("username") != USER:
            return False
        ha1 = _md5(f"{USER}:{params['realm']}:{PASSWORD}")
        ha2 = _md5(f"{self.command}:{params['uri']}")
        expected = _md5(
            f"{ha1}:{params['nonce']}:{params['nc']}:{params['cnonce']}:{params['qop']}:{ha2}"
        )
        return params.get("response") == expected

    def _challenge(self):
        self.send_response(401)
        self.send_header(
            "WWW-Authenticate",
            f'Digest realm="Login Required", qop="auth", nonce="{secrets.token_hex(16)}", '
            f'opaque="{secrets.token_hex(16)}"',
        )
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self._auth_ok():
            return self._challenge()
        if urlparse(self.path).path == "/api/nodes":
            return self._json(200, NODES)
        self._json(404, {"message": "Not found"})

    def do_POST(self):
        # Like the ESP-IDF server, refuse a POST without Content-Length.
        if "Content-Length" not in self.headers:
            self.send_response(411)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.rfile.read(int(self.headers["Content-Length"]))
        if not self._auth_ok():
            return self._challenge()
        url = urlparse(self.path)
        if url.path == "/api/nodes/0x0010":
            Gateway.received.append(parse_qs(url.query))
            return self._json(200, {"message": "Command queued"})
        self._json(404, {"message": "Unknown node address"})


@pytest.fixture
def host():
    Gateway.received = []
    server = HTTPServer(("127.0.0.1", 0), Gateway)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"127.0.0.1:{server.server_port}"
    server.shutdown()


def run(coro):
    return asyncio.run(coro)


def test_get_nodes_uses_digest_auth(host):
    async def go():
        async with httpx.AsyncClient() as http:
            return await api.GatewayClient(http, host, USER, PASSWORD).get_nodes()

    assert run(go())["nodes"][0]["name"] == "Durchgang"


def test_commands_use_query_args_and_clamp_brightness(host):
    async def go():
        async with httpx.AsyncClient() as http:
            client = api.GatewayClient(http, host, USER, PASSWORD)
            await client.send_command("0x0010", on=True)
            await client.send_command("0x0010", brightness=250)
            await client.send_command("0x0010", auto=False)

    run(go())
    assert Gateway.received == [{"on": ["1"]}, {"brightness": ["100"]}, {"auto": ["0"]}]


def test_unknown_node_is_a_gateway_error(host):
    async def go():
        async with httpx.AsyncClient() as http:
            await api.GatewayClient(http, host, USER, PASSWORD).send_command("0x0099", on=True)

    with pytest.raises(api.GatewayError, match="Unknown node address"):
        run(go())


def test_wrong_password_is_an_auth_error(host):
    async def go():
        async with httpx.AsyncClient() as http:
            await api.GatewayClient(http, host, USER, "wrong").get_nodes()

    with pytest.raises(api.GatewayAuthError):
        run(go())


def test_unreachable_gateway_is_a_gateway_error_not_auth_error():
    async def go():
        async with httpx.AsyncClient() as http:
            await api.GatewayClient(http, "127.0.0.1:1", USER, PASSWORD).get_nodes()

    with pytest.raises(api.GatewayError) as error:
        run(go())
    assert not isinstance(error.value, api.GatewayAuthError)

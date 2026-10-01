from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import json
import os
import re
import secrets
import sqlite3
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from urllib.parse import unquote

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel, ConfigDict, Field

COOKIE = "ambient_workspace"
SCOPES = {"workspace.control", "workspace.manage"}
HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}
PRIVATE_HEADERS = {"host", "cookie", "authorization", "origin", "x-account-id", "x-node-id", "x-grant-id", "forwarded"}
NODE_RE = re.compile(r"^[a-f0-9]{24}$")


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def iso(value: float | None) -> str | None:
    return datetime.fromtimestamp(value, UTC).isoformat().replace("+00:00", "Z") if value is not None else None


@dataclass
class GatewayConfig:
    database: str = "data/workspace-gateway.sqlite3"
    secret: str = ""
    workspace_domain: str = "localhost:8090"
    scheme: str = "http"
    http_limit: int = 2 * 1024 * 1024
    frame_limit: int = 256 * 1024
    http_concurrency: int = 16
    ws_concurrency: int = 16
    request_timeout: float = 30
    pairing_ttl: int = 300
    launch_ttl: int = 60
    session_ttl: int = 3600
    max_nodes: int = 10000

    def __post_init__(self):
        self.workspace_domain = self.workspace_domain.lower().rstrip(".")
        if not self.secret.strip():
            raise ValueError("WORKSPACE_GATEWAY_SECRET is required, including local development")
        if self.scheme not in {"http", "https"} or not re.fullmatch(
            r"[a-z0-9.-]+(?::[0-9]{1,5})?", self.workspace_domain
        ):
            raise ValueError("Use a hostname[:port] workspace domain and http/https scheme")
        hostname = self.workspace_domain.split(":")[0]
        if self.scheme != "https" and hostname != "localhost":
            raise ValueError("Public workspaces require HTTPS; HTTP is only available for *.localhost")

    @classmethod
    def from_env(cls):
        return cls(
            database=os.getenv("WORKSPACE_GATEWAY_DATABASE", "data/workspace-gateway.sqlite3"),
            secret=os.getenv("WORKSPACE_GATEWAY_SECRET", ""),
            workspace_domain=os.getenv("WORKSPACE_GATEWAY_DOMAIN", "localhost:8090"),
            scheme=os.getenv("WORKSPACE_GATEWAY_SCHEME", "http"),
        )


class PairBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    scopes: list[str] = Field(default_factory=lambda: ["workspace.control"], min_length=1, max_length=2)
    expires_in: int = Field(default=86400, ge=300, le=30 * 86400)


class ClaimBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=200)


class ApprovalBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_id: str = Field(min_length=1, max_length=200)
    grant_id: str = Field(min_length=1, max_length=100)


class Store:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            PRAGMA journal_mode=WAL;
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS nodes (
                node_id TEXT PRIMARY KEY, name TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE,
                pairing_hash TEXT UNIQUE, pairing_expires REAL NOT NULL, status TEXT NOT NULL,
                account_id TEXT, account_label TEXT, grant_id TEXT NOT NULL, scopes TEXT NOT NULL,
                expires REAL NOT NULL, last_seen REAL, created REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS nodes_account ON nodes(account_id);
            CREATE TABLE IF NOT EXISTS launches (token_hash TEXT PRIMARY KEY, node_id TEXT NOT NULL,
                grant_id TEXT NOT NULL, expires REAL NOT NULL, FOREIGN KEY(node_id) REFERENCES nodes(node_id));
            CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, node_id TEXT NOT NULL,
                grant_id TEXT NOT NULL, expires REAL NOT NULL, FOREIGN KEY(node_id) REFERENCES nodes(node_id));
            CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, timestamp REAL NOT NULL,
                event TEXT NOT NULL, node_id TEXT, account_id TEXT, status INTEGER, bytes INTEGER);
            CREATE TABLE IF NOT EXISTS deleted_accounts (account_id TEXT PRIMARY KEY, deleted REAL NOT NULL);
        """)

    def one(self, sql, args=()):
        row = self.db.execute(sql, args).fetchone()
        return dict(row) if row else None

    def node(self, node_id):
        return self.one("SELECT * FROM nodes WHERE node_id=?", (node_id,))

    def audit(self, now, event, node=None, status=None, size=None):
        self.db.execute(
            "INSERT INTO audit(timestamp,event,node_id,account_id,status,bytes) VALUES(?,?,?,?,?,?)",
            (now, event, node["node_id"] if node else None, node["account_id"] if node else None, status, size),
        )


@dataclass
class BrowserPipe:
    accepted: asyncio.Future
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=32))


@dataclass
class Tunnel:
    socket: WebSocket
    node_id: str
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    http: dict[str, asyncio.Future] = field(default_factory=dict)
    http_services: dict[str, str] = field(default_factory=dict)
    browser: dict[str, BrowserPipe] = field(default_factory=dict)
    closed: bool = False

    async def send(self, message, authorize=None):
        async with self.send_lock:
            if self.closed:
                raise HTTPException(503, "Node is offline")
            if authorize is not None:
                authorize()
            await self.socket.send_json(message)

    async def exchange(self, message, future, timeout, authorize=None):
        async with asyncio.timeout(timeout):
            await self.send(message, authorize=authorize)
            return await future

    async def close(self, reason="Node is offline", revoked=False):
        if self.closed:
            return
        if revoked:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self.send({"type": "revoked", "reason": reason}), timeout=1)
        self.closed = True
        for future in list(self.http.values()):
            if not future.done():
                future.set_exception(HTTPException(503, reason))
        for pipe in list(self.browser.values()):
            if not pipe.accepted.done():
                pipe.accepted.set_exception(HTTPException(503, reason))
            while pipe.queue.full():
                pipe.queue.get_nowait()
            pipe.queue.put_nowait({"type": "ws.close", "code": 1008 if revoked else 1012, "reason": reason})
        with contextlib.suppress(Exception):
            await asyncio.wait_for(self.socket.close(code=1008 if revoked else 1012, reason=reason[:100]), timeout=1)


def safe_headers(pairs, *, response=False, fixed_frame=False):
    if not isinstance(pairs, list) or len(pairs) > 100:
        raise ValueError("Invalid headers")
    connection_tokens = set()
    for pair in pairs:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2 or not all(isinstance(v, str) for v in pair):
            raise ValueError("Invalid header pair")
        if pair[0].lower() == "connection":
            connection_tokens.update(value.strip().lower() for value in pair[1].split(","))
    result = []
    for name, value in pairs:
        lower = name.lower()
        if (
            not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", name)
            or any(c in value for c in "\r\n\x00")
            or len(value) > 8192
        ):
            raise ValueError("Invalid header")
        if lower in HOP_HEADERS | connection_tokens or lower == "content-length":
            continue
        if response:
            if lower == "set-cookie":
                continue
            if lower == "content-encoding":
                if not fixed_frame:
                    continue
                if value.lower().strip() != "gzip":
                    raise ValueError("Fixed frame assets only allow gzip content encoding")
        elif (
            lower in PRIVATE_HEADERS
            or lower.startswith(("x-forwarded-", "x-ambient-", "sec-websocket-"))
            or lower == "accept-encoding"
        ):
            continue
        result.append([lower, value])
    if sum(len(a) + len(b) for a, b in result) > 32768:
        raise ValueError("Headers exceed quota")
    return result


def decode_body(value, limit):
    if not isinstance(value, str) or len(value) > ((limit + 2) // 3) * 4:
        raise ValueError("Body exceeds quota")
    result = base64.b64decode(value, validate=True)
    if len(result) > limit:
        raise ValueError("Body exceeds quota")
    return result


def route_path(path: str, method: str):
    decoded = path
    for _ in range(3):
        decoded = unquote(decoded)
    if (
        not decoded.startswith("/")
        or "\\" in decoded
        or "\x00" in decoded
        or "//" in decoded
        or any(part in {"..", "."} for part in decoded.split("/"))
    ):
        raise HTTPException(400, "Invalid workspace path")
    if decoded == "/api/remote-workspace" or decoded.startswith("/api/remote-workspace/"):
        raise HTTPException(403, "Connection management is local only")
    if decoded.startswith("/v1/") or (decoded.startswith("/_ambient/") and decoded != "/_ambient/frame.html"):
        raise HTTPException(404, "Unknown workspace route")
    if decoded == "/_ambient/frame.html":
        service, local, public = "frame", "/frame.html", True
    elif decoded in {
        "/frame_shell.css",
        "/frame_shell.mjs",
        "/controller_facade.mjs",
        "/presentation_context.mjs",
    } or decoded.startswith("/vendor/"):
        service, local, public = "frame", decoded, True
    elif decoded.startswith(("/api/", "/ws/")):
        service, local, public = "backend", path, False
    else:
        service, local, public = "frontend", path, False
    if public and method not in {"GET", "HEAD"}:
        raise HTTPException(405, "Static frame resources are read only")
    if service == "frontend" and method not in {"GET", "HEAD"}:
        raise HTTPException(405, "Frontend resources are read only")
    return service, local, public


def create_app(config: GatewayConfig | None = None) -> FastAPI:
    config = config or GatewayConfig.from_env()
    store = Store(config.database)
    tunnels: dict[str, Tunnel] = {}

    def now():
        return app.state.clock()

    def origin(node_id):
        return f"{config.scheme}://{node_id}.{config.workspace_domain}"

    def host_node(connection):
        host = connection.headers.get("host", "").lower().rstrip(".")
        suffix = "." + config.workspace_domain
        if not host.endswith(suffix):
            return None
        node_id = host[: -len(suffix)]
        return node_id if NODE_RE.fullmatch(node_id) else "invalid"

    def control_host(connection):
        if host_node(connection) is not None:
            raise HTTPException(404, "Control routes are unavailable on workspace hosts")

    def auth_secret(request):
        control_host(request)
        if not secrets.compare_digest(request.headers.get("authorization", ""), "Bearer " + config.secret):
            raise HTTPException(401, "Service authentication required")

    def device_node(request):
        control_host(request)
        value = request.headers.get("authorization", "")
        if not value.startswith("Bearer ") or len(value) > 300:
            raise HTTPException(401, "Device authentication required")
        node = store.one("SELECT * FROM nodes WHERE token_hash=?", (digest(value[7:]),))
        if not node:
            raise HTTPException(401, "Invalid device credentials")
        return node

    def node_status(node):
        if node["status"] == "revoked" or (
            node["account_id"]
            and store.one("SELECT account_id FROM deleted_accounts WHERE account_id=?", (node["account_id"],))
        ):
            return "revoked"
        if node["expires"] <= now() or (node["status"] == "pending" and node["pairing_expires"] <= now()):
            return "expired"
        return node["status"]

    def serialize(node):
        tunnel = tunnels.get(node["node_id"])
        status = node_status(node)
        return {
            "node_id": node["node_id"],
            "name": node["name"],
            "status": status,
            "online": status == "paired" and tunnel is not None and not tunnel.closed,
            "account_id": node["account_id"],
            "account_label": node["account_label"],
            "grant_id": node["grant_id"],
            "scopes": json.loads(node["scopes"]),
            "expires_at": iso(node["expires"]),
            "workspace_origin": origin(node["node_id"]),
            "last_seen_at": iso(node["last_seen"]),
        }

    def identity(node):
        info = serialize(node)
        return {key: info[key] for key in ("node_id", "account_id", "grant_id", "scopes", "workspace_origin")}

    def account_node(account_id, node_id):
        node = store.node(node_id)
        if not node or node["account_id"] != account_id:
            raise HTTPException(404, "Unknown node")
        return node

    def valid_node(node):
        if not node or node_status(node) != "paired":
            raise HTTPException(401, "Workspace authorization is inactive")

    def session_node(connection, *, public=False):
        node_id = host_node(connection)
        if node_id is None:
            raise HTTPException(404, "Use the node workspace hostname")
        node = store.node(node_id)
        valid_node(node)
        if not public:
            cookie = connection.cookies.get(COOKIE, "")
            session = store.one("SELECT * FROM sessions WHERE token_hash=?", (digest(cookie),)) if cookie else None
            if (
                not session
                or session["node_id"] != node_id
                or session["grant_id"] != node["grant_id"]
                or session["expires"] <= now()
            ):
                raise HTTPException(401, "Open the workspace from the signed-in cloud portal")
        else:
            session = None
        return node, session

    def active_tunnel(node):
        tunnel = tunnels.get(node["node_id"])
        if not tunnel or tunnel.closed:
            raise HTTPException(503, "Node is offline")
        return tunnel

    async def revoke(node):
        store.db.execute("UPDATE nodes SET status='revoked',pairing_hash=NULL WHERE node_id=?", (node["node_id"],))
        store.db.execute("DELETE FROM sessions WHERE node_id=?", (node["node_id"],))
        store.db.execute("DELETE FROM launches WHERE node_id=?", (node["node_id"],))
        store.audit(now(), "revoke", node)
        if tunnel := tunnels.get(node["node_id"]):
            await tunnel.close("Workspace authorization revoked", revoked=True)
        return serialize(store.node(node["node_id"]))

    async def sweep():
        while True:
            await asyncio.sleep(0.25)
            for node_id, tunnel in list(tunnels.items()):
                if node_status(store.node(node_id)) != "paired":
                    await tunnel.close("Workspace authorization expired", revoked=True)
            store.db.execute("DELETE FROM launches WHERE expires<=?", (now(),))
            store.db.execute("DELETE FROM sessions WHERE expires<=?", (now(),))

    @asynccontextmanager
    async def lifespan(application):
        task = asyncio.create_task(sweep())
        yield
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        for tunnel in list(tunnels.values()):
            await tunnel.close("Gateway shutting down")
        store.db.close()

    app = FastAPI(
        title="Ambient Workspace Gateway (proposal)", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None
    )
    app.state.config = config
    app.state.store = store
    app.state.tunnels = tunnels
    app.state.clock = time.time

    @app.get("/health")
    async def health(request: Request):
        control_host(request)
        return {"status": "ok"}

    @app.post("/v1/connector/pairings")
    async def pair(request: Request, body: PairBody):
        control_host(request)
        if (
            not set(body.scopes) <= SCOPES
            or "workspace.control" not in body.scopes
            or len(set(body.scopes)) != len(body.scopes)
        ):
            raise HTTPException(422, "Unknown or duplicate workspace scope")
        if store.one("SELECT count(*) AS n FROM nodes")["n"] >= config.max_nodes:
            raise HTTPException(429, "Gateway node capacity reached")
        node_id, token, code, grant = (
            secrets.token_hex(12),
            secrets.token_urlsafe(48),
            secrets.token_urlsafe(18),
            secrets.token_hex(16),
        )
        stamp = now()
        store.db.execute(
            "INSERT INTO nodes(node_id,name,token_hash,pairing_hash,pairing_expires,status,grant_id,scopes,expires,created) VALUES(?,?,?,?,?,'pending',?,?,?,?)",
            (
                node_id,
                body.name,
                digest(token),
                digest(code),
                stamp + config.pairing_ttl,
                grant,
                json.dumps(body.scopes),
                stamp + body.expires_in,
                stamp,
            ),
        )
        node = store.node(node_id)
        store.audit(stamp, "pair", node)
        return {
            "node_id": node_id,
            "connector_token": token,
            "pairing_code": code,
            "pairing_expires_at": iso(node["pairing_expires"]),
            "expires_at": iso(node["expires"]),
            "workspace_origin": origin(node_id),
        }

    @app.get("/v1/connector/state")
    async def state(request: Request):
        node = device_node(request)
        if node_status(node) == "expired" and (tunnel := tunnels.get(node["node_id"])):
            await tunnel.close("Workspace authorization expired", revoked=True)
        return serialize(node)

    @app.post("/v1/connector/approve")
    async def approve(request: Request, body: ApprovalBody):
        node = device_node(request)
        if node_status(node) != "claimed" or node["account_id"] != body.account_id or node["grant_id"] != body.grant_id:
            raise HTTPException(409, "Approval must match the claimed account and grant")
        store.db.execute("UPDATE nodes SET status='paired' WHERE node_id=? AND status='claimed'", (node["node_id"],))
        store.audit(now(), "approve", node)
        return serialize(store.node(node["node_id"]))

    @app.post("/v1/connector/revoke")
    async def device_revoke(request: Request):
        return await revoke(device_node(request))

    @app.post("/v1/accounts/{account_id}/pairings/claim")
    async def claim(request: Request, account_id: str, body: ClaimBody):
        auth_secret(request)
        if len(account_id) > 200:
            raise HTTPException(422, "Invalid account")
        if store.one("SELECT account_id FROM deleted_accounts WHERE account_id=?", (account_id,)):
            raise HTTPException(410, "Account has been deleted")
        node = store.one("SELECT * FROM nodes WHERE pairing_hash=?", (digest(body.code),))
        if not node or node_status(node) != "pending" or node["pairing_expires"] <= now():
            raise HTTPException(409, "Pairing code expired or already claimed")
        changed = store.db.execute(
            "UPDATE nodes SET account_id=?,account_label=?,status='claimed',pairing_hash=NULL WHERE node_id=? AND status='pending' AND pairing_hash=?",
            (account_id, body.label, node["node_id"], digest(body.code)),
        ).rowcount
        if changed != 1:
            raise HTTPException(409, "Pairing code already claimed")
        node = store.node(node["node_id"])
        store.audit(now(), "claim", node)
        return serialize(node)

    @app.get("/v1/accounts/{account_id}/nodes")
    async def nodes(request: Request, account_id: str):
        auth_secret(request)
        return {
            "nodes": [
                serialize(dict(row))
                for row in store.db.execute(
                    "SELECT * FROM nodes WHERE account_id=? ORDER BY created DESC", (account_id,)
                )
            ]
        }

    @app.post("/v1/accounts/{account_id}/nodes/{node_id}/launch")
    async def launch(request: Request, account_id: str, node_id: str):
        auth_secret(request)
        node = account_node(account_id, node_id)
        valid_node(node)
        active_tunnel(node)
        token, expires = secrets.token_urlsafe(32), min(now() + config.launch_ttl, node["expires"])
        store.db.execute("INSERT INTO launches VALUES(?,?,?,?)", (digest(token), node_id, node["grant_id"], expires))
        store.audit(now(), "launch", node)
        return {"url": origin(node_id) + "/_ambient/launch?ticket=" + token, "expires_at": iso(expires)}

    @app.delete("/v1/accounts/{account_id}/nodes/{node_id}")
    async def account_revoke(request: Request, account_id: str, node_id: str):
        auth_secret(request)
        return await revoke(account_node(account_id, node_id))

    async def revoke_account_nodes(account_id):
        selected = [
            dict(row)
            for row in store.db.execute("SELECT * FROM nodes WHERE account_id=? AND status!='revoked'", (account_id,))
        ]
        # Invalidate every grant before yielding while closing socket connections.
        store.db.execute("UPDATE nodes SET status='revoked',pairing_hash=NULL WHERE account_id=?", (account_id,))
        for node in selected:
            await revoke(node)
        return {"revoked": len(selected)}

    @app.delete("/v1/accounts/{account_id}/nodes")
    async def bulk_revoke(request: Request, account_id: str):
        auth_secret(request)
        return await revoke_account_nodes(account_id)

    @app.delete("/v1/accounts/{account_id}")
    async def delete_account(request: Request, account_id: str):
        auth_secret(request)
        # A permanent tombstone blocks concurrent claims and all existing grants.
        store.db.execute("INSERT OR IGNORE INTO deleted_accounts VALUES(?,?)", (account_id, now()))
        return await revoke_account_nodes(account_id)

    @app.get("/_ambient/launch")
    async def consume_launch(request: Request, ticket: str = ""):
        node_id = host_node(request)
        node = store.node(node_id) if node_id else None
        valid_node(node)
        launched = store.one("SELECT * FROM launches WHERE token_hash=?", (digest(ticket),))
        if (
            not launched
            or launched["node_id"] != node_id
            or launched["grant_id"] != node["grant_id"]
            or launched["expires"] <= now()
        ):
            raise HTTPException(401, "Launch link expired or already used")
        if store.db.execute("DELETE FROM launches WHERE token_hash=?", (digest(ticket),)).rowcount != 1:
            raise HTTPException(401, "Launch link already used")
        token, expires = secrets.token_urlsafe(32), min(now() + config.session_ttl, node["expires"])
        store.db.execute("INSERT INTO sessions VALUES(?,?,?,?)", (digest(token), node_id, node["grant_id"], expires))
        store.audit(now(), "session", node)
        response = RedirectResponse(
            "/", status_code=303, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}
        )
        response.set_cookie(
            COOKIE,
            token,
            max_age=max(1, int(expires - now())),
            httponly=True,
            secure=config.scheme == "https",
            samesite="lax",
            path="/",
        )
        return response

    @app.websocket("/v1/connector/tunnel")
    async def connector(socket: WebSocket):
        try:
            node = device_node(socket)
            valid_node(node)
        except HTTPException:
            await socket.close(code=1008)
            return
        await socket.accept()
        tunnel = Tunnel(socket, node["node_id"])
        previous = tunnels.get(node["node_id"])
        if previous:
            await previous.close("Connector replaced by a new connection")
        tunnels[node["node_id"]] = tunnel
        store.db.execute("UPDATE nodes SET last_seen=? WHERE node_id=?", (now(), node["node_id"]))
        store.audit(now(), "online", node)
        await tunnel.send({"type": "hello", **identity(node)})
        try:
            while True:
                wire = await socket.receive_text()
                if len(wire.encode()) > config.http_limit * 4 // 3 + 65536:
                    raise ValueError("Tunnel message exceeds quota")
                message = json.loads(wire)
                if not isinstance(message, dict):
                    raise ValueError("Invalid tunnel message")
                valid_node(store.node(node["node_id"]))
                kind, correlation = message.get("type"), message.get("id")
                if kind == "ping":
                    store.db.execute("UPDATE nodes SET last_seen=? WHERE node_id=?", (now(), node["node_id"]))
                    await tunnel.send({"type": "pong"})
                elif kind == "http.response" and correlation in tunnel.http:
                    body = decode_body(message.get("body"), config.http_limit)
                    headers = safe_headers(
                        message.get("headers"),
                        response=True,
                        fixed_frame=tunnel.http_services.get(correlation) == "frame",
                    )
                    status = message.get("status")
                    if not isinstance(status, int) or not 200 <= status <= 599:
                        raise ValueError("Invalid upstream status")
                    future = tunnel.http[correlation]
                    if not future.done():
                        future.set_result((status, headers, body))
                elif kind in {"ws.accept", "ws.data", "ws.close"} and correlation in tunnel.browser:
                    pipe = tunnel.browser[correlation]
                    if kind == "ws.accept":
                        if not pipe.accepted.done():
                            pipe.accepted.set_result(message.get("subprotocol"))
                    else:
                        if kind == "ws.data":
                            if message.get("kind") == "bytes":
                                decode_body(message.get("data"), config.frame_limit)
                            elif (
                                message.get("kind") != "text"
                                or not isinstance(message.get("data"), str)
                                or len(message["data"].encode()) > config.frame_limit
                            ):
                                raise ValueError("Invalid WebSocket frame")
                        if pipe.queue.full():
                            raise ValueError("Browser WebSocket backpressure quota exceeded")
                        pipe.queue.put_nowait(message)
                elif kind not in {"http.response", "ws.accept", "ws.data", "ws.close", "pong"}:
                    raise ValueError("Unknown tunnel message type")
        except (WebSocketDisconnect, RuntimeError):
            pass
        except (ValueError, HTTPException):
            await tunnel.close("Invalid tunnel message or inactive authorization")
        finally:
            await tunnel.close()
            if tunnels.get(node["node_id"]) is tunnel:
                tunnels.pop(node["node_id"], None)
            store.audit(now(), "offline", node)

    @app.websocket("/{path:path}")
    async def browser_ws(socket: WebSocket, path: str):
        tunnel = None
        correlation = None
        accepted = False
        try:
            service, local, public = route_path("/" + path, "GET")
            if service != "backend" or not local.startswith("/ws/"):
                raise HTTPException(403, "Only backend WebSocket routes are allowed")
            node, session = session_node(socket)
            if socket.headers.get("origin") and socket.headers["origin"] != origin(node["node_id"]):
                raise HTTPException(403, "Workspace Origin mismatch")
            tunnel = active_tunnel(node)
            if len(tunnel.browser) >= config.ws_concurrency:
                raise HTTPException(429, "Node WebSocket concurrency quota exceeded")
            correlation = secrets.token_hex(12)
            pipe = BrowserPipe(asyncio.get_running_loop().create_future())
            tunnel.browser[correlation] = pipe
            protocols = [
                item.strip() for item in socket.headers.get("sec-websocket-protocol", "").split(",") if item.strip()
            ]
            if len(protocols) > 16 or any(len(item) > 128 for item in protocols):
                raise HTTPException(400, "Too many WebSocket subprotocols")
            query = str(socket.url.query)
            protocol = await tunnel.exchange(
                {
                    "type": "ws.open",
                    "id": correlation,
                    **identity(node),
                    "service": "backend",
                    "method": "GET",
                    "path": local + ("?" + query if query else ""),
                    "headers": safe_headers([[k, v] for k, v in socket.headers.items()]),
                    "subprotocols": protocols,
                },
                pipe.accepted,
                config.request_timeout,
                authorize=lambda: session_node(socket),
            )
            if protocol is not None and protocol not in protocols:
                raise HTTPException(502, "Upstream selected an unknown subprotocol")
            valid_node(store.node(node["node_id"]))
            if session["expires"] <= now():
                raise HTTPException(401, "Browser workspace session expired")
            await socket.accept(subprotocol=protocol)
            accepted = True
            store.audit(now(), "ws.open", node)

            def check():
                valid_node(store.node(node["node_id"]))
                if session["expires"] <= now():
                    raise HTTPException(401, "Browser workspace session expired")

            async def browser_to_node():
                while True:
                    message = await socket.receive()
                    check()
                    if message["type"] == "websocket.disconnect":
                        return
                    payload = message.get("text")
                    binary = message.get("bytes")
                    size = len(payload.encode()) if payload is not None else len(binary or b"")
                    if size > config.frame_limit:
                        raise HTTPException(413, "WebSocket frame exceeds quota")
                    await tunnel.send(
                        {
                            "type": "ws.data",
                            "id": correlation,
                            "kind": "text" if payload is not None else "bytes",
                            "data": payload if payload is not None else base64.b64encode(binary or b"").decode(),
                        },
                        authorize=lambda: session_node(socket),
                    )

            async def node_to_browser():
                while True:
                    message = await pipe.queue.get()
                    check()
                    if message["type"] == "ws.close":
                        code = message.get("code", 1000)
                        code = (
                            code
                            if isinstance(code, int)
                            and (
                                code in {1000, 1001, 1002, 1003, 1007, 1008, 1009, 1010, 1011, 1012, 1013, 1014}
                                or 3000 <= code <= 4999
                            )
                            else 1000
                        )
                        await socket.close(code=code, reason=str(message.get("reason", ""))[:100])
                        return
                    if message["kind"] == "text":
                        await socket.send_text(message["data"])
                    else:
                        await socket.send_bytes(decode_body(message["data"], config.frame_limit))

            async def expiry_guard():
                while True:
                    await asyncio.sleep(0.25)
                    check()

            tasks = [asyncio.create_task(fn()) for fn in (browser_to_node, node_to_browser, expiry_guard)]
            try:
                done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    task.result()
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
        except (TimeoutError, HTTPException, ValueError):
            with contextlib.suppress(Exception):
                await socket.close(code=1008)
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            if tunnel and correlation:
                tunnel.browser.pop(correlation, None)
                if accepted:
                    store.audit(now(), "ws.close", node)
                if not tunnel.closed:
                    with contextlib.suppress(Exception):
                        await tunnel.send(
                            {"type": "ws.close", "id": correlation, "code": 1000, "reason": "Browser disconnected"}
                        )

    @app.api_route("/{path:path}", methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    async def proxy(request: Request, path: str):
        service, local, public = route_path("/" + path, request.method)
        node, session = session_node(request, public=public)
        if (
            not public
            and request.method not in {"GET", "HEAD", "OPTIONS"}
            and request.headers.get("origin")
            and request.headers["origin"] != origin(node["node_id"])
        ):
            raise HTTPException(403, "Workspace Origin mismatch")
        tunnel = active_tunnel(node)
        if len(tunnel.http) >= config.http_concurrency:
            raise HTTPException(429, "Node HTTP concurrency quota exceeded")
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > config.http_limit:
                raise HTTPException(413, "HTTP body exceeds quota")
        try:
            headers = safe_headers([[k, v] for k, v in request.headers.items()])
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        # Streaming the request body yields control; re-check before reserving a slot.
        valid_node(store.node(node["node_id"]))
        if session and session["expires"] <= now():
            raise HTTPException(401, "Browser workspace session expired")
        if len(tunnel.http) >= config.http_concurrency:
            raise HTTPException(429, "Node HTTP concurrency quota exceeded")
        correlation = secrets.token_hex(12)
        future = asyncio.get_running_loop().create_future()
        tunnel.http[correlation] = future
        tunnel.http_services[correlation] = service
        try:
            query = str(request.url.query)
            status, headers, output = await tunnel.exchange(
                {
                    "type": "http.request",
                    "id": correlation,
                    **identity(node),
                    "service": service,
                    "method": request.method,
                    "path": local + ("?" + query if query else ""),
                    "headers": headers,
                    "body": base64.b64encode(body).decode(),
                },
                future,
                config.request_timeout,
                authorize=lambda: session_node(request, public=public),
            )
            valid_node(store.node(node["node_id"]))
            if session and session["expires"] <= now():
                raise HTTPException(401, "Browser workspace session expired")
            media_type = next((v for k, v in headers if k == "content-type"), "")
            if service == "frontend" and "text/html" in media_type and request.method != "HEAD":
                bootstrap = (
                    "<script>window.__AMBIENT_REMOTE__="
                    + json.dumps({"apiBaseUrl": "/", "nodeId": node["node_id"]}, separators=(",", ":"))
                    + ";</script>"
                )
                text = output.decode("utf-8")
                text = text.replace("<head>", "<head>" + bootstrap, 1) if "<head>" in text else bootstrap + text
                output = text.encode("utf-8")
            response = Response(output, status_code=status)
            for name, value in headers:
                response.headers.append(name, value)
            response.headers["Cache-Control"] = "no-store"
            response.headers["Referrer-Policy"] = "no-referrer"
            store.audit(now(), "http." + service, node, status, len(output))
            return response
        except TimeoutError as exc:
            store.audit(now(), "http.timeout", node, 504)
            raise HTTPException(504, "Local workspace response timed out") from exc
        finally:
            tunnel.http.pop(correlation, None)
            tunnel.http_services.pop(correlation, None)

    return app

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
import hmac
import ipaddress
import math
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from urllib.parse import unquote, urlsplit

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse, Response, JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.requests import ClientDisconnect
from .safeguards import Resources, RateTable, validate_origins

COOKIE = "ambient_workspace"
SECURE_COOKIE = "__Host-ambient_workspace"
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
    request_timeout: float = 30.0
    pairing_ttl: int = 300
    launch_ttl: int = 60
    session_ttl: int = 3600
    max_nodes: int = 1000
    max_account_nodes: int = 10
    max_pending: int = 100
    max_account_pending: int = 3
    max_enrollments: int = 200
    max_account_enrollments: int = 3
    enrollment_ttl: int = 300
    global_http_concurrency: int = 64
    global_ws_concurrency: int = 64
    global_tunnel_concurrency: int = 32
    control_concurrency: int = 16
    control_body_limit: int = 16384
    buffer_bytes: int = 256 * 1024 * 1024
    queued_bytes: int = 8 * 1024 * 1024
    browser_queue_size: int = 4
    ws_max_queue: int = 2
    ws_send_timeout: float = 10.0
    source_rate: int = 10
    account_rate: int = 20
    account_read_rate: int = 120
    device_state_rate: int = 120
    device_rate: int = 60
    tunnel_rate: int = 1200
    tunnel_idle_timeout: float = 90.0
    max_launches: int = 1000
    max_sessions: int = 10000
    max_node_sessions: int = 100
    rate_window: int = 60
    rate_entries: int = 2048
    source_entries: int = 1024
    audit_max_rows: int = 10000
    audit_retention: int = 7 * 86400
    history_max_rows: int = 10000
    history_retention: int = 7 * 86400
    database_limit_bytes: int = 128 * 1024 * 1024
    maintenance_interval: int = 60
    control_host: str = "testserver"
    service_host: str = ""
    portal_origin: str = ""
    origin_mode: str = "separate-site"
    trusted_proxy_cidrs: str = ""

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
        self.control_host = self.control_host.lower()
        self.service_host = self.service_host.lower()
        if self.service_host and not re.fullmatch(r"[a-z0-9.-]+(?::[0-9]{1,5})?", self.service_host):
            raise ValueError("Invalid internal service host")
        if self.service_host.endswith("." + self.workspace_domain):
            raise ValueError("Internal service host cannot be a node host")
        if not self.secret.isascii() or len(self.secret) > 4096 or any(ord(c) < 32 for c in self.secret):
            raise ValueError("Service secret must be printable ASCII")
        if self.scheme == "https" and len(self.secret) < 32:
            raise ValueError("Production service secret must contain at least 32 characters")
        if not re.fullmatch(r"[a-z0-9.-]+(?::[0-9]{1,5})?", self.control_host):
            raise ValueError("Invalid control host")
        validate_origins(self.workspace_domain, self.scheme, self.control_host, self.portal_origin, self.origin_mode)
        for field_name in self.__dataclass_fields__:
            value = getattr(self, field_name)
            if isinstance(value, (int, float)) and (isinstance(value, bool) or not math.isfinite(value) or value <= 0):
                raise ValueError(f"{field_name} must be positive")
            default = self.__dataclass_fields__[field_name].default
            if isinstance(default, int) and not isinstance(value, int):
                raise ValueError(f"{field_name} must be an integer")
        if self.frame_limit > 256 * 1024 or self.http_limit > 2 * 1024 * 1024:
            raise ValueError("HTTP/frame limits cannot exceed the connector protocol limits")
        if self.enrollment_ttl > 300 or self.pairing_ttl > 300 or self.browser_queue_size > 8 or self.ws_max_queue > 4:
            raise ValueError("Enrollment/pairing TTL and queue sizes exceed supported safety limits")
        if self.queued_bytes > self.buffer_bytes or self.database_limit_bytes < 16 * 1024 * 1024:
            raise ValueError("Invalid buffer or database budget")
        for cidr in self.trusted_proxy_cidrs.split(","):
            if cidr.strip():
                ipaddress.ip_network(cidr.strip(), strict=True)

    @classmethod
    def from_env(cls):
        defaults = cls.__dataclass_fields__
        aliases = {"workspace_domain": "DOMAIN"}
        values = {}
        for name, item in defaults.items():
            raw = os.getenv("WORKSPACE_GATEWAY_" + aliases.get(name, name.upper()))
            if raw is not None:
                values[name] = type(item.default)(raw)
        public_url = os.getenv("WORKSPACE_GATEWAY_PUBLIC_URL")
        if public_url:
            parsed = urlsplit(public_url)
            if (parsed.scheme != values.get("scheme", "http") or not parsed.netloc or parsed.username
                    or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
                raise ValueError("Invalid gateway public URL")
            values.setdefault("control_host", parsed.netloc.lower())
            if values["control_host"] != parsed.netloc.lower():
                raise ValueError("Gateway control host and public URL differ")
        elif "control_host" not in values:
            values["control_host"] = values.get("workspace_domain", "localhost:8090")
        return cls(**values)


class PairBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    enrollment_token: str = Field(min_length=20, max_length=128)
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


class EnrollmentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(min_length=1, max_length=200)


class Store:
    def __init__(self, path: str, config: GatewayConfig):
        self.config = config
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA auto_vacuum=INCREMENTAL")
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
            CREATE TABLE IF NOT EXISTS enrollments (token_hash TEXT PRIMARY KEY, account_id TEXT NOT NULL,
                label TEXT NOT NULL, expires REAL NOT NULL, created REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS enrollments_account ON enrollments(account_id);
        """)
        columns = {row[1] for row in self.db.execute("PRAGMA table_info(nodes)")}
        if "enrollment_hash" not in columns:
            self.db.execute("ALTER TABLE nodes ADD COLUMN enrollment_hash TEXT")
            # Old paired identities and grants survive. Old pending/claimed entries
            # cannot bypass the new, account-bound enrollment admission.
            self.db.execute("UPDATE nodes SET pairing_expires=0 WHERE status IN ('pending','claimed')")
        if self.db.execute("PRAGMA auto_vacuum").fetchone()[0] != 2:
            self.db.execute("PRAGMA auto_vacuum=INCREMENTAL")
            self.db.execute("VACUUM")
        columns = {row[1] for row in self.db.execute("PRAGMA table_info(nodes)")}
        if "retired" not in columns:
            self.db.execute("ALTER TABLE nodes ADD COLUMN retired REAL")
            self.db.execute("UPDATE nodes SET retired=? WHERE status IN ('revoked','expired')", (time.time(),))
        self.db.execute("CREATE INDEX IF NOT EXISTS nodes_status ON nodes(status,account_id)")
        self.db.execute("CREATE INDEX IF NOT EXISTS audit_timestamp ON audit(timestamp)")
        page_size = self.db.execute("PRAGMA page_size").fetchone()[0]
        desired_pages = config.database_limit_bytes // page_size
        if self.db.execute(f"PRAGMA max_page_count={desired_pages}").fetchone()[0] > desired_pages:
            raise ValueError("Existing state exceeds database budget; increase budget without resetting identities")
        self.last_maintenance = 0

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
        self.db.execute("DELETE FROM audit WHERE timestamp<=?", (now - self.config.audit_retention,))
        self.db.execute("DELETE FROM audit WHERE id IN (SELECT id FROM audit ORDER BY id DESC LIMIT -1 OFFSET ?)",
                        (self.config.audit_max_rows,))

    def maintain(self, now, force=False):
        self.db.execute("DELETE FROM enrollments WHERE expires<=?", (now,))
        self.db.execute("DELETE FROM launches WHERE expires<=?", (now,))
        self.db.execute("DELETE FROM sessions WHERE expires<=?", (now,))
        self.db.execute("UPDATE nodes SET status='expired',pairing_hash=NULL,retired=coalesce(retired,?) WHERE status NOT IN ('revoked','expired') AND "
                        "(expires<=? OR (status IN ('pending','claimed') AND pairing_expires<=?))", (now, now, now))
        if not force and now - self.last_maintenance < self.config.maintenance_interval:
            return
        self.last_maintenance = now
        self.db.execute("DELETE FROM audit WHERE timestamp<=?", (now - self.config.audit_retention,))
        history = [row[0] for row in self.db.execute("SELECT node_id FROM nodes WHERE status IN ('revoked','expired') "
                    "AND (retired<=? OR node_id IN (SELECT node_id FROM nodes WHERE status IN ('revoked','expired') "
                    "ORDER BY created DESC,node_id DESC LIMIT -1 OFFSET ?))",
                    (now - self.config.history_retention, self.config.history_max_rows))]
        for node_id in history:
            self.db.execute("DELETE FROM launches WHERE node_id=?", (node_id,))
            self.db.execute("DELETE FROM sessions WHERE node_id=?", (node_id,))
            self.db.execute("DELETE FROM nodes WHERE node_id=?", (node_id,))
        # Permanent deleted_accounts tombstones are intentionally never garbage collected.
        self.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        self.db.execute("PRAGMA incremental_vacuum(256)")


@dataclass
class BrowserPipe:
    accepted: asyncio.Future
    resources: Resources
    maximum: int
    queue: asyncio.Queue = field(init=False)

    def __post_init__(self):
        self.queue = asyncio.Queue(maxsize=self.maximum)

    def put(self, message):
        if self.queue.full():
            self.resources.metrics["backpressure_closes"] += 1
            raise ValueError("Browser WebSocket backpressure quota exceeded")
        size = 4 * len(json.dumps(message, separators=(",", ":"), ensure_ascii=False).encode()) + 512
        self.resources.queue_charge(size)
        self.queue.put_nowait((message, size))

    def clear(self):
        while not self.queue.empty():
            _, size = self.queue.get_nowait()
            self.resources.queue_release(size)

    def shutdown(self, revoked, reason):
        self.clear()
        self.queue.put_nowait(({"type": "ws.close", "code": 1008 if revoked else 1012, "reason": reason}, 0))


@dataclass
class Tunnel:
    socket: WebSocket
    node_id: str
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    http: dict[str, asyncio.Future] = field(default_factory=dict)
    http_services: dict[str, str] = field(default_factory=dict)
    browser: dict[str, BrowserPipe] = field(default_factory=dict)
    closed: bool = False
    send_timeout: float = 10

    async def send(self, message, authorize=None):
        async with asyncio.timeout(self.send_timeout):
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
            pipe.shutdown(revoked, reason)
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
        "/vendor/babel.min.js",
        "/vendor/htm-preact.js",
    }:
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
    store = Store(config.database, config)
    tunnels: dict[str, Tunnel] = {}
    resources = Resources(config)
    sources = RateTable(config.source_entries, config.rate_window)
    accounts = RateTable(config.rate_entries, config.rate_window)
    devices = RateTable(config.rate_entries, config.rate_window)
    proxies = [ipaddress.ip_network(item.strip()) for item in config.trusted_proxy_cidrs.split(",") if item.strip()]
    cookie_name = SECURE_COOKIE if config.scheme == "https" else COOKIE

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

    def control_host(connection, *, service=False):
        host = connection.headers.get("host", "").lower().rstrip(".")
        allowed = host == config.control_host
        if service and config.service_host:
            allowed = allowed or host == config.service_host
        if host_node(connection) is not None or not allowed:
            raise HTTPException(404, "Control routes are unavailable on this host")

    def auth_secret(request):
        control_host(request, service=True)
        if not secrets.compare_digest(request.headers.get("authorization", ""), "Bearer " + config.secret):
            raise HTTPException(401, "Service authentication required")
        if not request.scope.get("gateway_account_rate"):
            parts = request.url.path.split("/")
            account = parts[3] if len(parts) > 3 and parts[2] == "accounts" else "metrics"
            if len(account) > 200:
                raise HTTPException(422, "Invalid account")
            limit = config.account_read_rate if request.method == "GET" else config.account_rate
            category = "read" if request.method == "GET" else "action"
            if not accounts.allow(digest(account) + category, now(), limit):
                resources.metrics["rate_rejections"] += 1
                raise HTTPException(429, "Account request rate exceeded")
            request.scope["gateway_account_rate"] = True

    def device_node(request):
        control_host(request)
        value = request.headers.get("authorization", "")
        if not value.startswith("Bearer ") or len(value) > 300:
            raise HTTPException(401, "Device authentication required")
        node = store.one("SELECT * FROM nodes WHERE token_hash=?", (digest(value[7:]),))
        if not node:
            raise HTTPException(401, "Invalid device credentials")
        if not request.scope.get("gateway_device_rate"):
            category = "state" if request.url.path.endswith("/state") else "action"
            limit = config.device_state_rate if category == "state" else config.device_rate
            if not devices.allow(node["node_id"] + category, now(), limit):
                resources.metrics["rate_rejections"] += 1
                raise HTTPException(429, "Device request rate exceeded")
            request.scope["gateway_device_rate"] = True
        return node

    def node_status(node):
        if node["status"] == "revoked" or (
            node["account_id"]
            and store.one("SELECT account_id FROM deleted_accounts WHERE account_id=?", (node["account_id"],))
        ):
            return "revoked"
        if node["expires"] <= now() or (node["status"] in {"pending", "claimed"} and node["pairing_expires"] <= now()):
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
            cookie = connection.cookies.get(cookie_name, "")
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
        changed = store.db.execute("UPDATE nodes SET status='revoked',pairing_hash=NULL,retired=? WHERE node_id=? AND status!='revoked'", (now(), node["node_id"])).rowcount
        store.db.execute("DELETE FROM sessions WHERE node_id=?", (node["node_id"],))
        store.db.execute("DELETE FROM launches WHERE node_id=?", (node["node_id"],))
        if changed:
            store.audit(now(), "revoke", node)
        if tunnel := tunnels.get(node["node_id"]):
            await tunnel.close("Workspace authorization revoked", revoked=True)
        return serialize(store.node(node["node_id"]))

    async def sweep():
        while True:
            await asyncio.sleep(0.25)
            for node_id, tunnel in list(tunnels.items()):
                current = store.node(node_id)
                if current is None or node_status(current) != "paired":
                    await tunnel.close("Workspace authorization expired", revoked=True)
            store.maintain(now())

    @asynccontextmanager
    async def lifespan(application):
        store.maintain(now(), force=True)
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
    app.state.resources = resources
    app.state.sources = sources
    app.state.accounts = accounts
    app.state.devices = devices

    def source_key(request):
        peer = request.client.host if request.client else "unknown"
        try:
            address = ipaddress.ip_address(peer)
        except ValueError:
            return digest(peer)
        if any(address in network for network in proxies):
            forwarded = request.headers.get("x-real-ip", "")
            try:
                address = ipaddress.ip_address(forwarded)
            except ValueError:
                pass
        return digest(str(address))

    class Boundary:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope["type"] != "http":
                await self.app(scope, receive, send)
                return
            request = Request(scope, receive=receive)
            lease, started = None, False
            received = 0

            async def tracked_send(message):
                nonlocal started
                if message["type"] == "http.response.start":
                    started = True
                await send(message)

            async def bounded_receive():
                nonlocal received
                message = await receive()
                if message["type"] == "http.request":
                    chunk = message.get("body", b"")
                    received += len(chunk)
                    ceiling = config.http_limit if lease.kind == "http" else config.control_body_limit
                    if received > ceiling:
                        raise HTTPException(413, "HTTP body exceeds quota")
                    if chunk and request.method in {"GET", "HEAD"}:
                        raise HTTPException(413, "GET and HEAD bodies are not supported")
                return message

            try:
                if (len(scope.get("headers", [])) > 100 or
                        sum(len(a) + len(b) for a, b in scope.get("headers", [])) > 32768):
                    raise HTTPException(400, "Headers exceed quota")
                if len(scope.get("query_string", b"")) > 8192:
                    raise HTTPException(414, "Query exceeds quota")
                # Reject declared GET/HEAD bodies before touching the receive stream.
                length = request.headers.get("content-length", "0")
                if not length.isdecimal() or len(length) > 20:
                    raise HTTPException(400, "Invalid content length")
                if request.method in {"GET", "HEAD"} and (int(length) or request.headers.get("transfer-encoding")):
                    raise HTTPException(413, "GET and HEAD bodies are not supported")
                node_id = host_node(request)
                if node_id is None:
                    service_route = request.url.path.startswith("/v1/accounts/") or request.url.path == "/v1/metrics"
                    control_host(request, service=service_route)
                    if service_route:
                        auth_secret(request)
                    elif request.url.path.startswith("/v1/connector/") and request.url.path != "/v1/connector/pairings":
                        device_node(request)
                    elif request.url.path == "/v1/connector/pairings":
                        if not sources.allow(source_key(request), now(), config.source_rate):
                            resources.metrics["rate_rejections"] += 1
                            raise HTTPException(429, "Pairing source rate exceeded")
                    lease = resources.acquire("control")
                elif request.url.path == "/_ambient/launch":
                    lease = resources.acquire("control")
                else:
                    _, _, public = route_path(request.url.path, request.method)
                    node, _ = session_node(request, public=public)
                    active_tunnel(node)
                    lease = resources.acquire("http", node["node_id"])
                if int(length) > (config.http_limit if lease.kind == "http" else config.control_body_limit):
                    raise HTTPException(413, "HTTP body exceeds quota")
                async with asyncio.timeout(config.request_timeout):
                    await self.app(scope, bounded_receive, tracked_send)
            except HTTPException as exc:
                if started:
                    raise
                headers = {"Retry-After": str(config.rate_window)} if exc.status_code == 429 else None
                await JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=headers)(scope, receive, send)
            except TimeoutError:
                resources.metrics["body_timeouts"] += 1
                if started:
                    raise
                await JSONResponse({"detail": "Workspace request timed out"}, status_code=504)(scope, receive, send)
            except ClientDisconnect:
                if not started:
                    await JSONResponse({"detail": "Browser disconnected"}, status_code=499)(scope, receive, send)
            except sqlite3.Error:
                if started:
                    raise
                await JSONResponse({"detail": "Gateway state storage unavailable"}, status_code=503,
                                   headers={"Retry-After": "5"})(scope, receive, send)
            finally:
                resources.release(lease)

    app.add_middleware(Boundary)

    @app.get("/health")
    async def health(request: Request):
        control_host(request)
        return {"status": "ok"}

    @app.get("/v1/metrics")
    async def metrics(request: Request):
        auth_secret(request)
        return resources.snapshot()

    @app.post("/v1/accounts/{account_id}/enrollments")
    async def enrollment(request: Request, account_id: str, body: EnrollmentBody):
        auth_secret(request)
        if store.one("SELECT account_id FROM deleted_accounts WHERE account_id=?", (account_id,)):
            raise HTTPException(410, "Account has been deleted")
        stamp = now()
        store.maintain(stamp)
        count = store.one("SELECT count(*) n FROM enrollments")["n"]
        owned = store.one("SELECT count(*) n FROM enrollments WHERE account_id=?", (account_id,))["n"]
        if count >= config.max_enrollments or owned >= config.max_account_enrollments:
            raise HTTPException(429, "Enrollment capacity reached", headers={"Retry-After": str(config.rate_window)})
        token = secrets.token_urlsafe(48)
        expires = stamp + config.enrollment_ttl
        store.db.execute("INSERT INTO enrollments VALUES(?,?,?,?,?)", (digest(token), account_id, body.label, expires, stamp))
        return {"enrollment_token": token, "expires_at": iso(expires)}

    @app.post("/v1/connector/pairings")
    async def pair(request: Request, body: PairBody):
        control_host(request)
        if (
            not set(body.scopes) <= SCOPES
            or "workspace.control" not in body.scopes
            or len(set(body.scopes)) != len(body.scopes)
        ):
            raise HTTPException(422, "Unknown or duplicate workspace scope")
        stamp = now()
        store.maintain(stamp)
        enrollment_hash = digest(body.enrollment_token)
        approved_enrollment = store.one("SELECT * FROM enrollments WHERE token_hash=? AND expires>?", (enrollment_hash, stamp))
        if not approved_enrollment:
            raise HTTPException(409, "Enrollment expired or already used")
        account_id = approved_enrollment["account_id"]
        if store.one("SELECT account_id FROM deleted_accounts WHERE account_id=?", (account_id,)):
            raise HTTPException(410, "Account has been deleted")
        if not accounts.allow(digest(account_id) + "pair", stamp, config.account_rate):
            raise HTTPException(429, "Account pairing rate exceeded", headers={"Retry-After": str(config.rate_window)})
        active_sql = "status IN ('pending','claimed','paired')"
        if (store.one("SELECT count(*) n FROM nodes WHERE " + active_sql)["n"] >= config.max_nodes
                or store.one("SELECT count(*) n FROM nodes WHERE account_id=? AND " + active_sql, (account_id,))["n"] >= config.max_account_nodes
                or store.one("SELECT count(*) n FROM nodes WHERE status IN ('pending','claimed')")["n"] >= config.max_pending
                or store.one("SELECT count(*) n FROM nodes WHERE account_id=? AND status IN ('pending','claimed')", (account_id,))["n"] >= config.max_account_pending):
            raise HTTPException(429, "Gateway node capacity reached", headers={"Retry-After": str(config.rate_window)})
        node_id, token, code, grant = (
            secrets.token_hex(12),
            secrets.token_urlsafe(48),
            secrets.token_urlsafe(18),
            secrets.token_hex(16),
        )
        store.db.execute("BEGIN IMMEDIATE")
        try:
            if store.db.execute("DELETE FROM enrollments WHERE token_hash=? AND expires>?", (enrollment_hash, stamp)).rowcount != 1:
                raise HTTPException(409, "Enrollment expired or already used")
            store.db.execute(
            "INSERT INTO nodes(node_id,name,token_hash,pairing_hash,pairing_expires,status,grant_id,scopes,expires,created,account_id,enrollment_hash) VALUES(?,?,?,?,?,'pending',?,?,?,?,?,?)",
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
                account_id,
                enrollment_hash,
            ),
            )
            store.db.execute("COMMIT")
        except BaseException:
            store.db.execute("ROLLBACK")
            raise
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
        if node["account_id"] != account_id or not node.get("enrollment_hash"):
            raise HTTPException(409, "Pairing is bound to a different account")
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
    async def nodes(request: Request, account_id: str, limit: int = 50, cursor: str = "", view: str = "active"):
        auth_secret(request)
        if not 1 <= limit <= 100 or view not in {"active", "history"} or len(cursor) > 2048:
            raise HTTPException(422, "Invalid node page")
        store.maintain(now())
        args = [account_id]
        condition = "status IN ('pending','claimed','paired')" if view == "active" else "status IN ('revoked','expired')"
        if cursor:
            try:
                if not re.fullmatch(r"[A-Za-z0-9_-]+", cursor):
                    raise ValueError()
                decoded = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
                raw, signature = decoded[:-32], decoded[-32:]
                if not hmac.compare_digest(signature, hmac.digest(config.secret.encode(), raw, "sha256")):
                    raise ValueError()
                owner, cursor_view, created, node_id = json.loads(raw)
                if owner != account_id or cursor_view != view or not isinstance(created, (int, float)) or not math.isfinite(created) or not NODE_RE.fullmatch(node_id):
                    raise ValueError()
            except (ValueError, TypeError, json.JSONDecodeError):
                raise HTTPException(422, "Invalid node cursor")
            condition += " AND (created<? OR (created=? AND node_id<?))"
            args.extend([created, created, node_id])
        args.append(limit + 1)
        selected = [dict(row) for row in store.db.execute("SELECT * FROM nodes WHERE account_id=? AND " + condition + " ORDER BY created DESC,node_id DESC LIMIT ?", args)]
        next_cursor = None
        if len(selected) > limit:
            last = selected[limit-1]
            raw = json.dumps([account_id, view, last["created"], last["node_id"]], separators=(",", ":")).encode()
            next_cursor = base64.urlsafe_b64encode(raw + hmac.digest(config.secret.encode(), raw, "sha256")).decode().rstrip("=")
        return {"nodes": [serialize(node) for node in selected[:limit]], "next_cursor": next_cursor}

    @app.post("/v1/accounts/{account_id}/nodes/{node_id}/launch")
    async def launch(request: Request, account_id: str, node_id: str):
        auth_secret(request)
        node = account_node(account_id, node_id)
        valid_node(node)
        active_tunnel(node)
        token, expires = secrets.token_urlsafe(32), min(now() + config.launch_ttl, node["expires"])
        store.maintain(now())
        if store.one("SELECT count(*) n FROM launches")["n"] >= config.max_launches:
            raise HTTPException(429, "Launch capacity reached", headers={"Retry-After": str(config.rate_window)})
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
        # Mark every authorization atomically before the first socket-close await.
        store.db.execute("BEGIN IMMEDIATE")
        try:
            for node in selected:
                store.db.execute("UPDATE nodes SET status='revoked',pairing_hash=NULL,retired=? WHERE node_id=?", (now(), node["node_id"]))
                store.audit(now(), "revoke", node)
            store.db.execute("DELETE FROM enrollments WHERE account_id=?", (account_id,))
            store.db.execute("COMMIT")
        except BaseException:
            store.db.execute("ROLLBACK")
            raise
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
        store.maintain(now())
        if (store.one("SELECT count(*) n FROM sessions")["n"] >= config.max_sessions
                or store.one("SELECT count(*) n FROM sessions WHERE node_id=?", (node_id,))["n"] >= config.max_node_sessions):
            raise HTTPException(429, "Session capacity reached", headers={"Retry-After": str(config.rate_window)})
        if store.db.execute("DELETE FROM launches WHERE token_hash=?", (digest(ticket),)).rowcount != 1:
            raise HTTPException(401, "Launch link already used")
        token, expires = secrets.token_urlsafe(32), min(now() + config.session_ttl, node["expires"])
        store.db.execute("INSERT INTO sessions VALUES(?,?,?,?)", (digest(token), node_id, node["grant_id"], expires))
        store.audit(now(), "session", node)
        response = RedirectResponse(
            "/", status_code=303, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}
        )
        response.set_cookie(
            cookie_name,
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
        lease = None
        tunnel = None
        try:
            try:
                node = device_node(socket)
                valid_node(node)
                lease = resources.acquire("tunnel", node["node_id"])
                await asyncio.wait_for(socket.accept(), config.request_timeout)
            except (HTTPException, WebSocketDisconnect, RuntimeError, TimeoutError):
                resources.release(lease)
                with contextlib.suppress(Exception):
                    await socket.close(code=1008)
                return
            tunnel = Tunnel(socket, node["node_id"], send_timeout=config.ws_send_timeout)
            previous = tunnels.get(node["node_id"])
            if previous:
                await previous.close("Connector replaced by a new connection")
            tunnels[node["node_id"]] = tunnel
            try:
                store.db.execute("UPDATE nodes SET last_seen=? WHERE node_id=?", (now(), node["node_id"]))
                store.audit(now(), "online", node)
                await tunnel.send({"type": "hello", **identity(node)})
                while True:
                    wire = await asyncio.wait_for(socket.receive_text(), config.tunnel_idle_timeout)
                    if not devices.allow(node["node_id"] + "wire", now(), config.tunnel_rate):
                        raise ValueError("Tunnel message rate exceeded")
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
                            cleaned = ({"type": "ws.data", "kind": message["kind"], "data": message["data"]}
                                       if kind == "ws.data" else {"type": "ws.close", "code": message.get("code", 1000),
                                                                "reason": str(message.get("reason", ""))[:100]})
                            pipe.put(cleaned)
                    elif kind not in {"http.response", "ws.accept", "ws.data", "ws.close", "pong"}:
                        raise ValueError("Unknown tunnel message type")
            except (WebSocketDisconnect, RuntimeError):
                pass
            except (ValueError, HTTPException, TimeoutError, sqlite3.Error):
                await tunnel.close("Invalid tunnel message, timeout or inactive authorization")
            finally:
                await tunnel.close()
                if tunnels.get(node["node_id"]) is tunnel:
                    tunnels.pop(node["node_id"], None)
                resources.release(lease)
                store.audit(now(), "offline", node)

        finally:
            # Covers cancellation in accept, connector replacement, runtime and close.
            resources.release(lease)
            if tunnel is not None:
                if tunnels.get(tunnel.node_id) is tunnel:
                    tunnels.pop(tunnel.node_id, None)
                await tunnel.close()

    @app.websocket("/{path:path}")
    async def browser_ws(socket: WebSocket, path: str):
        tunnel = None
        correlation = None
        accepted = False
        lease = None
        pipe = None
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
            lease = resources.acquire("ws", node["node_id"])
            correlation = secrets.token_hex(12)
            pipe = BrowserPipe(asyncio.get_running_loop().create_future(), resources, config.browser_queue_size)
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
                    message, charge = await pipe.queue.get()
                    try:
                        await relay_message(message)
                    finally:
                        resources.queue_release(charge)
                    if message["type"] == "ws.close":
                        return

            async def relay_message(message):
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
                    await asyncio.wait_for(socket.send_text(message["data"]), config.ws_send_timeout)
                else:
                    await asyncio.wait_for(socket.send_bytes(decode_body(message["data"], config.frame_limit)), config.ws_send_timeout)

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
            resources.release(lease)
            if pipe:
                pipe.clear()
                if not pipe.accepted.done():
                    pipe.accepted.cancel()
                elif not pipe.accepted.cancelled():
                    pipe.accepted.exception()
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
        if (not public and request.method not in {"GET", "HEAD", "OPTIONS"}
                and request.headers.get("origin") and request.headers["origin"] != origin(node["node_id"])):
            raise HTTPException(403, "Workspace Origin mismatch")
        tunnel = active_tunnel(node)
        try:
            headers = safe_headers([[k, v] for k, v in request.headers.items()])
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        # Boundary has atomically reserved both node/global slots and the buffer
        # budget before any receive. Keep the correlation bounded throughout upload.
        correlation = secrets.token_hex(12)
        future = asyncio.get_running_loop().create_future()
        tunnel.http[correlation] = future
        tunnel.http_services[correlation] = service
        exchange = disconnected = None
        try:
            body = bytearray()
            if request.method not in {"GET", "HEAD"}:
                async for chunk in request.stream():
                    if len(body) + len(chunk) > config.http_limit:
                        raise HTTPException(413, "HTTP body exceeds quota")
                    body.extend(chunk)
            valid_node(store.node(node["node_id"]))
            if session and session["expires"] <= now():
                raise HTTPException(401, "Browser workspace session expired")
            query = str(request.url.query)
            exchange = asyncio.create_task(tunnel.exchange(
                {"type": "http.request", "id": correlation, **identity(node), "service": service,
                 "method": request.method, "path": local + ("?" + query if query else ""),
                 "headers": headers, "body": base64.b64encode(body).decode()},
                future, config.request_timeout,
                authorize=lambda: session_node(request, public=public)))
            # Once upload has completed, observe disconnect while waiting for the
            # connector. Closing a tab releases admission immediately.
            async def watch_disconnect():
                while True:
                    message = await request.receive()
                    if message["type"] == "http.disconnect":
                        return
            disconnected = asyncio.create_task(watch_disconnect())
            done, _ = await asyncio.wait([exchange, disconnected], return_when=asyncio.FIRST_COMPLETED)
            if exchange not in done:
                raise HTTPException(499, "Browser disconnected")
            status, headers, output = exchange.result()
            valid_node(store.node(node["node_id"]))
            if session and session["expires"] <= now():
                raise HTTPException(401, "Browser workspace session expired")
            media_type = next((v for k, v in headers if k == "content-type"), "")
            if service == "frontend" and "text/html" in media_type and request.method != "HEAD":
                bootstrap = ("<script>window.__AMBIENT_REMOTE__="
                    + json.dumps({"apiBaseUrl": "/", "nodeId": node["node_id"]}, separators=(",", ":"))
                    + ";</script>")
                try:
                    text = output.decode("utf-8")
                except UnicodeError as exc:
                    raise HTTPException(502, "Frontend HTML must use UTF-8") from exc
                text = text.replace("<head>", "<head>" + bootstrap, 1) if "<head>" in text else bootstrap + text
                output = text.encode("utf-8")
                if len(output) > config.http_limit:
                    raise HTTPException(502, "Rewritten frontend exceeds quota")
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
            tasks = [task for task in (exchange, disconnected) if task is not None]
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            tunnel.http.pop(correlation, None)
            tunnel.http_services.pop(correlation, None)
            if not future.done():
                future.cancel()
            elif not future.cancelled():
                future.exception()

    return app

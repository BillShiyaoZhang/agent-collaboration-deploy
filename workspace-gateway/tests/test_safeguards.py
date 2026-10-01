import asyncio
import json
import sqlite3
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from workspace_gateway.app import BrowserPipe, GatewayConfig, create_app, digest
from workspace_gateway.domains import normalize_hostname, registrable_domain, validate_origins
from workspace_gateway.safeguards import RateTable, Resources
from test_gateway import SERVICE, enrollment_token, setup_node


def make_app(tmp_path, **kwargs):
    cfg = GatewayConfig(database=str(tmp_path / "state.sqlite3"), secret="test-service-secret", **kwargs)
    return create_app(cfg)


def test_enrollment_required_single_use_expiry_and_owner(tmp_path):
    app = make_app(tmp_path)
    with TestClient(app) as client:
        assert client.post("/v1/connector/pairings", json={"name": "x"}).status_code == 422
        assert app.state.store.one("SELECT count(*) n FROM nodes")["n"] == 0
        assert client.post("/v1/accounts/alice/enrollments", json={"label": "x"}).status_code == 401
        token = enrollment_token(client)
        paired = client.post("/v1/connector/pairings", json={"name": "x", "enrollment_token": token})
        assert paired.status_code == 200
        assert client.post("/v1/connector/pairings", json={"name": "x", "enrollment_token": token}).status_code == 409
        code = paired.json()["pairing_code"]
        assert client.post("/v1/accounts/bob/pairings/claim", headers=SERVICE,
                           json={"code": code, "label": "bob"}).status_code == 409
        assert client.post("/v1/accounts/alice/pairings/claim", headers=SERVICE,
                           json={"code": code, "label": "alice"}).status_code == 200
        late = enrollment_token(client, "bob")
        stamp = app.state.clock()
        app.state.clock = lambda: stamp + 301
        assert client.post("/v1/connector/pairings", json={"name": "x", "enrollment_token": late}).status_code == 409
        assert app.state.store.one("SELECT count(*) n FROM nodes")["n"] == 1


def test_pending_capacity_recovers_and_429_preserves_ticket(tmp_path):
    app = make_app(tmp_path, max_pending=1)
    with TestClient(app) as client:
        first = enrollment_token(client)
        assert client.post("/v1/connector/pairings", json={"name": "x", "enrollment_token": first}).status_code == 200
        second = enrollment_token(client, "bob")
        denied = client.post("/v1/connector/pairings", json={"name": "y", "enrollment_token": second})
        assert denied.status_code == 429 and denied.headers["retry-after"] == "60"
        assert app.state.store.one("SELECT token_hash FROM enrollments WHERE token_hash=?", (digest(second),))
        # Make the first pairing expire while the second enrollment remains valid.
        app.state.store.db.execute("UPDATE nodes SET pairing_expires=0")
        assert client.post("/v1/connector/pairings", json={"name": "y", "enrollment_token": second}).status_code == 200
        assert client.get("/v1/accounts/alice/nodes?view=history", headers=SERVICE).json()["nodes"][0]["status"] == "expired"


def test_enrollment_global_and_account_limits_and_deleted_account(tmp_path):
    app = make_app(tmp_path, max_enrollments=2, max_account_enrollments=1)
    with TestClient(app) as client:
        enrollment_token(client)
        assert client.post("/v1/accounts/alice/enrollments", headers=SERVICE, json={"label": "x"}).status_code == 429
        enrollment_token(client, "bob")
        assert client.post("/v1/accounts/carol/enrollments", headers=SERVICE, json={"label": "x"}).status_code == 429
        assert client.delete("/v1/accounts/alice", headers=SERVICE).status_code == 200
        assert client.post("/v1/accounts/alice/enrollments", headers=SERVICE, json={"label": "x"}).status_code == 410


def test_global_active_and_per_account_node_limits_recover(tmp_path):
    app = make_app(tmp_path, max_nodes=2, max_account_nodes=1)
    with TestClient(app) as client:
        first, _, _ = setup_node(client)
        token = enrollment_token(client)
        assert client.post("/v1/connector/pairings", json={"name": "x", "enrollment_token": token}).status_code == 429
        setup_node(client, "bob")
        other = enrollment_token(client, "carol")
        assert client.post("/v1/connector/pairings", json={"name": "x", "enrollment_token": other}).status_code == 429
        client.delete(f"/v1/accounts/alice/nodes/{first['node_id']}", headers=SERVICE)
        assert client.post("/v1/connector/pairings", json={"name": "x", "enrollment_token": token}).status_code == 200


def test_revoke_audit_idempotency_retention_and_permanent_tombstone(tmp_path):
    app = make_app(tmp_path, audit_max_rows=5, audit_retention=60, history_retention=60)
    with TestClient(app) as client:
        paired, device, _ = setup_node(client)
        endpoint = f"/v1/accounts/alice/nodes/{paired['node_id']}"
        assert client.delete(endpoint, headers=SERVICE).status_code == 200
        db = app.state.store.db
        count = db.execute("SELECT count(*) FROM audit WHERE event='revoke'").fetchone()[0]
        assert client.delete(endpoint, headers=SERVICE).status_code == 200
        assert client.post("/v1/connector/revoke", headers=device).status_code == 200
        assert db.execute("SELECT count(*) FROM audit WHERE event='revoke'").fetchone()[0] == count == 1
        client.delete("/v1/accounts/alice", headers=SERVICE)
        for _ in range(10):
            app.state.store.audit(app.state.clock(), "test")
        assert db.execute("SELECT count(*) FROM audit").fetchone()[0] == 5
        app.state.clock = lambda: time.time() + 100
        app.state.store.maintain(app.state.clock(), force=True)
        assert db.execute("SELECT count(*) FROM audit").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM nodes").fetchone()[0] == 0
        assert db.execute("SELECT account_id FROM deleted_accounts").fetchone()[0] == "alice"


def test_pagination_is_stable_opaque_owner_bound_and_history_separate(tmp_path):
    app = make_app(tmp_path)
    with TestClient(app) as client:
        for _ in range(3):
            setup_node(client)
        first = client.get("/v1/accounts/alice/nodes?limit=2", headers=SERVICE).json()
        assert len(first["nodes"]) == 2 and first["next_cursor"]
        cursor = first["next_cursor"]
        second = client.get("/v1/accounts/alice/nodes", params={"limit": 2, "cursor": cursor}, headers=SERVICE).json()
        assert len(second["nodes"]) == 1 and second["next_cursor"] is None
        assert not {n["node_id"] for n in first["nodes"]} & {n["node_id"] for n in second["nodes"]}
        assert client.get("/v1/accounts/bob/nodes", params={"cursor": cursor}, headers=SERVICE).status_code == 422
        assert client.get("/v1/accounts/alice/nodes", params={"view": "history", "cursor": cursor}, headers=SERVICE).status_code == 422
        assert client.get("/v1/accounts/alice/nodes?limit=101", headers=SERVICE).status_code == 422
        client.delete(f"/v1/accounts/alice/nodes/{second['nodes'][0]['node_id']}", headers=SERVICE)
        assert len(client.get("/v1/accounts/alice/nodes?view=history", headers=SERVICE).json()["nodes"]) == 1


def test_source_rate_and_source_table_are_bounded_and_spoofed_header_is_ignored(tmp_path):
    app = make_app(tmp_path, source_rate=1)
    with TestClient(app) as client:
        token = enrollment_token(client)
        first = client.post("/v1/connector/pairings", headers={"X-Real-IP": "1.1.1.1"},
                            json={"name": "x", "enrollment_token": token})
        assert first.status_code == 200
        other = enrollment_token(client, "bob")
        assert client.post("/v1/connector/pairings", headers={"X-Real-IP": "2.2.2.2"},
                           json={"name": "x", "enrollment_token": other}).status_code == 429
        assert len(app.state.sources.entries) == 1
    table = RateTable(2, 60)
    assert table.allow("one", 0, 1) and table.allow("two", 0, 1)
    assert not table.allow("three", 0, 1) and len(table.entries) == 2
    assert table.allow("three", 61, 1) and len(table.entries) == 1


def test_config_invalid_values_and_psl_domain_isolation(tmp_path, monkeypatch):
    for changes in [{"global_http_concurrency": 0}, {"request_timeout": float("nan")},
                    {"max_nodes": 0.5}, {"ws_max_queue": 5}, {"queued_bytes": 999999999},
                    {"trusted_proxy_cidrs": "172.30.80.2/24"}]:
        with pytest.raises(ValueError):
            GatewayConfig(secret="s", **changes)
    assert registrable_domain("nodes.example.co.uk") == "example.co.uk"
    assert registrable_domain("a.owner.github.io") == "owner.github.io"
    assert registrable_domain("www.city.kawasaki.jp") == "city.kawasaki.jp"
    assert registrable_domain("a.b.ck") == "a.b.ck"
    assert registrable_domain("www.ck") == "www.ck"
    assert normalize_hostname("BÜCHER.DE") == "xn--bcher-kva.de"
    for host in ["foo/bar.example.com", "foo@bar.example.com", " x.com", "-foo.com", "a..com", "a.unknowninvalidsuffix"]:
        with pytest.raises(ValueError):
            registrable_domain(host)
    with pytest.raises(ValueError):
        validate_origins("nodes.example.com", "https", "control.example.com", "https://portal.example.com")
    validate_origins("nodes.workspace.net", "https", "control.workspace.net", "https://portal.example.com")
    monkeypatch.setenv("WORKSPACE_GATEWAY_SECRET", "s")
    monkeypatch.setenv("WORKSPACE_GATEWAY_REQUEST_TIMEOUT", "0.25")
    assert GatewayConfig.from_env().request_timeout == 0.25



def test_same_site_origin_mode_is_explicit_https_and_keeps_distinct_node_hosts(monkeypatch):
    shared = ("nodes.workspace.example.com", "https", "connect.workspace.example.com", "https://portal.example.com")
    with pytest.raises(ValueError, match="separate"):
        validate_origins(*shared)
    validate_origins(*shared, "same-site-subdomains")
    cfg = GatewayConfig(secret="s"*64, scheme="https", workspace_domain=shared[0],
                        control_host=shared[2], portal_origin=shared[3], origin_mode="same-site-subdomains")
    assert cfg.origin_mode == "same-site-subdomains"
    for mode in ("false", "true", "SEPARATE-SITE", "", " same-site-subdomains", None):
        with pytest.raises(ValueError, match="mode"):
            validate_origins(*shared, mode)
    with pytest.raises(ValueError, match="HTTPS"):
        validate_origins("localhost:8090", "http", "localhost:8090", "", "same-site-subdomains")
    with pytest.raises(ValueError, match="mode"):
        GatewayConfig(secret="s", origin_mode="false")
    monkeypatch.setenv("WORKSPACE_GATEWAY_SECRET", "s"*64)
    monkeypatch.setenv("WORKSPACE_GATEWAY_SCHEME", "https")
    monkeypatch.setenv("WORKSPACE_GATEWAY_DOMAIN", shared[0])
    monkeypatch.setenv("WORKSPACE_GATEWAY_CONTROL_HOST", shared[2])
    monkeypatch.setenv("WORKSPACE_GATEWAY_PORTAL_ORIGIN", shared[3])
    monkeypatch.setenv("WORKSPACE_GATEWAY_ORIGIN_MODE", "same-site-subdomains")
    assert GatewayConfig.from_env().origin_mode == "same-site-subdomains"
    monkeypatch.setenv("WORKSPACE_GATEWAY_ORIGIN_MODE", "false")
    with pytest.raises(ValueError, match="mode"):
        GatewayConfig.from_env()


@pytest.mark.parametrize("domain,control,portal", [
    ("nodes.workspace.example.com", "connect.other.net", "https://portal.example.com"),
    ("nodes.workspace.example.com", "connect.workspace.example.com", "https://portal.other.net"),
    ("nodes.workspace.example.com", "connect.workspace.example.com", "http://portal.example.com"),
    ("nodes.workspace.example.com", "connect.workspace.example.com", "https://connect.workspace.example.com"),
    ("nodes.workspace.example.com", "connect.workspace.example.com", "https://nodes.workspace.example.com"),
    ("nodes.workspace.example.com", "connect.workspace.example.com", "https://portal.nodes.workspace.example.com"),
    ("nodes.workspace.example.com", "a"*24 + ".nodes.workspace.example.com", "https://portal.example.com"),
])
def test_same_site_origin_mode_rejects_overlap_or_unrelated_sites(domain, control, portal):
    with pytest.raises(ValueError):
        validate_origins(domain, "https", control, portal, "same-site-subdomains")

def test_resources_global_slots_buffers_and_browser_queue_charge(tmp_path):
    cfg = GatewayConfig(secret="s", global_http_concurrency=1, global_ws_concurrency=1, global_tunnel_concurrency=1)
    resources = Resources(cfg)
    http = resources.acquire("http", "one")
    with pytest.raises(HTTPException) as denied:
        resources.acquire("http", "two")
    assert denied.value.status_code == 429 and denied.value.headers["Retry-After"] == "60"
    resources.release(http)
    resources.release(http)
    assert resources.buffer_bytes == 0
    resources.config.buffer_bytes = 100
    with pytest.raises(HTTPException):
        resources.acquire("tunnel", "one")
    resources.config.buffer_bytes = 1000
    resources.config.queued_bytes = 850
    async def exercise():
        pipe = BrowserPipe(asyncio.get_running_loop().create_future(), resources, 2)
        pipe.put({"type": "ws.data", "kind": "text", "data": "x"})
        with pytest.raises(ValueError):
            pipe.put({"type": "ws.data", "kind": "text", "data": "z" * 100})
        assert resources.queued_bytes > 0
        pipe.clear()
        assert resources.queued_bytes == resources.buffer_bytes == 0
    asyncio.run(exercise())


def prepare_asgi_node(app):
    node_id = "a" * 24
    stamp = time.time()
    app.state.store.db.execute(
        "INSERT INTO nodes(node_id,name,token_hash,pairing_expires,status,account_id,grant_id,scopes,expires,created,enrollment_hash) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (node_id, "x", digest("device"), stamp+300, "paired", "alice", "grant", '["workspace.control"]', stamp+3600, stamp, digest("ticket")))
    app.state.store.db.execute("INSERT INTO sessions VALUES(?,?,?,?)", (digest("session"), node_id, "grant", stamp+3600))
    async def exchange(message, future, timeout, authorize=None):
        if authorize:
            authorize()
        return await future
    tunnel = SimpleNamespace(http={}, http_services={}, browser={}, closed=False, exchange=exchange)
    app.state.tunnels[node_id] = tunnel
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "scheme": "http",
             "method": "POST", "path": "/api/work", "raw_path": b"/api/work", "query_string": b"",
             "root_path": "", "headers": [(b"host", (node_id+".localhost:8090").encode()),
             (b"cookie", b"ambient_workspace=session")], "client": ("127.0.0.1", 10), "server": ("localhost", 8090)}
    return scope, tunnel


def test_actual_asgi_slow_body_preoccupies_slot_and_timeout_releases(tmp_path):
    app = make_app(tmp_path, http_concurrency=1, request_timeout=0.05)
    async def exercise():
        scope, tunnel = prepare_asgi_node(app)
        entered = asyncio.Event()
        never = asyncio.Event()
        sent = []
        async def receive():
            entered.set()
            await never.wait()
            return {"type": "http.request", "body": b"x", "more_body": True}
        async def send(message):
            sent.append(message)
        first = asyncio.create_task(app(dict(scope), receive, send))
        await entered.wait()
        assert app.state.resources.counts["http"] == 1 and len(tunnel.http) == 1
        rejected = []
        async def no_receive():
            raise AssertionError("Over-capacity request read its body")
        async def reject_send(message):
            rejected.append(message)
        await app(dict(scope), no_receive, reject_send)
        assert rejected[0]["status"] == 429
        await first
        assert sent[0]["status"] == 504
        assert app.state.resources.counts["http"] == 0 and not tunnel.http
        assert app.state.resources.buffer_bytes == 0
    asyncio.run(exercise())


def test_actual_asgi_cancel_and_disconnect_release_slots(tmp_path):
    app = make_app(tmp_path, request_timeout=10)
    async def exercise():
        scope, tunnel = prepare_asgi_node(app)
        entered = asyncio.Event()
        async def receive():
            entered.set()
            await asyncio.Event().wait()
        async def send(message):
            pass
        task = asyncio.create_task(app(dict(scope), receive, send))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert app.state.resources.counts["http"] == 0 and not tunnel.http
        calls = 0
        sent = []
        async def complete_then_disconnect():
            nonlocal calls
            calls += 1
            if calls == 1:
                return {"type": "http.request", "body": b"done", "more_body": False}
            return {"type": "http.disconnect"}
        async def capture(message):
            sent.append(message)
        await app(dict(scope), complete_then_disconnect, capture)
        assert sent[0]["status"] == 499
        assert app.state.resources.counts["http"] == 0 and not tunnel.http
        assert app.state.resources.buffer_bytes == 0
    asyncio.run(exercise())


def test_public_get_body_and_non_fixed_vendor_are_rejected_before_receive(tmp_path):
    app = make_app(tmp_path)
    async def exercise():
        scope, _ = prepare_asgi_node(app)
        scope["method"] = "GET"
        scope["path"] = "/vendor/babel.min.js"
        scope["headers"] = [(key, value) for key, value in scope["headers"] if key != b"cookie"]
        scope["headers"].append((b"content-length", b"1"))
        messages = []
        async def receive():
            raise AssertionError("GET declared body must not be read")
        async def send(message):
            messages.append(message)
        await app(scope, receive, send)
        assert messages[0]["status"] == 413
        scope["path"] = "/vendor/private.js"
        scope["headers"] = [(key, value) for key, value in scope["headers"] if key != b"content-length"]
        messages.clear()
        await app(scope, receive, send)
        assert messages[0]["status"] == 401
    asyncio.run(exercise())


def test_unknown_control_host_and_node_service_api_are_rejected(tmp_path):
    app = make_app(tmp_path)
    with TestClient(app) as client:
        assert client.post("http://evil.test/v1/accounts/alice/enrollments",
                           headers=SERVICE, json={"label": "x"}).status_code == 404
        assert client.get("http://"+"a"*24+".localhost:8090/v1/accounts/alice/nodes", headers=SERVICE).status_code == 404


def test_old_schema_paired_identities_survive_and_unenrolled_pending_cannot_claim(tmp_path):
    path = tmp_path / "state.sqlite3"
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE nodes(node_id TEXT PRIMARY KEY,name TEXT,token_hash TEXT UNIQUE,pairing_hash TEXT UNIQUE,"
               "pairing_expires REAL,status TEXT,account_id TEXT,account_label TEXT,grant_id TEXT,scopes TEXT,"
               "expires REAL,last_seen REAL,created REAL)")
    stamp = time.time()
    db.execute("INSERT INTO nodes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
               ("b"*24, "legacy", digest("legacy-device"), None, stamp+300, "paired", "alice", "alice",
                "original-grant", '["workspace.control"]', stamp+3600, stamp, stamp))
    db.execute("INSERT INTO nodes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
               ("c"*24, "legacy-pending", digest("legacy-pending-device"), digest("legacy-code"), stamp+300,
                "pending", None, None, "pending-grant", '["workspace.control"]', stamp+3600, None, stamp))
    db.commit()
    db.close()
    app = make_app(tmp_path)
    with TestClient(app) as client:
        legacy = client.get("/v1/connector/state", headers={"Authorization": "Bearer legacy-device"}).json()
        assert legacy["status"] == "paired" and legacy["grant_id"] == "original-grant"
        assert legacy["expires_at"]
        assert client.get("/v1/connector/state",
                          headers={"Authorization": "Bearer legacy-pending-device"}).json()["status"] == "expired"
        assert client.post("/v1/accounts/alice/pairings/claim", headers=SERVICE,
                           json={"code": "legacy-code", "label": "alice"}).status_code == 409
        assert app.state.store.node("b"*24)["token_hash"] == digest("legacy-device")


def test_actual_asgi_global_http_quota_across_nodes_and_response_send_timeout(tmp_path):
    app = make_app(tmp_path, global_http_concurrency=1, request_timeout=0.05)
    async def exercise():
        scope, tunnel = prepare_asgi_node(app)
        entered = asyncio.Event()
        async def receive():
            entered.set()
            await asyncio.Event().wait()
        async def send(message):
            pass
        held = asyncio.create_task(app(dict(scope), receive, send))
        await entered.wait()
        other = "d"*24
        app.state.store.db.execute("INSERT INTO nodes SELECT ?,name,?,NULL,pairing_expires,status,account_id,account_label,"
              "grant_id,scopes,expires,last_seen,created,enrollment_hash,retired FROM nodes WHERE node_id=?",
              (other, digest("other-device"), "a"*24))
        app.state.store.db.execute("INSERT INTO sessions VALUES(?,?,?,?)",
                                  (digest("other-session"), other, "grant", time.time()+3600))
        app.state.tunnels[other] = tunnel
        second = dict(scope)
        second["headers"] = [(b"host", (other+".localhost:8090").encode()), (b"cookie", b"ambient_workspace=other-session")]
        rejected = []
        async def no_receive():
            raise AssertionError("Globally rejected request must not read")
        async def reject_send(message):
            rejected.append(message)
        await app(second, no_receive, reject_send)
        assert rejected[0]["status"] == 429
        held.cancel()
        with pytest.raises(asyncio.CancelledError):
            await held
        # The request timeout includes the response sender after the connector reply.
        async def response_exchange(message, future, timeout, authorize=None):
            return 200, [["content-type", "application/json"]], b"{}"
        tunnel.exchange = response_exchange
        calls = 0
        async def complete_upload():
            nonlocal calls
            calls += 1
            if calls == 1:
                return {"type": "http.request", "body": b"", "more_body": False}
            await asyncio.Event().wait()
        started = []
        async def slow_send(message):
            started.append(message)
            await asyncio.Event().wait()
        with pytest.raises(TimeoutError):
            await app(dict(scope), complete_upload, slow_send)
        assert started[0]["type"] == "http.response.start"
        assert not tunnel.http and app.state.resources.buffer_bytes == 0
    asyncio.run(exercise())


def test_actual_asgi_disconnect_during_body_releases(tmp_path):
    app = make_app(tmp_path)
    async def exercise():
        scope, tunnel = prepare_asgi_node(app)
        sent = []
        async def receive():
            return {"type": "http.disconnect"}
        async def send(message):
            sent.append(message)
        await app(scope, receive, send)
        assert sent[0]["status"] == 499 and not tunnel.http
        assert app.state.resources.buffer_bytes == 0
    asyncio.run(exercise())


def test_https_host_cookie_and_independent_portal_site(tmp_path):
    app = create_app(GatewayConfig(database=str(tmp_path / "https.sqlite3"), secret="s"*48,
                     workspace_domain="nodes.workspace.net", control_host="control.workspace.net",
                     scheme="https", portal_origin="https://portal.example.com"))
    service = {"Authorization": "Bearer " + "s"*48}
    with TestClient(app, base_url="https://control.workspace.net") as client:
        token = client.post("/v1/accounts/alice/enrollments", headers=service, json={"label": "alice"}).json()["enrollment_token"]
        pair = client.post("/v1/connector/pairings", json={"name": "local", "enrollment_token": token}).json()
        device = {"Authorization": "Bearer " + pair["connector_token"]}
        claimed = client.post("/v1/accounts/alice/pairings/claim", headers=service,
                              json={"code": pair["pairing_code"], "label": "alice"}).json()
        client.post("/v1/connector/approve", headers=device,
                    json={"account_id": "alice", "grant_id": claimed["grant_id"]})
        with client.websocket_connect("wss://control.workspace.net/v1/connector/tunnel", headers=device) as tunnel:
            tunnel.receive_json()
            ticket = client.post(f"/v1/accounts/alice/nodes/{pair['node_id']}/launch", headers=service).json()["url"]
            response = client.get(ticket, follow_redirects=False)
            cookie = response.headers["set-cookie"]
            assert cookie.startswith("__Host-ambient_workspace=") and "Secure" in cookie and "Domain=" not in cookie
            assert response.headers["location"] == "/"


def test_real_browser_ws_backpressure_closes_tunnel_and_drains_global_queue(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from test_gateway import launch
    app = make_app(tmp_path, browser_queue_size=1, ws_send_timeout=0.1)
    with TestClient(app) as client:
        pair, device, node = setup_node(client)
        with client.websocket_connect("/v1/connector/tunnel", headers=device) as tunnel:
            tunnel.receive_json()
            launch(client, pair)
            with ThreadPoolExecutor() as executor:
                def browser():
                    with client.websocket_connect(pair["workspace_origin"].replace("http:", "ws:")+"/ws/events") as ws:
                        ws.send_text("ready")
                        assert ws.receive()["type"] == "websocket.close"
                waiting = executor.submit(browser)
                opened = tunnel.receive_json()
                tunnel.send_json({"type": "ws.accept", "id": opened["id"], "subprotocol": None})
                assert tunnel.receive_json()["data"] == "ready"
                active = app.state.tunnels[pair["node_id"]]
                pipe = active.browser[opened["id"]]
                # Hold the actual browser socket send; the third upstream frame
                # fills the one-frame pipe and triggers bounded backpressure.
                from starlette.websockets import WebSocket
                original = WebSocket.send_text
                async def blocked(socket, data):
                    await asyncio.sleep(0.5)
                    await original(socket, data)
                monkeypatch.setattr(WebSocket, "send_text", blocked)
                for index in range(4):
                    tunnel.send_json({"type": "ws.data", "id": opened["id"], "kind": "text", "data": str(index)})
                waiting.result(timeout=3)
                assert active.closed
            assert app.state.resources.queued_bytes == 0
            assert app.state.resources.counts["ws"] == 0
            assert app.state.resources.metrics["backpressure_closes"] >= 1


def test_rejected_resource_admission_does_not_accumulate_node_counters():
    resources = Resources(GatewayConfig(secret="s", buffer_bytes=1, queued_bytes=1))
    for index in range(1000):
        with pytest.raises(HTTPException):
            resources.acquire("http", str(index))
    assert len(resources.nodes) == 0 and resources.buffer_bytes == 0


def test_device_polling_uses_separate_budget_from_mutation(tmp_path):
    app = make_app(tmp_path, device_rate=1, device_state_rate=120)
    with TestClient(app) as client:
        pair, device, _ = setup_node(client)
        for _ in range(35):
            assert client.get("/v1/connector/state", headers=device).status_code == 200
        app.state.devices.entries.clear()
        assert client.post("/v1/connector/revoke", headers=device).status_code == 200
        denied = client.post("/v1/connector/revoke", headers=device)
        assert denied.status_code == 429 and denied.headers["retry-after"] == "60"


def test_internal_service_host_only_allows_bearer_account_and_metrics_routes(tmp_path):
    app = make_app(tmp_path, service_host="workspace-gateway:8090")
    with TestClient(app, base_url="http://workspace-gateway:8090") as client:
        assert client.post("/v1/accounts/alice/enrollments", json={"label": "alice"}).status_code == 401
        created = client.post("/v1/accounts/alice/enrollments", headers=SERVICE, json={"label": "alice"})
        assert created.status_code == 200
        assert client.get("/v1/accounts/alice/nodes", headers=SERVICE).json() == {"nodes": [], "next_cursor": None}
        assert client.get("/v1/metrics", headers=SERVICE).status_code == 200
        assert client.get("/v1/metrics").status_code == 401
        assert client.get("/v1/metrics", headers={"Authorization": "Bearer wrong"}).status_code == 401
        assert client.get("/health").status_code == 404
        assert client.post("/v1/connector/pairings", json={"name": "x", "enrollment_token": created.json()["enrollment_token"]}).status_code == 404
        paired = client.post("http://testserver/v1/connector/pairings",
                             json={"name": "x", "enrollment_token": created.json()["enrollment_token"]})
        assert paired.status_code == 200
        assert client.get(paired.json()["workspace_origin"]+"/v1/accounts/alice/nodes", headers=SERVICE).status_code == 404


@pytest.mark.parametrize("stage", ["accept", "replace"])
def test_actual_asgi_connector_cancellation_releases_admission_in_handshake_and_replacement(tmp_path, stage):
    app = make_app(tmp_path)
    async def exercise():
        _, previous = prepare_asgi_node(app)
        held = asyncio.Event()
        async def blocked_close(*args, **kwargs):
            held.set()
            await asyncio.Event().wait()
        previous.close = blocked_close
        scope = {"type": "websocket", "asgi": {"version": "3.0"}, "scheme": "ws",
                 "path": "/v1/connector/tunnel", "raw_path": b"/v1/connector/tunnel", "query_string": b"",
                 "root_path": "", "headers": [(b"host", b"testserver"), (b"authorization", b"Bearer device")],
                 "client": ("127.0.0.1", 10), "server": ("testserver", 80), "subprotocols": []}
        first = True
        async def receive():
            nonlocal first
            if first:
                first = False
                return {"type": "websocket.connect"}
            await asyncio.Event().wait()
        async def send(message):
            if stage == "accept" and message["type"] == "websocket.accept":
                held.set()
                await asyncio.Event().wait()
        task = asyncio.create_task(app(scope, receive, send))
        await held.wait()
        assert app.state.resources.counts["tunnel"] == 1
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert app.state.resources.counts["tunnel"] == 0
        assert app.state.resources.buffer_bytes == 0
        assert app.state.tunnels.get("a"*24) is previous
    asyncio.run(exercise())


def test_browser_ws_reservation_covers_launcher_shared_transport_receive_queue():
    cfg = GatewayConfig(secret="s", http_limit=1024, frame_limit=128, ws_max_queue=2)
    resources = Resources(cfg)
    lease = resources.acquire("ws", "browser")
    wire_ceiling = cfg.http_limit * 4 // 3 + 65536
    assert lease.size == (cfg.ws_max_queue + 1) * (4 * wire_ceiling + 1024) + 12 * cfg.frame_limit + 4096
    resources.release(lease)
    assert resources.buffer_bytes == 0


def test_browser_queue_charge_covers_wide_python_text():
    resources = Resources(GatewayConfig(secret="s"))
    async def exercise():
        pipe = BrowserPipe(asyncio.get_running_loop().create_future(), resources, 2)
        message = {"type": "ws.data", "kind": "text", "data": "\U0001f600" + "x"*1000}
        pipe.put(message)
        assert resources.queued_bytes >= 4 * len(json.dumps(message, ensure_ascii=False).encode())
        pipe.clear()
        assert resources.buffer_bytes == 0
    asyncio.run(exercise())


def test_mixed_unicode_transport_and_browser_queue_reservations_cover_real_python_objects():
    import sys
    cfg = GatewayConfig(secret="s")
    resources = Resources(cfg)
    wire_ceiling = cfg.http_limit * 4 // 3 + 65536
    wire = "a"*(wire_ceiling-4) + "\U0001f600"
    assert len(wire.encode("utf-8")) == wire_ceiling
    assert sys.getsizeof(wire) > len(wire.encode("utf-8")) * 3
    tunnel = resources.acquire("tunnel", "one")
    assert tunnel.size >= (cfg.ws_max_queue+1) * sys.getsizeof(wire)
    resources.release(tunnel)
    browser = resources.acquire("ws", "one")
    assert browser.size >= (cfg.ws_max_queue+1) * sys.getsizeof(wire)
    resources.release(browser)
    async def exercise():
        payload = "a"*(cfg.frame_limit-4) + "\U0001f600"
        assert len(payload.encode("utf-8")) == cfg.frame_limit
        message = {"type": "ws.data", "kind": "text", "data": payload}
        pipe = BrowserPipe(asyncio.get_running_loop().create_future(), resources, 2)
        pipe.put(message)
        retained = (sys.getsizeof(message) + sys.getsizeof((message, 0))
                    + sys.getsizeof(resources.queued_bytes)
                    + sum(sys.getsizeof(key)+sys.getsizeof(value) for key, value in message.items()))
        assert resources.queued_bytes >= retained
        pipe.clear()
        assert resources.buffer_bytes == 0
    asyncio.run(exercise())


@pytest.mark.parametrize("mode,portal", [
    ("same-site-subdomains", "https://portal.example.com"),
    ("separate-site", "https://portal.example.net"),
])
def test_exact_control_subdomain_is_not_classified_as_a_node(tmp_path, mode, portal):
    cfg = GatewayConfig(database=str(tmp_path / "state.sqlite3"), secret="synthetic-service-secret-at-least-32",
        scheme="https", workspace_domain="workspace.example.com", control_host="gateway.workspace.example.com",
        service_host="workspace-gateway:8090", portal_origin=portal, origin_mode=mode)
    app = create_app(cfg)
    service = {"Authorization": "Bearer " + cfg.secret}
    control = "https://" + cfg.control_host
    with TestClient(app, base_url="http://workspace-gateway:8090") as client:
        assert client.get(control + "/health").status_code == 200
        token = client.post("/v1/accounts/synthetic/enrollments", headers=service, json={"label": "test"}).json()["enrollment_token"]
        response = client.post(control + "/v1/connector/pairings", json={"name": "test", "enrollment_token": token})
        assert response.status_code == 200
        pair = response.json()
        claimed = client.post("/v1/accounts/synthetic/pairings/claim", headers=service,
            json={"code": pair["pairing_code"], "label": "test"}).json()
        device = {"Authorization": "Bearer " + pair["connector_token"]}
        assert client.post(control + "/v1/connector/approve", headers=device,
            json={"account_id": "synthetic", "grant_id": claimed["grant_id"]}).status_code == 200
        assert client.get(control + "/v1/connector/state", headers=device).json()["status"] == "paired"
        with client.websocket_connect(control.replace("https:", "wss:") + "/v1/connector/tunnel", headers=device) as tunnel:
            assert tunnel.receive_json()["type"] == "hello"
        assert client.get("https://unknown.workspace.example.com/v1/connector/state", headers=device).status_code == 404
        assert client.get(pair["workspace_origin"] + "/v1/connector/state", headers=device).status_code == 404
        assert client.get(portal + "/health").status_code == 404

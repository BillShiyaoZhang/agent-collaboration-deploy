import base64
import asyncio
import gzip
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from workspace_gateway.app import GatewayConfig, create_app

SERVICE = {"Authorization": "Bearer test-service-secret"}


def setup_node(client, account="alice", expires_in=3600):
    pair = client.post(
        "/v1/connector/pairings", json={"name": "My Ambient", "scopes": ["workspace.control"], "expires_in": expires_in}
    ).json()
    device = {"Authorization": "Bearer " + pair["connector_token"]}
    claimed = client.post(
        f"/v1/accounts/{account}/pairings/claim",
        headers=SERVICE,
        json={"code": pair["pairing_code"], "label": account + "@example.test"},
    )
    assert claimed.status_code == 200
    node = claimed.json()
    approved = client.post(
        "/v1/connector/approve", headers=device, json={"account_id": account, "grant_id": node["grant_id"]}
    )
    assert approved.status_code == 200
    return pair, device, node


@pytest.fixture
def app(tmp_path):
    return create_app(
        GatewayConfig(
            database=str(tmp_path / "gateway.sqlite3"),
            secret="test-service-secret",
            workspace_domain="localhost:8090",
            scheme="http",
        )
    )


def launch(client, pair, account="alice"):
    result = client.post(f"/v1/accounts/{account}/nodes/{pair['node_id']}/launch", headers=SERVICE)
    assert result.status_code == 200, result.text
    url = result.json()["url"]
    response = client.get(url, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "Domain=" not in response.headers["set-cookie"]
    return url


def test_pairing_claim_requires_local_confirmation_and_is_single_use(app):
    with TestClient(app) as client:
        pair = client.post(
            "/v1/connector/pairings", json={"name": "Home", "scopes": ["workspace.control"], "expires_in": 3600}
        ).json()
        device = {"Authorization": "Bearer " + pair["connector_token"]}
        assert (
            client.post(
                "/v1/accounts/alice/pairings/claim", json={"code": pair["pairing_code"], "label": "alice"}
            ).status_code
            == 401
        )
        claimed = client.post(
            "/v1/accounts/alice/pairings/claim", headers=SERVICE, json={"code": pair["pairing_code"], "label": "alice"}
        ).json()
        assert claimed["status"] == "claimed"
        assert (
            client.post(
                "/v1/accounts/bob/pairings/claim", headers=SERVICE, json={"code": pair["pairing_code"], "label": "bob"}
            ).status_code
            == 409
        )
        assert (
            client.post(
                "/v1/connector/approve", headers=device, json={"account_id": "bob", "grant_id": claimed["grant_id"]}
            ).status_code
            == 409
        )
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/v1/connector/tunnel", headers=device):
                pass
        assert (
            client.post(
                "/v1/connector/approve", headers=device, json={"account_id": "alice", "grant_id": claimed["grant_id"]}
            ).status_code
            == 200
        )
        assert client.get("/v1/accounts/bob/nodes", headers=SERVICE).json() == {"nodes": []}
        assert client.delete(f"/v1/accounts/bob/nodes/{pair['node_id']}", headers=SERVICE).status_code == 404


def test_launch_host_cookie_replay_and_proxy_http(app):
    with TestClient(app) as client:
        pair, device, node = setup_node(client)
        with client.websocket_connect("/v1/connector/tunnel", headers=device) as tunnel:
            hello = tunnel.receive_json()
            assert hello["type"] == "hello" and hello["account_id"] == "alice"
            assert hello["grant_id"] == node["grant_id"]
            url = launch(client, pair)
            assert client.get(url, follow_redirects=False).status_code == 401
            assert client.post(f"/v1/accounts/bob/nodes/{pair['node_id']}/launch", headers=SERVICE).status_code == 404
            origin = pair["workspace_origin"]
            assert client.get(origin + "/v1/accounts/alice/nodes", headers=SERVICE).status_code == 404
            with ThreadPoolExecutor() as executor:
                response = executor.submit(
                    client.get,
                    origin + "/api/graphs?x=1",
                    headers={"X-Account-Id": "bob", "Authorization": "Bearer stolen", "X-Forwarded-Host": "evil.test"},
                )
                message = tunnel.receive_json()
                assert message["type"] == "http.request" and message["service"] == "backend"
                assert message["path"] == "/api/graphs?x=1" and message["account_id"] == "alice"
                assert not {"cookie", "authorization", "host", "x-account-id", "x-forwarded-host"} & {
                    item[0].lower() for item in message["headers"]
                }
                tunnel.send_json(
                    {
                        "type": "http.response",
                        "id": message["id"],
                        "status": 200,
                        "headers": [["content-type", "application/json"]],
                        "body": base64.b64encode(b'{"real":true}').decode(),
                    }
                )
                assert response.result(timeout=5).json() == {"real": True}


def test_html_config_and_public_frame_allowlist(app):
    with TestClient(app) as client:
        pair, device, node = setup_node(client)
        with client.websocket_connect("/v1/connector/tunnel", headers=device) as tunnel:
            tunnel.receive_json()
            launch(client, pair)
            with ThreadPoolExecutor() as executor:
                response = executor.submit(client.get, pair["workspace_origin"] + "/")
                message = tunnel.receive_json()
                html = b"<html><head></head><body>App</body></html>"
                tunnel.send_json(
                    {
                        "type": "http.response",
                        "id": message["id"],
                        "status": 200,
                        "headers": [
                            ["content-type", "text/html"],
                            ["content-length", str(len(html))],
                            ["content-security-policy", "default-src 'self'"],
                        ],
                        "body": base64.b64encode(html).decode(),
                    }
                )
                page = response.result(timeout=5)
                assert "window.__AMBIENT_REMOTE__=" in page.text and pair["node_id"] in page.text
                assert page.headers["content-security-policy"] == "default-src 'self'"
                assert int(page.headers["content-length"]) == len(page.content)
                client.cookies.clear()
                frame = executor.submit(client.get, pair["workspace_origin"] + "/_ambient/frame.html")
                message = tunnel.receive_json()
                assert message["service"] == "frame" and message["path"] == "/frame.html"
                tunnel.send_json(
                    {
                        "type": "http.response",
                        "id": message["id"],
                        "status": 200,
                        "headers": [["content-type", "text/html"]],
                        "body": base64.b64encode(b"<html>Frame</html>").decode(),
                    }
                )
                assert "__AMBIENT_REMOTE__" not in frame.result(timeout=5).text
            assert client.get(pair["workspace_origin"] + "/api/graphs").status_code == 401
            assert client.get(pair["workspace_origin"] + "/_ambient/private").status_code == 404


def test_websocket_subprotocol_and_bidirectional_frames_and_revoke(app):
    with TestClient(app) as client:
        pair, device, node = setup_node(client)
        with client.websocket_connect("/v1/connector/tunnel", headers=device) as tunnel:
            tunnel.receive_json()
            launch(client, pair)
            with ThreadPoolExecutor() as executor:

                def browser():
                    with client.websocket_connect(
                        pair["workspace_origin"].replace("http:", "ws:") + "/ws/events", subprotocols=["ambient-v1"]
                    ) as ws:
                        assert ws.accepted_subprotocol == "ambient-v1"
                        ws.send_text("hello")
                        assert ws.receive_bytes() == b"reply"
                        assert ws.receive()["type"] == "websocket.close"

                task = executor.submit(browser)
                opened = tunnel.receive_json()
                assert opened["type"] == "ws.open" and opened["subprotocols"] == ["ambient-v1"]
                tunnel.send_json({"type": "ws.accept", "id": opened["id"], "subprotocol": "ambient-v1"})
                message = tunnel.receive_json()
                assert message["type"] == "ws.data" and message["kind"] == "text" and message["data"] == "hello"
                tunnel.send_json(
                    {
                        "type": "ws.data",
                        "id": opened["id"],
                        "kind": "bytes",
                        "data": base64.b64encode(b"reply").decode(),
                    }
                )
                assert client.delete(f"/v1/accounts/alice/nodes/{pair['node_id']}", headers=SERVICE).status_code == 200
                assert tunnel.receive_json()["type"] == "revoked"
                task.result(timeout=5)
            assert client.get(pair["workspace_origin"] + "/api/graphs").status_code == 401


def test_expiry_rejects_ticket_and_closes_live_tunnel(app):
    with TestClient(app) as client:
        pair, device, node = setup_node(client, expires_in=300)
        with client.websocket_connect("/v1/connector/tunnel", headers=device) as tunnel:
            tunnel.receive_json()
            url = launch(client, pair)
            app.state.clock = lambda: datetime.fromisoformat(node["expires_at"].replace("Z", "+00:00")).timestamp() + 1
            assert client.get("/v1/connector/state", headers=device).json()["status"] == "expired"
            assert client.get(url, follow_redirects=False).status_code == 401
            assert tunnel.receive_json()["type"] == "revoked"


def test_paths_body_quota_and_timeout(app):
    with TestClient(app) as client:
        pair, device, node = setup_node(client)
        with client.websocket_connect("/v1/connector/tunnel", headers=device) as tunnel:
            tunnel.receive_json()
            launch(client, pair)
            origin = pair["workspace_origin"]
            assert client.post(origin + "/api/remote-workspace/approve").status_code == 403
            assert client.get(origin + "/api/%2e%2e/secrets").status_code == 400
            assert client.post(origin + "/api/graphs", content=b"x" * (2 * 1024 * 1024 + 1)).status_code == 413
            app.state.config.request_timeout = 0.05
            assert client.get(origin + "/api/graphs").status_code == 504
            tunnel.receive_json()


def test_restart_keeps_grant_without_raw_tokens_or_content(tmp_path):
    config = GatewayConfig(
        database=str(tmp_path / "gateway.sqlite3"),
        secret="test-service-secret",
        workspace_domain="localhost:8090",
        scheme="http",
    )
    with TestClient(create_app(config)) as client:
        pair, device, node = setup_node(client)
    raw = (tmp_path / "gateway.sqlite3").read_bytes()
    assert pair["connector_token"].encode() not in raw
    assert pair["pairing_code"].encode() not in raw
    with TestClient(create_app(config)) as client:
        state = client.get("/v1/connector/state", headers=device).json()
        assert state["status"] == "paired" and state["grant_id"] == node["grant_id"] and state["online"] is False
    database = sqlite3.connect(config.database)
    assert database.execute("select count(*) from audit").fetchone()[0] >= 3


def test_public_plaintext_and_missing_secret_rejected():
    with pytest.raises(ValueError):
        GatewayConfig(secret="", workspace_domain="workspaces.example.com", scheme="https")
    with pytest.raises(ValueError):
        GatewayConfig(secret="real", workspace_domain="workspaces.example.com", scheme="http")


def test_http_concurrency_and_inflight_revoke(app):
    app.state.config.http_concurrency = 1
    with TestClient(app) as client:
        pair, device, node = setup_node(client)
        with client.websocket_connect("/v1/connector/tunnel", headers=device) as tunnel:
            tunnel.receive_json()
            launch(client, pair)
            with ThreadPoolExecutor() as executor:
                waiting = executor.submit(client.get, pair["workspace_origin"] + "/api/graphs")
                assert tunnel.receive_json()["type"] == "http.request"
                assert client.get(pair["workspace_origin"] + "/api/graphs").status_code == 429
                assert client.post("/v1/connector/revoke", headers=device).status_code == 200
                assert waiting.result(timeout=5).status_code == 503
                assert tunnel.receive_json()["type"] == "revoked"


def test_wrong_workspace_host_cannot_consume_ticket(app):
    with TestClient(app) as client:
        pair, device, node = setup_node(client)
        second, _, _ = setup_node(client, account="bob")
        with client.websocket_connect("/v1/connector/tunnel", headers=device) as tunnel:
            tunnel.receive_json()
            ticket = client.post(f"/v1/accounts/alice/nodes/{pair['node_id']}/launch", headers=SERVICE).json()["url"]
            wrong = ticket.replace(pair["node_id"], second["node_id"])
            assert client.get(wrong, follow_redirects=False).status_code == 401
            assert client.get(ticket, follow_redirects=False).status_code == 303


def test_pairing_and_launch_expiry(app):
    with TestClient(app) as client:
        pair = client.post("/v1/connector/pairings", json={"name": "Expired", "expires_in": 3600}).json()
        expiry = datetime.fromisoformat(pair["pairing_expires_at"].replace("Z", "+00:00")).timestamp()
        app.state.clock = lambda: expiry + 1
        assert (
            client.post(
                "/v1/accounts/alice/pairings/claim",
                headers=SERVICE,
                json={"code": pair["pairing_code"], "label": "alice"},
            ).status_code
            == 409
        )
        pair, device, node = setup_node(client)
        with client.websocket_connect("/v1/connector/tunnel", headers=device) as tunnel:
            tunnel.receive_json()
            ticket = client.post(f"/v1/accounts/alice/nodes/{pair['node_id']}/launch", headers=SERVICE).json()
            expires = datetime.fromisoformat(ticket["expires_at"].replace("Z", "+00:00")).timestamp()
            app.state.clock = lambda: expires + 1
            assert client.get(ticket["url"], follow_redirects=False).status_code == 401


def test_session_expiry_closes_existing_browser_websocket(app):
    app.state.config.session_ttl = 1
    with TestClient(app) as client:
        pair, device, node = setup_node(client)
        with client.websocket_connect("/v1/connector/tunnel", headers=device) as tunnel:
            tunnel.receive_json()
            launch(client, pair)
            clock = app.state.clock
            with ThreadPoolExecutor() as executor:

                def browser():
                    with client.websocket_connect(
                        pair["workspace_origin"].replace("http:", "ws:") + "/ws/events"
                    ) as ws:
                        ws.send_text("online")
                        assert ws.receive()["type"] == "websocket.close"

                waiting = executor.submit(browser)
                opened = tunnel.receive_json()
                tunnel.send_json({"type": "ws.accept", "id": opened["id"], "subprotocol": None})
                assert tunnel.receive_json()["data"] == "online"
                app.state.clock = lambda: clock() + 2
                waiting.result(timeout=5)
                assert tunnel.receive_json()["type"] == "ws.close"


def test_browser_websocket_frame_limit(app):
    app.state.config.frame_limit = 8
    with TestClient(app) as client:
        pair, device, node = setup_node(client)
        with client.websocket_connect("/v1/connector/tunnel", headers=device) as tunnel:
            tunnel.receive_json()
            launch(client, pair)
            with ThreadPoolExecutor() as executor:

                def browser():
                    with client.websocket_connect(
                        pair["workspace_origin"].replace("http:", "ws:") + "/ws/events"
                    ) as ws:
                        ws.send_bytes(b"123456789")
                        assert ws.receive()["type"] == "websocket.close"

                waiting = executor.submit(browser)
                opened = tunnel.receive_json()
                tunnel.send_json({"type": "ws.accept", "id": opened["id"], "subprotocol": None})
                assert tunnel.receive_json()["type"] == "ws.close"
                waiting.result(timeout=5)


def test_all_fixed_frame_module_dependencies_are_public_and_frame_routed(app):
    with TestClient(app) as client:
        pair, device, node = setup_node(client)
        with client.websocket_connect("/v1/connector/tunnel", headers=device) as tunnel:
            tunnel.receive_json()
            with ThreadPoolExecutor() as executor:
                for path in [
                    "/_ambient/frame.html",
                    "/frame_shell.css",
                    "/frame_shell.mjs",
                    "/controller_facade.mjs",
                    "/presentation_context.mjs",
                    "/vendor/babel.min.js",
                    "/vendor/htm-preact.js",
                ]:
                    waiting = executor.submit(client.get, pair["workspace_origin"] + path)
                    message = tunnel.receive_json()
                    assert message["service"] == "frame"
                    assert message["path"] == ("/frame.html" if path == "/_ambient/frame.html" else path)
                    tunnel.send_json(
                        {
                            "type": "http.response",
                            "id": message["id"],
                            "status": 200,
                            "headers": [
                                ["content-type", "application/javascript"],
                                ["access-control-allow-origin", "*"],
                            ],
                            "body": base64.b64encode(b"export {};").decode(),
                        }
                    )
                    assert waiting.result(timeout=5).status_code == 200


def test_account_bulk_revoke_only_affects_own_nodes(app):
    with TestClient(app) as client:
        first, first_device, _ = setup_node(client)
        second, _, _ = setup_node(client)
        other, _, _ = setup_node(client, account="bob")
        with client.websocket_connect("/v1/connector/tunnel", headers=first_device) as tunnel:
            tunnel.receive_json()
            assert client.delete("/v1/accounts/alice/nodes").status_code == 401
            assert client.delete("/v1/accounts/alice/nodes", headers=SERVICE).json() == {"revoked": 2}
            assert tunnel.receive_json()["type"] == "revoked"
            assert all(
                n["status"] == "revoked"
                for n in client.get("/v1/accounts/alice/nodes", headers=SERVICE).json()["nodes"]
            )
            assert client.get("/v1/accounts/bob/nodes", headers=SERVICE).json()["nodes"][0]["status"] == "paired"


def test_missing_frame_modules_are_public_even_without_browser_session(app):
    with TestClient(app) as client:
        pair, _, _ = setup_node(client)
        for path in ["/controller_facade.mjs", "/presentation_context.mjs"]:
            assert client.get(pair["workspace_origin"] + path).status_code == 503


def test_account_deletion_is_terminal_and_idempotent(app):
    with TestClient(app) as client:
        pair, device, node = setup_node(client)
        assert client.delete("/v1/accounts/alice", headers=SERVICE).json() == {"revoked": 1}
        assert client.delete("/v1/accounts/alice", headers=SERVICE).json() == {"revoked": 0}
        assert (
            client.post(
                "/v1/connector/approve", headers=device, json={"account_id": "alice", "grant_id": node["grant_id"]}
            ).status_code
            == 409
        )
        next_pair = client.post("/v1/connector/pairings", json={"name": "New"}).json()
        assert (
            client.post(
                "/v1/accounts/alice/pairings/claim",
                headers=SERVICE,
                json={"code": next_pair["pairing_code"], "label": "alice"},
            ).status_code
            == 410
        )
        assert (
            client.post(
                "/v1/accounts/bob/pairings/claim",
                headers=SERVICE,
                json={"code": next_pair["pairing_code"], "label": "bob"},
            ).status_code
            == 200
        )


def test_browser_expiry_during_request_body_does_not_dispatch(app):
    with TestClient(app) as client:
        pair, device, node = setup_node(client, expires_in=7200)
        with client.websocket_connect("/v1/connector/tunnel", headers=device) as tunnel:
            tunnel.receive_json()
            launch(client, pair)
            clock = app.state.clock

            async def expire_during_body(request, call_next):
                original = request._receive

                async def late_receive():
                    message = await original()
                    app.state.clock = lambda: clock() + 3601
                    return message

                request._receive = late_receive
                return await call_next(request)

            from starlette.middleware.base import BaseHTTPMiddleware

            app.middleware_stack = BaseHTTPMiddleware(app.middleware_stack, dispatch=expire_during_body)
            app.state.config.request_timeout = 0.05
            assert client.post(pair["workspace_origin"] + "/api/graphs", content=b"write").status_code == 401
            assert not app.state.tunnels[pair["node_id"]].http


def test_fixed_frame_gzip_asset_stays_within_wire_limit_and_decodes_in_browser(app):
    with TestClient(app) as client:
        pair, device, node = setup_node(client)
        with client.websocket_connect("/v1/connector/tunnel", headers=device) as tunnel:
            tunnel.receive_json()
            with ThreadPoolExecutor() as executor:
                waiting = executor.submit(client.get, pair["workspace_origin"] + "/vendor/babel.min.js")
                message = tunnel.receive_json()
                source = b"/* known vendor asset */" + b"x" * (2 * 1024 * 1024 + 100)
                compressed = gzip.compress(source)
                assert len(compressed) < app.state.config.http_limit < len(source)
                tunnel.send_json(
                    {
                        "type": "http.response",
                        "id": message["id"],
                        "status": 200,
                        "headers": [
                            ["content-type", "text/javascript"],
                            ["content-encoding", "gzip"],
                            ["access-control-allow-origin", "*"],
                        ],
                        "body": base64.b64encode(compressed).decode(),
                    }
                )
                response = waiting.result(timeout=5)
                assert response.headers["content-encoding"] == "gzip"
                assert response.content == source


def test_browser_expiry_while_waiting_for_ws_accept_is_denied(app):
    app.state.config.session_ttl = 1
    with TestClient(app) as client:
        pair, device, node = setup_node(client, expires_in=7200)
        with client.websocket_connect("/v1/connector/tunnel", headers=device) as tunnel:
            tunnel.receive_json()
            launch(client, pair)
            clock = app.state.clock
            with ThreadPoolExecutor() as executor:

                def browser():
                    with pytest.raises(WebSocketDisconnect):
                        with client.websocket_connect(pair["workspace_origin"].replace("http:", "ws:") + "/ws/events"):
                            pytest.fail("Expired browser session was accepted")

                waiting = executor.submit(browser)
                opened = tunnel.receive_json()
                app.state.clock = lambda: clock() + 2
                tunnel.send_json({"type": "ws.accept", "id": opened["id"], "subprotocol": None})
                waiting.result(timeout=5)
                assert tunnel.receive_json()["type"] == "ws.close"


def test_browser_websocket_concurrency_quota(app):
    app.state.config.ws_concurrency = 1
    with TestClient(app) as client:
        pair, device, node = setup_node(client)
        with client.websocket_connect("/v1/connector/tunnel", headers=device) as tunnel:
            tunnel.receive_json()
            launch(client, pair)
            url = pair["workspace_origin"].replace("http:", "ws:") + "/ws/events"
            with ThreadPoolExecutor() as executor:

                def browser():
                    with client.websocket_connect(url) as ws:
                        ws.send_text("ready")
                        assert ws.receive()["type"] == "websocket.close"

                waiting = executor.submit(browser)
                opened = tunnel.receive_json()
                tunnel.send_json({"type": "ws.accept", "id": opened["id"], "subprotocol": None})
                assert tunnel.receive_json()["data"] == "ready"
                with pytest.raises(WebSocketDisconnect):
                    with client.websocket_connect(url):
                        pytest.fail("WebSocket concurrency quota was ignored")
                tunnel.send_json({"type": "ws.close", "id": opened["id"], "code": 1000, "reason": "done"})
                waiting.result(timeout=5)


def test_http_timeout_budget_includes_blocked_tunnel_write(app):
    app.state.config.request_timeout = 0.03
    with TestClient(app) as client:
        pair, device, node = setup_node(client)
        with client.websocket_connect("/v1/connector/tunnel", headers=device) as tunnel:
            tunnel.receive_json()
            launch(client, pair)
            active = app.state.tunnels[pair["node_id"]]
            original = active.socket.send_json
            completed = []

            async def blocked_write(message):
                await asyncio.sleep(0.1)
                completed.append(True)
                await original(message)

            active.socket.send_json = blocked_write
            assert client.get(pair["workspace_origin"] + "/api/graphs").status_code == 504
            assert not completed, "The request timeout only started after the blocked write"

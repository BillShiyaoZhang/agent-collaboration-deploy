from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from workspace_gateway.app import GatewayConfig, create_app, iso
from test_gateway import SERVICE, enrollment_token, launch, setup_node

SENTINEL = "9999-01-01T00:00:00Z"
SENTINEL_EPOCH = 253370764800
STAMP = 1700000000.0


@pytest.fixture
def gateway(tmp_path):
    app = create_app(GatewayConfig(database=str(tmp_path / "grants.sqlite3"), secret="test-service-secret"))
    app.state.clock = lambda: STAMP
    return app


def pair_long(client, **changes):
    return client.post("/v1/connector/pairings", json={
        "name": "Owned Ambient", "scopes": ["workspace.control"], "expires_in": 3600,
        "enrollment_token": enrollment_token(client), "until_revoked": True, **changes,
    })


def approved_long(client):
    response = pair_long(client)
    assert response.status_code == 200
    pair = response.json()
    device = {"Authorization": "Bearer " + pair["connector_token"]}
    claim = client.post("/v1/accounts/alice/pairings/claim", headers=SERVICE,
                        json={"code": pair["pairing_code"], "label": "alice"})
    assert claim.status_code == 200
    grant = claim.json()["grant_id"]
    result = client.post("/v1/connector/approve", headers=device, json={"account_id": "alice", "grant_id": grant})
    assert result.status_code == 200
    assert result.json()["expires_at"] == SENTINEL
    return pair, device


def test_capabilities_are_credential_free_and_do_not_create_state(gateway):
    with TestClient(gateway) as client:
        response = client.get("/v1/connector/capabilities", follow_redirects=False)
        assert response.status_code == 200
        assert response.json() == {"supported_grant_modes": ["bounded", "until_revoked"]}
        assert response.headers["cache-control"] == "no-store"
        assert "location" not in response.headers and "set-cookie" not in response.headers
        for table in ("nodes", "enrollments", "sessions", "launches", "audit"):
            assert gateway.state.store.one(f"SELECT count(*) n FROM {table}")["n"] == 0
        for method in ("POST", "HEAD", "PUT"):
            assert client.request(method, "/v1/connector/capabilities").status_code == 405
        for host in ("workspace-gateway:8090", "a" * 24 + ".localhost:8090", "evil.test"):
            assert client.get("http://" + host + "/v1/connector/capabilities").status_code == 404


@pytest.mark.parametrize("headers", [{"Authorization": "Bearer synthetic"}, {"Cookie": "synthetic=x"}])
def test_capabilities_reject_credentials(gateway, headers):
    with TestClient(gateway) as client:
        assert client.get("/v1/connector/capabilities", headers=headers).status_code == 400
        assert gateway.state.store.one("SELECT count(*) n FROM nodes")["n"] == 0


def test_capabilities_reject_query_and_body(gateway):
    with TestClient(gateway) as client:
        assert client.get("/v1/connector/capabilities?enrollment=synthetic").status_code == 400
        assert client.request("GET", "/v1/connector/capabilities", content=b"x").status_code == 413


@pytest.mark.parametrize("value", [0, 1, "true", "false", None, [], {}])
def test_until_revoked_requires_strict_boolean_without_consuming_enrollment(gateway, value):
    with TestClient(gateway) as client:
        response = pair_long(client, until_revoked=value)
        assert response.status_code == 422
        assert "input" not in response.text
        assert gateway.state.store.one("SELECT count(*) n FROM enrollments")["n"] == 1
        assert gateway.state.store.one("SELECT count(*) n FROM nodes")["n"] == 0


@pytest.mark.parametrize("duration", [299, 30 * 86400 + 1])
def test_until_revoked_keeps_finite_duration_validation(gateway, duration):
    with TestClient(gateway) as client:
        assert pair_long(client, expires_in=duration).status_code == 422
        assert gateway.state.store.one("SELECT count(*) n FROM enrollments")["n"] == 1


@pytest.mark.parametrize("explicit_false", [False, True])
def test_bounded_old_payload_and_explicit_false_keep_original_expiry(gateway, explicit_false):
    with TestClient(gateway) as client:
        body = {"name": "Bounded", "expires_in": 30 * 86400, "enrollment_token": enrollment_token(client)}
        if explicit_false:
            body["until_revoked"] = False
        response = client.post("/v1/connector/pairings", json=body)
        assert response.status_code == 200
        assert response.json()["expires_at"] == datetime.fromtimestamp(STAMP + 30 * 86400, UTC).isoformat().replace("+00:00", "Z")


def test_long_pairing_keeps_account_binding_local_confirmation_and_pending_deadline(gateway):
    with TestClient(gateway) as client:
        response = pair_long(client)
        assert response.status_code == 200
        pair = response.json()
        assert pair["expires_at"] == SENTINEL
        assert pair["pairing_expires_at"] == iso(STAMP + 300)
        assert gateway.state.store.node(pair["node_id"])["expires"] == SENTINEL_EPOCH
        device = {"Authorization": "Bearer " + pair["connector_token"]}
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/v1/connector/tunnel", headers=device):
                pass
        assert client.post("/v1/accounts/bob/pairings/claim", headers=SERVICE,
                           json={"code": pair["pairing_code"], "label": "bob"}).status_code == 409
        claim = client.post("/v1/accounts/alice/pairings/claim", headers=SERVICE,
                            json={"code": pair["pairing_code"], "label": "alice"})
        assert claim.status_code == 200 and claim.json()["expires_at"] == SENTINEL
        gateway.state.clock = lambda: STAMP + 301
        assert client.get("/v1/connector/state", headers=device).json()["status"] == "expired"


def test_long_grant_still_uses_short_launch_and_browser_session(gateway):
    with TestClient(gateway) as client:
        pair, device = approved_long(client)
        with client.websocket_connect("/v1/connector/tunnel", headers=device) as tunnel:
            tunnel.receive_json()
            result = client.post(f"/v1/accounts/alice/nodes/{pair['node_id']}/launch", headers=SERVICE)
            assert result.status_code == 200 and result.json()["expires_at"] == iso(STAMP + 60)
            response = client.get(result.json()["url"], follow_redirects=False)
            assert response.status_code == 303 and "Max-Age=3600" in response.headers["set-cookie"]
            gateway.state.clock = lambda: STAMP + 3601
            assert client.get(pair["workspace_origin"] + "/api/graphs").status_code == 401
            assert client.get("/v1/connector/state", headers=device).json()["status"] == "paired"


@pytest.mark.parametrize("account_delete", [False, True])
def test_long_grant_revoke_and_account_delete_close_tunnel(gateway, account_delete):
    with TestClient(gateway) as client:
        pair, device = approved_long(client)
        with client.websocket_connect("/v1/connector/tunnel", headers=device) as tunnel:
            tunnel.receive_json()
            launch(client, pair)
            endpoint = "/v1/accounts/alice" if account_delete else f"/v1/accounts/alice/nodes/{pair['node_id']}"
            assert client.delete(endpoint, headers=SERVICE).status_code == 200
            assert tunnel.receive_json()["type"] == "revoked"
        assert client.get(pair["workspace_origin"] + "/api/graphs").status_code == 401
        assert client.get("/v1/connector/state", headers=device).json()["status"] == "revoked"


def test_restart_preserves_bounded_and_long_grant_without_migration(gateway):
    with TestClient(gateway) as client:
        old, old_device, _ = setup_node(client)
        long, long_device = approved_long(client)
    restored = create_app(gateway.state.config)
    restored.state.clock = lambda: STAMP + 60
    with TestClient(restored) as client:
        for original, device in ((old, old_device), (long, long_device)):
            status = client.get("/v1/connector/state", headers=device).json()
            assert status["status"] == "paired"
            assert status["node_id"] == original["node_id"]
            assert status["expires_at"] == original["expires_at"]


def test_iso_supports_year_9999_portably_and_retains_ordinary_format():
    assert iso(SENTINEL_EPOCH) == SENTINEL
    assert iso(STAMP) == "2023-11-14T22:13:20Z"
    assert iso(None) is None

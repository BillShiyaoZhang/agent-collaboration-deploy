"""Desired transport isolation: legal replay is data, not control flooding."""
import asyncio
import base64
import json
import queue
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from workspace_gateway.app import BrowserPipe, GatewayConfig, Tunnel, create_app
from workspace_gateway.safeguards import Resources
from test_gateway import launch, setup_node


def configured_app(tmp_path, **changes):
    config = GatewayConfig(
        database=str(tmp_path / "replay.sqlite3"),
        secret="test-service-secret",
        workspace_domain="localhost:8090",
        scheme="http",
        **changes,
    )
    app = create_app(config)
    instant = time.time()
    app.state.clock = lambda: instant
    return app


def test_consumed_legal_replay_above_1200_frames_preserves_node_tunnel(tmp_path):
    app = configured_app(tmp_path)
    expected_frames = 1205
    consumed = queue.Queue(maxsize=1)
    with TestClient(app) as client:
        pair, device, _ = setup_node(client)
        with client.websocket_connect("/v1/connector/tunnel", headers=device) as connector:
            assert connector.receive_json()["type"] == "hello"
            launch(client, pair)
            with ThreadPoolExecutor(max_workers=1) as executor:

                def browser():
                    count = 0
                    try:
                        with client.websocket_connect(
                            pair["workspace_origin"].replace("http:", "ws:")
                            + "/ws/runs?after_sequence=0",
                            headers={"Origin": pair["workspace_origin"]},
                        ) as socket:
                            for sequence in range(expected_frames):
                                event = socket.receive_json()
                                assert event == {"type": "run_event", "event": {"sequence": sequence}}
                                count += 1
                                consumed.put(("frame", sequence), timeout=3)
                    except WebSocketDisconnect as error:
                        consumed.put(("closed", error.code, count), timeout=3)
                    return count

                receiver = executor.submit(browser)
                opened = connector.receive_json()
                assert opened["type"] == "ws.open" and opened["path"] == "/ws/runs?after_sequence=0"
                active = app.state.tunnels[pair["node_id"]]
                connector.send_json({"type": "ws.accept", "id": opened["id"], "subprotocol": None})
                for sequence in range(expected_frames):
                    connector.send_json(
                        {
                            "type": "ws.data",
                            "id": opened["id"],
                            "kind": "text",
                            "data": json.dumps({"type": "run_event", "event": {"sequence": sequence}}),
                        }
                    )
                    outcome = consumed.get(timeout=3)
                    assert outcome == ("frame", sequence), (
                        f"Legal consumed replay was terminated at frame {sequence}: {outcome}; "
                        f"node_tunnel_closed={active.closed}; "
                        f"backpressure_closes={app.state.resources.metrics['backpressure_closes']}"
                    )
                assert receiver.result(timeout=3) == expected_frames
                assert not active.closed
                assert app.state.resources.metrics["backpressure_closes"] == 0
                assert app.state.resources.queued_bytes == 0
                assert client.get("/v1/connector/state", headers=device).json()["online"] is True
                connector.send_json({"type": "ping"})
                for _ in range(3):
                    reply = connector.receive_json()
                    if reply["type"] == "pong":
                        break
                else:
                    raise AssertionError("Legal history replay must leave the connector responsive")


def test_control_ping_flood_remains_bounded(tmp_path):
    app = configured_app(tmp_path, tunnel_rate=3)
    with TestClient(app) as client:
        pair, device, _ = setup_node(client)
        with client.websocket_connect("/v1/connector/tunnel", headers=device) as connector:
            assert connector.receive_json()["type"] == "hello"
            active = app.state.tunnels[pair["node_id"]]
            for _ in range(3):
                connector.send_json({"type": "ping"})
                assert connector.receive_json() == {"type": "pong"}
            connector.send_json({"type": "ping"})
            close = connector.receive()
            assert close["type"] == "websocket.close" and close["code"] == 1012
            assert active.closed
        state = client.get("/v1/connector/state", headers=device).json()
        assert state["status"] == "paired" and state["online"] is False
        assert pair["node_id"] not in app.state.tunnels
        assert app.state.resources.counts["tunnel"] == 0


def test_4053_frame_burst_with_consuming_browser_preserves_node(tmp_path):
    app = configured_app(tmp_path)
    with TestClient(app) as client:
        pair, device, _ = setup_node(client)
        with client.websocket_connect("/v1/connector/tunnel", headers=device) as connector:
            connector.receive_json()
            launch(client, pair)
            with ThreadPoolExecutor(max_workers=1) as executor:
                def browser():
                    received = 0
                    try:
                        with client.websocket_connect(
                            pair["workspace_origin"].replace("http:", "ws:") + "/ws/runs?after_sequence=0"
                        ) as socket:
                            for sequence in range(4053):
                                assert socket.receive_json() == {"sequence": sequence}
                                received += 1
                    except WebSocketDisconnect:
                        pass
                    return received
                receiver = executor.submit(browser)
                opened = connector.receive_json()
                active = app.state.tunnels[pair["node_id"]]
                connector.send_json({"type": "ws.accept", "id": opened["id"], "subprotocol": None})
                for sequence in range(4053):
                    connector.send_json({
                        "type": "ws.data", "id": opened["id"], "kind": "text",
                        "data": json.dumps({"sequence": sequence}),
                    })
                received = receiver.result(timeout=10)
                assert received == 4053, (
                    f"Normally consuming browser received only {received} burst frames; "
                    f"tunnel_closed={active.closed}, "
                    f"backpressure_closes={app.state.resources.metrics['backpressure_closes']}"
                )
                assert not active.closed
                assert app.state.resources.metrics["backpressure_closes"] == 0
                assert app.state.resources.queued_bytes == 0


@pytest.mark.parametrize("kind", ["ping", "unknown_correlation_data"])
def test_control_rejection_is_observable_and_unknown_data_cannot_bypass_it(tmp_path, kind):
    app = configured_app(tmp_path, tunnel_rate=3)
    with TestClient(app) as client:
        _, device, _ = setup_node(client)
        with client.websocket_connect("/v1/connector/tunnel", headers=device) as connector:
            connector.receive_json()
            for _ in range(4):
                connector.send_json(
                    {"type": "ping"} if kind == "ping" else
                    {"type": "ws.data", "id": "never-issued", "kind": "text", "data": "data"}
                )
            for _ in range(4):
                message = connector.receive()
                if message["type"] == "websocket.close":
                    assert message["code"] == 1012
                    break
            else:
                raise AssertionError("Control/unknown correlation flood was not closed")
            assert app.state.resources.metrics["rate_rejections"] == 1
            assert app.state.resources.metrics["tunnel_control_rate_rejections"] == 1


def test_closed_lane_late_burst_preserves_other_lane_http_ping_and_revoke(tmp_path):
    app = configured_app(tmp_path)
    with TestClient(app) as client:
        pair, device, _ = setup_node(client)
        with client.websocket_connect("/v1/connector/tunnel", headers=device) as connector:
            connector.receive_json()
            launch(client, pair)
            url = pair["workspace_origin"].replace("http:", "ws:")
            with ThreadPoolExecutor(max_workers=2) as executor:
                def one_frame(path):
                    with client.websocket_connect(url + path) as socket:
                        return socket.receive_text()
                first = executor.submit(one_frame, "/ws/runs")
                first_open = connector.receive_json()
                connector.send_json({"type": "ws.accept", "id": first_open["id"]})
                connector.send_json({"type": "ws.data", "id": first_open["id"], "kind": "text", "data": "done"})
                assert first.result(timeout=3) == "done"
                active = app.state.tunnels[pair["node_id"]]
                assert active.was_closed(first_open["id"], app.state.clock())
                second = executor.submit(one_frame, "/ws/chat")
                for _ in range(2):
                    second_open = connector.receive_json()
                    if second_open["type"] == "ws.open":
                        break
                assert second_open["type"] == "ws.open"
                connector.send_json({"type": "ws.accept", "id": second_open["id"]})
                for _ in range(1205):
                    connector.send_json({"type": "ws.data", "id": first_open["id"], "kind": "text", "data": "in-flight"})
                connector.send_json({"type": "ping"})
                assert connector.receive_json() == {"type": "pong"}
                assert not active.closed and second_open["id"] in active.browser
                assert app.state.resources.metrics["rate_rejections"] == 0
                request = executor.submit(client.get, pair["workspace_origin"] + "/api/sessions")
                http = connector.receive_json()
                assert http["type"] == "http.request"
                connector.send_json({"type": "http.response", "id": http["id"], "status": 200,
                                     "headers": [], "body": base64.b64encode(b"[]").decode()})
                assert request.result(timeout=3).status_code == 200
                connector.send_json({"type": "ws.data", "id": second_open["id"], "kind": "text", "data": "healthy"})
                assert second.result(timeout=3) == "healthy"
            assert app.state.resources.queued_bytes == 0
            assert app.state.resources.counts["ws"] == 0
            assert client.post("/v1/connector/revoke", headers=device).status_code == 200
            for _ in range(2):
                notice = connector.receive_json()
                if notice["type"] == "revoked":
                    break
            assert notice["type"] == "revoked"
            assert connector.receive()["code"] == 1008
        assert app.state.resources.queued_bytes == app.state.resources.buffer_bytes == 0


@pytest.mark.parametrize("budget", ["frames", "bytes"])
def test_node_data_budget_rejection_is_observable_and_stops_tunnel(tmp_path, budget):
    app = configured_app(tmp_path, **({"tunnel_data_rate": 1} if budget == "frames" else {"tunnel_data_bytes": 1}))
    with TestClient(app) as client:
        pair, device, _ = setup_node(client)
        with client.websocket_connect("/v1/connector/tunnel", headers=device) as connector:
            connector.receive_json()
            active = app.state.tunnels[pair["node_id"]]
            # A server-issued, recently closed lane is still subject to data quotas.
            active.remember_browser("issued", app.state.clock(), 60)
            for _ in range(2 if budget == "frames" else 1):
                connector.send_json({"type": "ws.data", "id": "issued", "kind": "text", "data": "late"})
            assert connector.receive()["code"] == 1012
            assert app.state.resources.metrics["rate_rejections"] == 1
            assert app.state.resources.metrics["tunnel_data_rate_rejections"] == 1
            assert app.state.resources.metrics["tunnel_control_rate_rejections"] == 0
        assert app.state.resources.buffer_bytes == app.state.resources.queued_bytes == 0
        assert client.get("/v1/connector/state", headers=device).json()["status"] == "paired"
        # Reconnecting cannot reset this node's budget.
        with client.websocket_connect("/v1/connector/tunnel", headers=device) as connector:
            connector.receive_json()
            active = app.state.tunnels[pair["node_id"]]
            active.remember_browser("issued-again", app.state.clock(), 60)
            connector.send_json({"type": "ws.data", "id": "issued-again", "kind": "text", "data": "late"})
            assert connector.receive()["code"] == 1012
            assert app.state.resources.metrics["tunnel_data_rate_rejections"] == 2


def test_closed_lane_tombstones_have_bounded_count_and_expire():
    tunnel = Tunnel(None, "synthetic")
    for index in range(1000):
        tunnel.remember_browser(str(index), 100, 60)
    assert len(tunnel.recently_closed) == 256
    assert not tunnel.was_closed("0", 100)
    assert tunnel.was_closed("999", 159)
    assert not tunnel.was_closed("999", 160)
    assert not tunnel.recently_closed


@pytest.mark.parametrize("ending", ["cancel", "shutdown", "revoke"])
def test_pending_queue_insertions_release_each_charge_once(ending):
    async def exercise():
        resources = Resources(GatewayConfig(secret="synthetic", browser_queue_size=1))
        pipe = BrowserPipe(asyncio.get_running_loop().create_future(), resources, 1)
        message = {"type": "ws.data", "kind": "text", "data": "synthetic"}
        await pipe.put(message)
        initial = resources.queued_bytes
        waiting = asyncio.create_task(pipe.put(message))
        for _ in range(10):
            await asyncio.sleep(0)
            if resources.queued_bytes == initial * 2:
                break
        assert resources.queued_bytes == initial * 2 and not waiting.done()
        if ending == "cancel":
            waiting.cancel()
            with pytest.raises(asyncio.CancelledError):
                await waiting
            assert resources.queued_bytes == initial
            pipe.clear()
        else:
            tunnel = Tunnel(None, "synthetic", browser={"issued": pipe})
            if ending == "revoke":
                await tunnel.close("Authorization revoked", revoked=True)
            else:
                pipe.shutdown(False, "Browser disconnected")
            assert await waiting is False
            pipe.clear()
        assert not pipe.pending_puts
        assert resources.queued_bytes == resources.buffer_bytes == 0
    asyncio.run(exercise())

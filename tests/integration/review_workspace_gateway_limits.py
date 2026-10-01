"""Reproduce the reviewed proposal's limits using temporary SQLite and ASGI only.

This is an explicit review probe, not a live network or production load test.
Run with --gateway-root pointing at Deploy proposal 94aeccb/workspace-gateway.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import secrets
import sys
import tempfile
import time
from pathlib import Path


def emit(label, values):
    print(label, json.dumps(values, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway-root", type=Path, required=True)
    args = parser.parse_args()
    gateway_root = args.gateway_root.resolve()
    if not (gateway_root / "workspace_gateway" / "app.py").is_file():
        parser.error("--gateway-root must contain workspace_gateway/app.py")
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(gateway_root))

    import httpx
    from fastapi.testclient import TestClient
    from workspace_gateway.app import COOKIE, GatewayConfig, Tunnel, create_app, digest

    secret = secrets.token_urlsafe(32)
    with tempfile.TemporaryDirectory(prefix="gateway-review-") as temporary:
        config = GatewayConfig(
            secret=secret, database=str(Path(temporary) / "capacity.sqlite"), max_nodes=2
        )
        app = create_app(config)
        with TestClient(app) as client:
            pairs = [client.post("/v1/connector/pairings", json={"name": "review"}) for _ in range(3)]
            statuses = [response.status_code for response in pairs]
            assert statuses == [200, 200, 429], statuses
            device = {"Authorization": "Bearer " + pairs[0].json()["connector_token"]}
            before = app.state.store.one("SELECT count(*) AS n FROM audit")["n"]
            revoked = [client.post("/v1/connector/revoke", headers=device).status_code for _ in range(3)]
            after = app.state.store.one("SELECT count(*) AS n FROM audit")["n"]
            assert revoked == [200, 200, 200] and after - before == 3, (revoked, before, after)
            emit("REPEATED_REVOKE", {"statuses": revoked, "audit_before": before, "audit_after": after})
            later = time.time() + 100000
            app.state.clock = lambda: later
            time.sleep(0.4)  # Wait longer than the proposal's 0.25-second sweep interval.
            status = client.post("/v1/connector/pairings", json={"name": "after_expiry"}).status_code
            count = app.state.store.one("SELECT count(*) AS n FROM nodes")["n"]
            assert status == 429 and count == 2, (status, count)
            emit("ANONYMOUS_CAPACITY", {
                "initial_status": statuses, "post_expiry_status": status, "nodes_after_sweep": count
            })
        app = create_app(config)
        app.state.clock = lambda: later
        with TestClient(app) as client:
            status = client.post("/v1/connector/pairings", json={"name": "after_restart"}).status_code
            assert status == 429, status
            emit("RESTART_CAPACITY", {"status": status})

        app = create_app(GatewayConfig(
            secret=secret, database=str(Path(temporary) / "body.sqlite"),
            http_concurrency=16, request_timeout=0.05
        ))
        with TestClient(app) as client:
            pair = client.post("/v1/connector/pairings", json={"name": "review"})
            assert pair.status_code == 200, pair.status_code
            pair = pair.json()
            service = {"Authorization": "Bearer " + secret}
            claim = client.post("/v1/accounts/review-account/pairings/claim", headers=service,
                                json={"code": pair["pairing_code"], "label": "review synthetic account"})
            assert claim.status_code == 200, claim.status_code
            node = claim.json()
            approved = client.post("/v1/connector/approve",
                                   headers={"Authorization": "Bearer " + pair["connector_token"]},
                                   json={"account_id": node["account_id"], "grant_id": node["grant_id"]})
            assert approved.status_code == 200, approved.status_code
            session = secrets.token_urlsafe(32)
            app.state.store.db.execute(
                "INSERT INTO sessions(token_hash,node_id,grant_id,expires) VALUES(?,?,?,?)",
                (digest(session), node["node_id"], node["grant_id"], time.time() + 1000)
            )

            class FakeSocket:
                async def send_json(self, message):
                    raise AssertionError("Unexpected dispatch before body completion")

                async def close(self, **kwargs):
                    pass

            active = Tunnel(FakeSocket(), node["node_id"])
            app.state.tunnels[node["node_id"]] = active

            async def check_body():
                entered = []

                class Slow(httpx.AsyncByteStream):
                    async def __aiter__(self):
                        entered.append(1)
                        yield b"x"
                        await asyncio.Event().wait()
                        yield b"y"

                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app)) as asynchronous:
                    tasks = [asyncio.create_task(asynchronous.post(
                        pair["workspace_origin"] + "/api/sessions",
                        headers={"cookie": COOKIE + "=" + session, "origin": pair["workspace_origin"]},
                        content=Slow()
                    )) for _ in range(20)]
                    try:
                        await asyncio.sleep(0.25)
                        result = {
                            "configured_node_concurrency": 16, "configured_timeout": 0.05,
                            "elapsed": 0.25, "streams_entered": len(entered),
                            "tasks_pending": sum(not task.done() for task in tasks),
                            "reserved_tunnel_http": len(active.http)
                        }
                        emit("SLOW_BODY", result)
                        assert result["streams_entered"] == result["tasks_pending"] == 20, result
                        assert result["reserved_tunnel_http"] == 0, result
                    finally:
                        for task in tasks:
                            task.cancel()
                        await asyncio.gather(*tasks, return_exceptions=True)

            asyncio.run(check_body())


if __name__ == "__main__":
    main()

# Ambient Workspace Gateway proposal

This isolated proposal adds a single-process HTTP/WebSocket relay beside the existing Web and Platform services. It never schedules Ambient Runs or stores proxied business bodies. The protocol and boundaries are described in [the design](../docs/architecture/WORKSPACE_GATEWAY_PROPOSAL.md).

## Local development

Install `requirements-dev.txt` in a disposable Python 3.11+ environment. Set `WORKSPACE_GATEWAY_SECRET` to a separate random service secret, `WORKSPACE_GATEWAY_DOMAIN=localhost:8090`, and `WORKSPACE_GATEWAY_SCHEME=http`. From this directory run:

```sh
uvicorn workspace_gateway.app:create_app --factory --host 127.0.0.1 --port 8090 --no-proxy-headers --no-access-log --ws-max-size 2861744
pytest -c pytest.ini --confcutdir=. tests -q
```

Configure the proposed Web BFF with the same secret and `WORKSPACE_GATEWAY_URL=http://127.0.0.1:8090`. Configure Ambient with that Gateway URL and the Web portal URL. Ambient initiates pairing, the signed-in portal claims it, and the owner approves it in the local Ambient window. Opening the node from the portal consumes a one-use link and sets a separate host-only workspace cookie. Modern browsers resolve `*.localhost` to loopback; command-line HTTP clients may require a loopback resolver mapping.

The optional [Compose overlay](../docker-compose.workspace.yml) exposes Gateway only on local loopback. It deliberately does not alter existing production nginx routes. Production operators must configure a dedicated wildcard workspace hostname and TLS ingress, preserve the Host header and WebSocket upgrades, restrict internal BFF service access, suppress/redact launch query strings in ingress access logs, protect the SQLite volume and backups, and enforce deployment-wide registration/rate/billing limits. `WORKSPACE_GATEWAY_SCHEME=https` controls secure workspace cookies; direct plain HTTP ingress must never remain publicly reachable.

HTTP and response bodies are limited to 2 MiB, WS frames to 256 KiB, and each node to 16 HTTP plus 16 browser WS connections. HTTP and WS establishment waits expire after 30 seconds. Cookies expire within one hour and within the local grant. Revocation and grant/session expiry also invalidate live connections. Startup requires a secret and refuses public HTTP workspace origins. The default SQLite file is ignored local state; do not commit it. One active Gateway instance is supported; multi-replica routing, P2P, shared workspaces and cloud execution are outside this proposal.

Only fixed public Frame assets may retain gzip content encoding. The current Babel vendor exceeds the uncompressed 2 MiB ceiling, so Connector requests gzip and relays its raw compressed payload within the same 2 MiB wire budget. Other services retain the ordinary body limit and drop encoding when rewritten. No CSP or Widget sandbox permissions are expanded.

For local tests using an existing Ambient runtime, run `uv run --no-sync python -m pytest -c .cache/agent-collaboration-proposal/workspace-gateway/pytest.ini --confcutdir=.cache/agent-collaboration-proposal/workspace-gateway .cache/agent-collaboration-proposal/workspace-gateway/tests -q` from the Ambient checkout. This only confirms isolated relay contracts; the browser and real Connector integration need their own recorded validation.

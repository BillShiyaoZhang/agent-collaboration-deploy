# Ambient Workspace Gateway

This single-process HTTP/WebSocket relay sits beside Web and Platform. Ambient owns the local workspace, secrets, Apps and Runs. Gateway never schedules a Run or stores proxied business bodies. The original [proposal](../docs/architecture/WORKSPACE_GATEWAY_PROPOSAL.md) is a design baseline; the contracts below describe the reviewed implementation on this branch. Source changes do not prove a production deployment.

## Run and configure

Install requirements-dev.txt in a disposable Python 3.11+ environment. Set WORKSPACE_GATEWAY_SECRET to a separate random service secret, WORKSPACE_GATEWAY_DOMAIN=localhost:8090, WORKSPACE_GATEWAY_PUBLIC_URL=http://localhost:8090 and WORKSPACE_GATEWAY_SCHEME=http. From this directory run:

    python -m workspace_gateway.launcher
    pytest -c pytest.ini --confcutdir=. tests -q

Web BFF needs the same service secret, the internal WORKSPACE_GATEWAY_URL and the public control URL. The [Compose overlay](../docker-compose.workspace.yml) and [operations guide](../docs/operations/WORKSPACE_GATEWAY.md) cover HTTPS ingress, database volume and container limits. Runtime derives the exact control host from WORKSPACE_GATEWAY_PUBLIC_URL unless WORKSPACE_GATEWAY_CONTROL_HOST is explicit. Tests explicitly use the control host testserver. WORKSPACE_GATEWAY_SERVICE_HOST is an explicit optional internal BFF Host (Compose: workspace-gateway:8090). Only account/metrics routes accept it, and require the service Bearer; Connector and health routes still require the public control Host. Container loopback health checks must set that Host header.

Run one process and one replica. Its event loop atomically maintains admission and resource accounting. Multi-replica routing, P2P, shared workspaces, cloud execution and automatic request replay are outside this implementation.

## Enrollment and pairing

1. Signed-in portal BFF calls service-authenticated POST /v1/accounts/{account_id}/enrollments with {label}, 1..200 characters; account and label come from the server-side session. Response: {enrollment_token,expires_at}.
2. Owner transfers that one-use enrollment token to local Ambient. It expires after at most 300 seconds. Treat it as a bearer secret; exclude it from query strings, logs and browser persistent storage.
3. Ambient calls public POST /v1/connector/pairings with {enrollment_token,name,scopes,expires_in}. Name is 1..100 characters; scopes require workspace.control and may include workspace.manage; grant lifetime is 300 seconds..30 days. Response retains {node_id,connector_token,pairing_code,pairing_expires_at,expires_at,workspace_origin}.
4. Enrollment consumption and pending-node creation commit in one SQLite transaction. The node belongs to the enrollment account immediately. Existing POST /v1/accounts/{account_id}/pairings/claim with {code,label} must match that account; cross-account rejection preserves the code.
5. Ambient displays claimed account, scopes and expiry. Local POST /v1/connector/approve still requires device Bearer and matching {account_id,grant_id}. Only a paired node can open /v1/connector/tunnel.
6. Service-authenticated POST /v1/accounts/{account_id}/nodes/{node_id}/launch returns {url,expires_at}. The node host consumes /_ambient/launch?ticket=... once and redirects to /. HTTPS cookie is __Host-ambient_workspace, Secure, HttpOnly, SameSite=Lax, Path=/, no Domain. HTTP localhost uses ambient_workspace.

Missing/invalid fields: 422. Invalid, expired or replayed enrollment/mismatched claim: 409. Terminal deleted account: 410. Quota/rate rejection: 429 with Retry-After (default 60 seconds). Capacity rejection preserves an enrollment until its original expiry. A lost successful pairing response cannot replay its device secret: the orphaned pending node expires within 300 seconds, then the user obtains a new portal token. Ambient must not silently loop through new enrollments. Local explicit approval remains mandatory.

Existing paired device tokens, grant IDs, scopes and expiry survive schema migration/restart. Legacy pending/claimed entries without enrollment expire on upgrade. Do not reinitialize identities. Moving from development HTTP to HTTPS requires a fresh launch cookie.

## Pagination, revocation and retention

Service-authenticated GET /v1/accounts/{account_id}/nodes?view=active|history&limit=50&cursor=... returns {nodes,next_cursor}, with next_cursor always null or opaque base64url. Limit is 1..100. Active is the default: unexpired pending, claimed and paired. History contains revoked/expired nodes. Cursors use authenticated account/view binding and stable created DESC,node_id DESC keyset ordering; invalid/mismatched cursors return 422. This is a live list, not a snapshot: refresh page one for new nodes, and expiry/revocation can move nodes between views.

Device/single-node/bulk/account revocation is state and audit idempotent. Revocation invalidates cookies/tickets. Deleted-account tombstones are permanent and never garbage collected. History and audit keep up to seven days and at most 10,000 rows each, whichever bound is reached first. History age begins when a grant is retired. Active nodes are not deleted to free capacity. Startup, admissions and sweeps reclaim expired enrollments, pending/claimed nodes, tickets and sessions.

SQLite uses bounded page count, WAL checkpoints and incremental vacuum. A legacy database needs a one-time VACUUM for auto-vacuum: back it up and allow temporary disk headroom. If existing state exceeds the configured budget, startup fails and asks for a larger budget, preserving identities. Audit stores only fixed event names, time, node/account IDs, status and byte counts; no URL/token/business body. Retention never removes account tombstones.

## Admission and resource bounds

HTTP reserves node/global slots and a buffer allowance before receiving a body. One deadline covers upload, tunnel lock/send, connector reply and ASGI response send. Disconnect/cancellation releases slots and correlations. Declared GET/HEAD bodies are rejected without reading slow bodies. HTTP requests/responses are at most 2 MiB, including rewritten HTML; browser WS frames are at most 256 KiB.

Browser pipes have four queued frames and a global byte budget. Overflow closes and drains the connection. Browser/connector writes have a deadline; grant/session expiry and revocation close live channels. Uvicorn uses two queued WS messages, an HTTP-derived wire ceiling, one worker and an HTTP transport connection limit. Uvicorn processes WS upgrades before that HTTP limit; WS admission therefore depends on ingress connection limits plus Gateway authentication/slot/buffer gates.

These are application accounting budgets, not an exact process RAM cap. Python objects, JSON temporaries, protocol/kernel/TLS buffers and allocator overhead need container headroom. The production overlay defaults to 256 MiB application reservation and a 384 MiB container. This supports the initial single active workspace page with its four browser WebSockets; two fully active pages exceed that reservation budget even though the configured connection ceilings are higher. Validate RSS and rejection metrics under the real workload before choosing capacity.

Only these exact public Frame paths bypass browser sessions: /_ambient/frame.html, /frame_shell.css, /frame_shell.mjs, /controller_facade.mjs, /presentation_context.mjs, /vendor/babel.min.js, /vendor/htm-preact.js. Only these assets may preserve gzip. Arbitrary /vendor/* is not public. Cookie/bearer/proxy identity and hop-by-hop headers are stripped; local connection-management paths are blocked. CSP and Widget sandbox permissions remain intact.

All configuration fields map to WORKSPACE_GATEWAY_ plus the uppercase field, except workspace_domain maps to DOMAIN. Values must be positive/finite; integer fields reject fractions. Unsupported protocol/TTL/queue ceilings fail startup.

| Setting suffix | Standalone default | Meaning |
| --- | --- | --- |
| HTTP_LIMIT / FRAME_LIMIT | 2097152 / 262144 | Decoded HTTP/WS ceilings; cannot exceed protocol |
| HTTP_CONCURRENCY / WS_CONCURRENCY | 16 / 16 | Per-node HTTP / browser WS |
| GLOBAL_HTTP_CONCURRENCY / GLOBAL_WS_CONCURRENCY / GLOBAL_TUNNEL_CONCURRENCY | 64 / 64 / 32 | Global caps; byte budget may reject earlier |
| CONTROL_CONCURRENCY / CONTROL_BODY_LIMIT | 16 / 16384 | Control-plane connections/body |
| BUFFER_BYTES / QUEUED_BYTES | 268435456 / 8388608 | Application reservation / queued frames |
| BROWSER_QUEUE_SIZE / WS_MAX_QUEUE | 4 / 2 | App / Uvicorn queues; maxima 8 / 4 |
| REQUEST_TIMEOUT / WS_SEND_TIMEOUT / TUNNEL_IDLE_TIMEOUT | 30 / 10 / 90 | HTTP+WS handshake / writes / idle connector seconds |
| MAX_NODES / MAX_ACCOUNT_NODES | 1000 / 10 | Active nodes globally / per account |
| MAX_PENDING / MAX_ACCOUNT_PENDING | 100 / 3 | Pending plus claimed |
| MAX_ENROLLMENTS / MAX_ACCOUNT_ENROLLMENTS | 200 / 3 | Live one-use enrollments |
| ENROLLMENT_TTL / PAIRING_TTL | 300 / 300 | Token / approval deadline seconds |
| MAX_LAUNCHES / MAX_SESSIONS / MAX_NODE_SESSIONS | 1000 / 10000 / 100 | Live ticket / session records |
| SOURCE_RATE / ACCOUNT_RATE / ACCOUNT_READ_RATE | 10 / 20 / 120 | Anonymous pair source / account mutation and pairing categories / reads per window |
| DEVICE_RATE / DEVICE_STATE_RATE / TUNNEL_RATE | 60 / 120 / 1200 | Device actions+reconnect / polling / tunnel messages per window |
| RATE_WINDOW / SOURCE_ENTRIES / RATE_ENTRIES | 60 / 1024 / 2048 | Window seconds / bounded counter keys |
| AUDIT_MAX_ROWS / HISTORY_MAX_ROWS | 10000 / 10000 | Historical row caps |
| AUDIT_RETENTION / HISTORY_RETENTION | 604800 / 604800 | Retention seconds |
| DATABASE_LIMIT_BYTES / MAINTENANCE_INTERVAL | 134217728 / 60 | SQLite page budget / disk maintenance seconds |
| LAUNCH_TTL / SESSION_TTL | 60 / 3600 | Ticket / cookie lifetime, also bounded by grant |
| UVICORN_CONCURRENCY | 256 | Launcher HTTP transport cap, maximum 1024 |

Per HTTP reserves 6*HTTP_LIMIT+131072 bytes; browser WS reserves (WS_MAX_QUEUE+1)*(4*WIRE+1024)+12*FRAME_LIMIT+4096; a tunnel reserves (WS_MAX_QUEUE+1)*(4*WIRE+1024), where WIRE=HTTP_LIMIT*4//3+65536. The shared Uvicorn transport ceiling also applies to browser sockets: their reservation includes its receive queue even though application frames are smaller. Transport/application text reservations conservatively allow four bytes per Python character. Each queued upstream message additionally charges 4*UTF8_JSON_BYTES+512 until sent/discarded; byte caps may reduce effective concurrency well before connection caps. Tune combined limits with memory. Compose may choose tighter defaults than standalone development.

Only peers in WORKSPACE_GATEWAY_TRUSTED_PROXY_CIDRS (default empty) can supply X-Real-IP. Client forwarding headers cannot rotate source counters. Rate tables reject new keys at capacity and recycle expired counters. Anonymous source keys are hashed and never persisted. Service-authenticated GET /v1/metrics exposes fixed counters and aggregate connection/buffer totals, with no account/source labels.

Production requires exact control host/public URL, WORKSPACE_GATEWAY_PORTAL_ORIGIN, and a printable ASCII service secret of at least 32 characters. Portal must use a different registrable domain from workspace/control; workspace and control share a registrable domain. Validation uses the vendored [official Public Suffix List](https://publicsuffix.org/list/) (ICANN+PRIVATE, MPL-2.0) with IDNA, wildcard and exception rules; unknown suffixes fail closed. Localhost is the explicit HTTP development exception.

## Verification scope

Isolated SQLite, real ASGI receive/send, fake connectors and TestClient HTTP/WS cover enrollment replay/account binding, capacity recovery, audit idempotency/retention, legacy identity migration, pagination, slow upload/response send, disconnect/cancel, node/global/buffer quotas, HTTPS cookie attributes, fixed Frame assets and live WS backpressure. They do not prove real Ambient browser integration or production TLS. Record those after Ambient implements enrollment UI and Connector admission.

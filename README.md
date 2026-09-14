# Agent Collaboration Deployment

Unified docker-compose setup for agent-comm-platform and agent-collaboration-web.

## Architecture

- **nginx**: Reverse proxy on port 80/443 with Let's Encrypt SSL, routes `/`, `/healthz`, `/api/v1/`, `/admin`, and `/docs` → platform; other paths, including `/api/auth/`, → web
- **web**: Next.js frontend on internal port 3000
- **platform**: Go backend on internal port 8080, exposes libp2p on port 45041

See [product boundaries and extension ports](docs/ARCHITECTURE_AND_EXTENSION_PORTS.md)
and [architecture diagrams](docs/PROJECT_ARCHITECTURE_DIAGRAMS.md).
The Web is a remote agent workbench; contacts, collaboration state and conversation
history belong to the agent. The standalone Python runtime supports host, memory,
interaction and transport adapters; Hermes is the first integrated host.

The 2026-09-14 early-access release is live. Start from the
[invitation and installation packages](https://agent-communication.online/downloads/agent-comm-early-access-invitation.pdf)
or the [release record](docs/EARLY_ACCESS_RELEASE_2026-09-14.md).
The initial deployment was built from a verified workspace snapshot. This
repository pins the corresponding SDK, platform and Web commits through its
nested submodules; the published source ZIP preserves the original release snapshot.

## Prerequisites

Install Docker with Compose v2, then clone this deployment repository with its
pinned, nested submodules. Compose builds from directories inside this checkout:

```
agent-collaboration-deploy/
├── docker-compose.yml
├── agent-collaboration-web/       # Next.js frontend submodule
└── agent-comm-platform/          # Go backend submodule
    └── agent-comm/               # SDK/helper and current connectors submodule
```

```bash
git clone --recurse-submodules https://github.com/BillShiyaoZhang/agent-collaboration-deploy.git
cd agent-collaboration-deploy
```

For an existing clone, initialize both levels before the first build:

```bash
git submodule sync --recursive
git submodule update --init --recursive
```

These commands check out the versions recorded by this repository. Separate
sibling clones are not used by Compose.

## DNS Setup

Before requesting an SSL cert, point your domain to this server's public IP:

| Type | Name | Value |
|------|------|-------|
| A | `agent-communication.online` | `8.130.40.38` |
| A | `www.agent-communication.online` | `8.130.40.38` |

Verify with `dig agent-communication.online +short` once DNS propagates.

## SSL Certificate (Let's Encrypt)

```bash
ssh root@8.130.40.38
apt update && apt install -y certbot

# Temporarily stop nginx so certbot can bind port 80 for the HTTP-01 challenge
cd ~/agent-collaboration-deploy
docker compose stop nginx

# Request a cert covering both the apex and www subdomain
certbot certonly --standalone \
  -d agent-communication.online \
  -d www.agent-communication.online \
  --email your-email@example.com \
  --agree-tos --non-interactive

# Restart nginx (it will mount /etc/letsencrypt and pick up the cert)
docker compose start nginx
```

Certs land in `/etc/letsencrypt/live/agent-communication.online/` and are mounted into the nginx container via the volume declared in `docker-compose.yml`.

## Configuration

Create a `.env` file in this directory:

```bash
NEXTAUTH_SECRET=<generate-with: openssl rand -base64 32>
PLATFORM_ADMIN_TOKEN=<generate-with: openssl rand -hex 16>
NEXTAUTH_URL=https://agent-communication.online
```

## Deployment

```bash
# Run from the deployment repository root.
git submodule update --init --recursive
docker compose config --quiet
docker compose up --build -d
```

## Update Deployment

After this repository pins a new platform or web release, run from its root on
the server with a clean source checkout:

```bash
git pull --ff-only
git submodule sync --recursive
git submodule update --init --recursive
docker compose config --quiet
docker compose up --build -d
```

Use the recorded submodule commits; `git submodule update --remote` would select
different code from the deployed release.

The Web entrypoint applies `prisma/remote-console.sql` idempotently. This additive
migration preserves legacy tables and rows while adding the remote request cache
and per-user connection uniqueness. Back up the database before upgrades; the
entrypoint does not run `db push --accept-data-loss`.

## Hermes connection

Compose runs the cloud platform, web and nginx. Run the helper and Hermes Gateway
on the same machine, using the current connector from
[`agent-comm-platform/agent-comm/connectors/hermes-platform`](agent-comm-platform/agent-comm/connectors/hermes-platform/README.md).
The deployment repository's root `connectors/` implementations and installation
CLI are retired. Use the SDK directory installation below, including when
upgrading an existing deployment.

On the Hermes machine, initialize this repository recursively as above. With
Go 1.25.7 or newer, build the helper from its pinned SDK source:

```bash
# From the deployment repository root on the Hermes machine.
DEPLOY_DIR="$(pwd)"
mkdir -p "$DEPLOY_DIR/build"
(
  cd "$DEPLOY_DIR/agent-comm-platform/agent-comm"
  go build -o "$DEPLOY_DIR/build/agent-comm-helper" ./cmd/helper
)
"$DEPLOY_DIR/build/agent-comm-helper" init /absolute/path/to/hermes-agent-keys
"$DEPLOY_DIR/build/agent-comm-helper" daemon /absolute/path/to/hermes-agent-keys https://agent-communication.online 45042
```

The daemon stays in the foreground; use the SDK's
[service instructions](agent-comm-platform/agent-comm/README.md)
for persistent operation. Keep the existing identity directory and `mailbox.db`
when upgrading. Each helper identity needs its own data directory and local port.
Set the service's `ExecStart` or `ProgramArguments` to the absolute helper path
built above and the same existing identity directory; adjust the SDK examples'
paths to match this installation.

In another terminal, use the **same Python 3.11+ environment as Hermes Gateway**:

```bash
python -m pip install /absolute/path/to/agent-collaboration-deploy/agent-comm-platform/agent-comm/python /absolute/path/to/agent-collaboration-deploy/agent-comm-platform/agent-comm/connectors/hermes-platform
python -c "from hermes_constants import get_hermes_home; print(get_hermes_home())"
curl --fail http://127.0.0.1:45042/info
```

Follow the [SDK connector instructions](agent-comm-platform/agent-comm/connectors/hermes-platform/README.md)
to enable `plugins.enabled: [agent_comm]` and merge
`platforms.agent_comm.extra` into the actual Hermes profile. Set its
`platform_url` to **`http://127.0.0.1:45042`**, its `urn` to the helper's identity
from `/info`, and `allow_from` to the explicitly allowed peer URNs. The cloud
HTTPS address belongs in the helper's `daemon` command; the connector connects
to the loopback helper API. It does not use the platform admin token.

Restart Gateway using its normal service manager and confirm an established SSE
connection. Preserve the connector receipts database, and use one active
connector consumer per helper inbox. See the [migration notes](docs/AGENT_COMM_CONNECTOR_DESIGN.md)
for removing a duplicate old plugin installation without losing identity or state.

## SSL Auto-Renewal

The existing server uses Certbot's `webroot` renewal with the Compose mount
`./acme-challenge:/var/www/certbot:ro`. HTTP requests under
`/.well-known/acme-challenge/` are served by nginx without a redirect. Renewal
does not need to stop the workbench.

```bash
sudo systemctl enable --now certbot-renew.timer
sudo systemctl status certbot-renew.timer
```

After a successful renewal, the root-owned deploy hook at
`/etc/letsencrypt/renewal-hooks/deploy/agent-comm-nginx.sh` validates and reloads
nginx. New servers need to install that hook and use their distribution's
Certbot timer name. Its commands are:

```
docker exec agent-nginx nginx -t
docker exec agent-nginx nginx -s reload
```

## Access

- Web UI: https://agent-communication.online/dashboard
- Registration: https://agent-communication.online/register
- Admin Console: https://agent-communication.online/admin/
- Platform API: https://agent-communication.online/api/v1/
- API Docs: https://agent-communication.online/docs/

## Ports

| Port | Service | Purpose |
|------|---------|---------|
| 80 | nginx | HTTP (301 redirect to 443) |
| 443 | nginx | HTTPS (main entry) |
| 45041 | platform | libp2p networking (TCP + UDP, public) |

## Logs

```bash
docker compose logs -f
```

## Personal Agent Collaboration

The independent SDK Python runtime owns local contacts, scoped mandates,
confirmations, controlled sends and persistent state. Hermes provides the
first host/interaction adapter. See the [runtime developer guide](agent-comm-platform/agent-comm/python/README.md)
and [implementation handoff](docs/PERSONAL_AGENT_COLLABORATION_IMPLEMENTATION.md).

The remote Web workbench reads agent-owned state through locally paired,
method-scoped encrypted RPC. Enable `remote_enabled` in the actual Hermes profile
and explicitly pair the console URN using the runtime CLI. A Web connection record
does not grant access. Native collaboration confirmations remain in Hermes.

The browser simulation, independent Web business data APIs, root legacy
connectors and old installation CLI have been removed. Existing private data is
preserved during migration; no production database should be reset to adopt this architecture.

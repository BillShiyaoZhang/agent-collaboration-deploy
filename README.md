# Agent Collaboration Deployment

Unified docker-compose setup for agent-comm-platform and agent-collaboration-web.

## Architecture

- **nginx**: Reverse proxy on port 80/443 with Let's Encrypt SSL, routes `/` → platform (landing page), `/api/` and `/admin/` → platform, all other paths → web
- **web**: Next.js frontend on internal port 3000
- **platform**: Go backend on internal port 8080, exposes libp2p on port 45041

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

> **Prisma Schema changes** (web submodule updated the DB schema), additionally run:
> ```bash
> docker compose exec web npx prisma migrate deploy
> ```

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
python -m pip install /absolute/path/to/agent-collaboration-deploy/agent-comm-platform/agent-comm/connectors/hermes-platform
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
connector consumer per helper inbox. See the [migration notes](connectors/README.md)
for removing a duplicate old plugin installation without losing identity or state.

## SSL Auto-Renewal

Let's Encrypt certs expire every 90 days. Add a cron to renew automatically:

```bash
crontab -e
```

Add this line:

```
0 3 * * * certbot renew --pre-hook "docker compose -f /root/agent-collaboration-deploy/docker-compose.yml stop nginx" --post-hook "docker compose -f /root/agent-collaboration-deploy/docker-compose.yml start nginx"
```

## Access

- Web UI: https://agent-communication.online/
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

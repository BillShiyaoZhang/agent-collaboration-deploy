# Agent Collaboration Deployment

Unified docker-compose setup for agent-comm-platform and agent-collaboration-web.

## Architecture

- **nginx**: Reverse proxy on port 80/443 with Let's Encrypt SSL, routes `/` → platform (landing page), `/api/` and `/admin/` → platform, all other paths → web
- **web**: Next.js frontend on internal port 3000
- **platform**: Go backend on internal port 8080, exposes libp2p on port 45041

## Prerequisites

Clone all repositories into the same parent directory:

```
~/
├── agent-collaboration-deploy/    # this repo
├── agent-comm-platform/          # Go backend
├── agent-collaboration-web/       # Next.js frontend
└── agent-comm/                    # Go SDK (sibling to agent-comm-platform)
```

```bash
git clone https://github.com/BillShiyaoZhang/agent-collaboration-deploy.git
git clone https://github.com/BillShiyaoZhang/agent-comm-platform.git
git clone https://github.com/BillShiyaoZhang/agent-collaboration-web.git
git clone https://github.com/BillShiyaoZhang/agent-comm.git
```

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
cd agent-collaboration-deploy
docker compose up --build -d
```

## Update Deployment

When submodule repos have new commits, run on the server:

```bash
git pull --recurse-submodules
docker compose up --build -d
```

> **Prisma Schema changes** (web submodule updated the DB schema), additionally run:
> ```bash
> docker compose exec web npx prisma migrate deploy
> ```

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
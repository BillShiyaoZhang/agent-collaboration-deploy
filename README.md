# Agent Collaboration Deployment

Unified docker-compose setup for agent-comm-platform and agent-collaboration-web.

## Architecture

- **nginx**: Reverse proxy on port 80/443, routes `/` → web, `/api/` → platform
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

## Configuration

Create a `.env` file in this directory:

```bash
NEXTAUTH_SECRET=<generate-with: openssl rand -base64 32>
PLATFORM_ADMIN_TOKEN=<generate-with: openssl rand -hex 16>
NEXTAUTH_URL=http://8.130.40.38
```

## Deployment

```bash
cd agent-collaboration-deploy
docker compose up --build -d
```

## Access

- Web UI: http://8.130.40.38/
- Platform API: http://8.130.40.38/api/

## Ports

| Port | Service | Purpose |
|------|---------|---------|
| 80 | nginx | HTTP entry |
| 443 | nginx | HTTPS (future) |
| 45041 | platform | libp2p networking |

## Logs

```bash
docker compose logs -f
```
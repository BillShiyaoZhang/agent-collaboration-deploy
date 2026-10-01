"""One-process Uvicorn launcher; transport queue limits match application reservations."""
import os
import uvicorn
from .app import GatewayConfig


def main():
    cfg = GatewayConfig.from_env()
    concurrency = int(os.getenv("WORKSPACE_GATEWAY_UVICORN_CONCURRENCY", "256"))
    if concurrency <= 0 or concurrency > 1024:
        raise ValueError("Uvicorn concurrency must be in 1..1024")
    uvicorn.run("workspace_gateway.app:create_app", factory=True, host="0.0.0.0", port=8090,
                workers=1, proxy_headers=False, access_log=False, ws="websockets",
                ws_max_size=cfg.http_limit * 4 // 3 + 65536, ws_max_queue=cfg.ws_max_queue,
                limit_concurrency=concurrency)


if __name__ == "__main__":
    main()

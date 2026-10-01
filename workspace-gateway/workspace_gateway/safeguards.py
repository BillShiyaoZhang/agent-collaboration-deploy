"""Bounded, single-process admission and resource accounting. No business data."""
from __future__ import annotations

from collections import OrderedDict, defaultdict
from dataclasses import dataclass

from fastapi import HTTPException
from .domains import registrable_domain as registrable_domain, validate_origins as validate_origins


class RateTable:
    def __init__(self, maximum, window):
        self.maximum, self.window = maximum, window
        self.entries = OrderedDict()

    def allow(self, key, now, limit, *, cost=1):
        # Fixed-window counters, bounded keys. Never evict live sources to let an
        # attacker rotate addresses and erase another source's quota.
        for existing, (_, until) in list(self.entries.items()):
            if until <= now:
                self.entries.pop(existing)
        if key not in self.entries:
            if len(self.entries) >= self.maximum:
                return False
            self.entries[key] = (0, now + self.window)
        count, until = self.entries[key]
        if not isinstance(cost, int) or isinstance(cost, bool) or cost <= 0:
            raise ValueError("Rate cost must be a positive integer")
        if count + cost > limit:
            return False
        self.entries[key] = (count + cost, until)
        return True


@dataclass
class Lease:
    kind: str
    node: str | None
    size: int
    released: bool = False


class Resources:
    """Mutations never await, so admission is atomic on the ASGI event loop."""
    def __init__(self, config):
        self.config = config
        self.counts = defaultdict(int)
        self.nodes = defaultdict(int)
        self.buffer_bytes = 0
        self.queued_bytes = 0
        self.metrics = {"capacity_rejections": 0, "rate_rejections": 0,
                        "body_timeouts": 0, "backpressure_closes": 0,
                        "tunnel_control_rate_rejections": 0, "tunnel_data_rate_rejections": 0}

    def acquire(self, kind, node=None):
        cfg = self.config
        limit = {"http": cfg.global_http_concurrency, "ws": cfg.global_ws_concurrency,
                 "tunnel": cfg.global_tunnel_concurrency, "control": cfg.control_concurrency}[kind]
        size = {"http": 6 * cfg.http_limit + 131072, "ws": ((cfg.ws_max_queue + 1) * (4 * (cfg.http_limit * 4 // 3 + 65536) + 1024)
                + 12 * cfg.frame_limit + 4096),
                "tunnel": (cfg.ws_max_queue + 1) * (4 * (cfg.http_limit * 4 // 3 + 65536) + 1024),
                "control": 2 * cfg.control_body_limit}[kind]
        node_limit = {"http": cfg.http_concurrency, "ws": cfg.ws_concurrency}.get(kind)
        if (self.counts[kind] >= limit or (node_limit and self.nodes.get((kind, node), 0) >= node_limit)
                or self.buffer_bytes + size > cfg.buffer_bytes):
            self.metrics["capacity_rejections"] += 1
            raise HTTPException(429, "Gateway connection or buffer capacity reached", headers={"Retry-After": str(cfg.rate_window)})
        self.counts[kind] += 1
        if node:
            self.nodes[(kind, node)] += 1
        self.buffer_bytes += size
        return Lease(kind, node, size)

    def release(self, lease):
        if lease is None or lease.released:
            return
        lease.released = True
        self.counts[lease.kind] -= 1
        if lease.node:
            key = (lease.kind, lease.node)
            self.nodes[key] -= 1
            if not self.nodes[key]:
                self.nodes.pop(key)
        self.buffer_bytes -= lease.size

    def queue_charge(self, size):
        if (self.queued_bytes + size > self.config.queued_bytes
                or self.buffer_bytes + size > self.config.buffer_bytes):
            self.metrics["backpressure_closes"] += 1
            raise ValueError("Global browser queue capacity reached")
        self.queued_bytes += size
        self.buffer_bytes += size

    def queue_release(self, size):
        self.queued_bytes -= size
        self.buffer_bytes -= size

    def snapshot(self):
        return {**self.metrics, "connections": dict(self.counts), "buffer_bytes": self.buffer_bytes,
                "queued_bytes": self.queued_bytes}

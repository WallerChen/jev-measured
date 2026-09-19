"""Measure the network round-trip floor to the API host.

Borrowed from anisselbd/jev-phishing-bench, which measures this before quoting
any latency number. Without it you are publishing your own home connection,
not the model: a wall-clock of 380ms from Shanghai to a US host says almost
nothing about how fast Jev is.

Everything the site publishes should therefore be reported as
    wall_clock (raw)  and  wall_clock - floor (compute estimate)
with both shown, so a reader can judge for themselves.
"""

from __future__ import annotations

import socket
import statistics
import time
from urllib.parse import urlparse


def tcp_rtt(host: str, port: int = 443, samples: int = 7, timeout: float = 5.0) -> dict:
    """Median time to complete a TCP handshake — the floor any HTTPS call pays."""
    timings: list[float] = []
    for _ in range(samples):
        started = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=timeout):
                timings.append((time.perf_counter() - started) * 1000)
        except OSError:
            continue
        time.sleep(0.12)

    if not timings:
        return {"host": host, "ok": False, "samples": 0}

    return {
        "host": host,
        "ok": True,
        "samples": len(timings),
        "min_ms": round(min(timings), 1),
        "median_ms": round(statistics.median(timings), 1),
        "max_ms": round(max(timings), 1),
    }


def floor_for(base_url: str, **kwargs) -> dict:
    host = urlparse(base_url).hostname or base_url
    return tcp_rtt(host, **kwargs)


if __name__ == "__main__":
    import json
    import os

    base = os.environ.get("TYPESAFE_BASE_URL", "https://api.typesafe.ai")
    print(json.dumps(floor_for(base), indent=2))

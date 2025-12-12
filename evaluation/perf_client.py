#!/usr/bin/env python3
"""
HTTP benchmark client.

- Returns structured results for notebooks.
- Computes percentiles properly.
- Tracks errors and timeouts.
"""

from __future__ import annotations

import argparse
import statistics
import time
from dataclasses import dataclass
from typing import Any

import requests


def _percentile(sorted_vals: list[float], p: float) -> float:
    """Nearest-rank percentile. p in [0,1]."""
    if not sorted_vals:
        return float("nan")
    k = int(p * len(sorted_vals))
    if k <= 0:
        return sorted_vals[0]
    if k >= len(sorted_vals):
        return sorted_vals[-1]
    return sorted_vals[k - 1]


def run_benchmark(
    url: str,
    num_requests: int = 100,
    warmup: int = 10,
    timeout: float = 3.0,
    allow_redirects: bool = True,
) -> dict[str, Any]:
    latencies_ms: list[float] = []
    errors: list[str] = []

    sess = requests.Session()

    # Warmup
    for _ in range(warmup):
        try:
            r = sess.get(url, timeout=timeout, allow_redirects=allow_redirects)
            r.raise_for_status()
        except Exception:
            pass

    start_all = time.perf_counter()

    for i in range(num_requests):
        t0 = time.perf_counter()
        try:
            r = sess.get(url, timeout=timeout, allow_redirects=allow_redirects)
            r.raise_for_status()
            t1 = time.perf_counter()
            latencies_ms.append((t1 - t0) * 1000.0)
        except Exception as e:
            errors.append(f"{i}:{type(e).__name__}")

    end_all = time.perf_counter()

    total_time = end_all - start_all
    n_ok = len(latencies_ms)
    n_err = len(errors)
    n_total = num_requests

    latencies_ms_sorted = sorted(latencies_ms)

    out = {
        "url": url,
        "n": n_total,
        "ok": n_ok,
        "errors": n_err,
        "error_rate": (n_err / n_total) if n_total else 0.0,
        "total_time_s": total_time,
        "throughput": (n_ok / total_time) if total_time > 0 else float("nan"),
        "latencies": latencies_ms,  # raw samples
    }

    if n_ok > 0:
        out.update(
            {
                "mean": statistics.mean(latencies_ms_sorted),
                "stdev": statistics.pstdev(latencies_ms_sorted),
                "p50": _percentile(latencies_ms_sorted, 0.50),
                "p90": _percentile(latencies_ms_sorted, 0.90),
                "p95": _percentile(latencies_ms_sorted, 0.95),
                "p99": _percentile(latencies_ms_sorted, 0.99),
                "min": latencies_ms_sorted[0],
                "max": latencies_ms_sorted[-1],
            }
        )
    else:
        out.update(
            {
                "mean": float("nan"),
                "stdev": float("nan"),
                "p50": float("nan"),
                "p90": float("nan"),
                "p95": float("nan"),
                "p99": float("nan"),
                "min": float("nan"),
                "max": float("nan"),
            }
        )

    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--requests", type=int, default=100)
    ap.add_argument("--warmup", type=int, default=10)
    ap.add_argument("--timeout", type=float, default=3.0)
    args = ap.parse_args()

    res = run_benchmark(args.url, args.requests, args.warmup, args.timeout)
    print(res)


if __name__ == "__main__":
    main()

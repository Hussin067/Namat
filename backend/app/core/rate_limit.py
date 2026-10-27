"""A small in-memory rate limiter (sliding window) for sensitive endpoints.

- Login: failed attempts are limited per account and per client address, which
  slows down password guessing without locking out a user who signs in normally.
- Registration: limited per client address (slows mass sign-ups and probing
  which emails are registered).
- Medical report and PDF: limited per user, because building them is CPU-heavy.

Limits live in this process's memory. That fits the current single-process
deployment (one uvicorn worker). With several workers or servers each keeps its
own counters, so the effective limit multiplies; move the counters to a shared
store such as Redis before scaling out.

Behind a reverse proxy, run uvicorn with --proxy-headers and a trusted
--forwarded-allow-ips, otherwise every request appears to come from the proxy.
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass
from threading import Lock

from fastapi import HTTPException, Request, status


@dataclass(frozen=True)
class Rule:
    name: str
    limit: int  # requests allowed ...
    window: int  # ... per this many seconds


LOGIN_FAILURES_PER_ACCOUNT = Rule("login-account", 10, 15 * 60)
LOGIN_FAILURES_PER_CLIENT = Rule("login-client", 30, 15 * 60)
REGISTRATIONS_PER_CLIENT = Rule("register-client", 10, 60 * 60)
REPORTS_PER_USER = Rule("report", 60, 10 * 60)
REPORT_PDFS_PER_USER = Rule("report-pdf", 20, 10 * 60)

MAX_KEYS = 50_000  # memory bound: expired keys are pruned beyond this


class RateLimiter:
    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = Lock()

    def _recent(self, key: str, window: int, now: float) -> deque[float]:
        hits = self._hits.get(key)
        if hits is None:
            return deque()
        while hits and hits[0] <= now - window:
            hits.popleft()
        return hits

    def retry_after(self, rule: Rule, key: str) -> int | None:
        """Seconds to wait if `key` has used up `rule`, else None. Records nothing."""
        with self._lock:
            now = self._clock()
            hits = self._recent(f"{rule.name}:{key}", rule.window, now)
            if len(hits) < rule.limit:
                return None
            return max(1, math.ceil(hits[0] + rule.window - now))

    def record(self, rule: Rule, key: str) -> None:
        with self._lock:
            now = self._clock()
            full_key = f"{rule.name}:{key}"
            self._recent(full_key, rule.window, now)
            self._hits.setdefault(full_key, deque()).append(now)
            if len(self._hits) > MAX_KEYS:
                self._prune(now)

    def _prune(self, now: float) -> None:
        # Drop keys with no hits in the longest window used by any rule.
        horizon = max(r.window for r in (LOGIN_FAILURES_PER_ACCOUNT, LOGIN_FAILURES_PER_CLIENT,
                                          REGISTRATIONS_PER_CLIENT, REPORTS_PER_USER, REPORT_PDFS_PER_USER))
        for key in [k for k, hits in self._hits.items() if not hits or hits[-1] <= now - horizon]:
            del self._hits[key]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()


def too_many_requests(retry_after: int) -> HTTPException:
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many attempts. Please wait a moment and try again.",
        headers={"Retry-After": str(retry_after)},
    )


def check(rule: Rule, key: str) -> None:
    """Raise 429 if `key` has used up `rule`."""
    wait = limiter.retry_after(rule, key)
    if wait is not None:
        raise too_many_requests(wait)


def check_and_record(rule: Rule, key: str) -> None:
    """Raise 429 if used up; otherwise count this request."""
    check(rule, key)
    limiter.record(rule, key)


def client_address(request: Request) -> str:
    return request.client.host if request.client else "unknown"

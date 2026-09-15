"""Tiny, dependency-free JSON HTTP client with an on-disk TTL cache.

Only the Python standard library is used, so the "zero-cost, no API keys"
promise holds: no requests/httpx/aiohttp dependency, no SDKs. Every call is
best-effort — a civic app must keep working on a train with no signal, so
failures return ``(None, meta)`` instead of raising.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .. import config

logger = logging.getLogger("citypulse.http")

NEGATIVE_TTL_SECONDS = 300  # remember failures briefly so we do not hammer a dead upstream


@dataclass
class LiveResult:
    """A value plus how trustworthy/fresh it is."""

    data: Any = None
    source: str = "unavailable"  # live | cache | unavailable
    fetched_at: str | None = None
    age_seconds: float | None = None
    error: str | None = None
    cache_key: str = ""

    @property
    def ok(self) -> bool:
        return self.data is not None

    def meta(self) -> dict:
        return {
            "source": self.source,
            "fetched_at": self.fetched_at,
            "age_seconds": round(self.age_seconds, 1) if self.age_seconds is not None else None,
            "stale": self.source == "cache",
            "error": self.error,
        }

    def as_dict(self) -> dict:
        return {"value": self.data, **self.meta()}


def _cache_path(namespace: str, key: str) -> Path:
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:20]
    return config.CACHE_DIR / namespace / f"{digest}.json"


def _read_cache(namespace: str, key: str, ttl_seconds: float) -> LiveResult | None:
    path = _cache_path(namespace, key)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    stored_at = float(payload.get("stored_at", 0))
    age = max(0.0, time.time() - stored_at)
    ttl = ttl_seconds if payload.get("value") is not None else min(ttl_seconds, NEGATIVE_TTL_SECONDS)
    if age > ttl:
        return None
    return LiveResult(
        data=payload.get("value"),
        source="cache",
        fetched_at=payload.get("fetched_at"),
        age_seconds=age,
        error=payload.get("error"),
        cache_key=key,
    )


def _write_cache(namespace: str, key: str, value: Any, error: str | None = None) -> None:
    if not config.CACHE_ENABLED:
        return
    path = _cache_path(namespace, key)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "stored_at": time.time(),
                    "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "value": value,
                    "error": error,
                }
            ),
            encoding="utf-8",
        )
    except OSError as exc:  # pragma: no cover - filesystem dependent
        logger.debug("Could not cache %s/%s: %s", namespace, key, exc)


def clear_cache(namespace: str | None = None) -> int:
    """Drop cached live responses. Used by the refresh endpoint and tests."""
    root = config.CACHE_DIR / namespace if namespace else config.CACHE_DIR
    removed = 0
    if not root.exists():
        return 0
    for path in root.rglob("*.json"):
        try:
            path.unlink()
            removed += 1
        except OSError:  # pragma: no cover
            continue
    return removed


def fetch_json(
    url: str,
    params: dict[str, Any] | None = None,
    *,
    namespace: str,
    ttl_seconds: float,
    timeout: float | None = None,
    headers: dict[str, str] | None = None,
    use_cache: bool = True,
) -> LiveResult:
    """GET ``url`` and decode JSON, preferring a fresh cached copy."""
    query = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v is not None}, doseq=True)
    cache_key = f"{url}?{query}"
    read_only = {"use_cache": use_cache, "namespace": namespace, "ttl": ttl_seconds}
    logger.debug("fetch_json %s %s", url, read_only)

    if use_cache:
        cached = _read_cache(namespace, cache_key, ttl_seconds)
        if cached is not None:
            return cached

    if not config.ENABLE_LIVE_DATA:
        return LiveResult(source="unavailable", error="Live data disabled by configuration", cache_key=cache_key)

    request = urllib.request.Request(
        f"{url}?{query}" if query else url,
        headers={
            "User-Agent": config.HTTP_USER_AGENT,
            "Accept": "application/json",
            **(headers or {}),
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout or config.HTTP_TIMEOUT_SECONDS) as response:
            body = response.read()
        data = json.loads(body.decode("utf-8", errors="replace"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        message = f"{type(exc).__name__}: {exc}"
        logger.info("Live lookup failed for %s (%s)", url, message)
        _write_cache(namespace, cache_key, None, message)
        return LiveResult(source="unavailable", error=message, cache_key=cache_key)
    except json.JSONDecodeError as exc:
        message = f"Invalid JSON from {url}: {exc}"
        logger.warning(message)
        _write_cache(namespace, cache_key, None, message)
        return LiveResult(source="unavailable", error=message, cache_key=cache_key)

    _write_cache(namespace, cache_key, data)
    return LiveResult(
        data=data,
        source="live",
        fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        age_seconds=0.0,
        cache_key=cache_key,
    )


def post_json(
    url: str,
    data: dict[str, Any],
    *,
    namespace: str,
    ttl_seconds: float,
    timeout: float | None = None,
) -> LiveResult:
    """POST a form-encoded body (used by Overpass) with the same caching rules."""
    body = urllib.parse.urlencode(data).encode("utf-8")
    cache_key = f"POST {url} {data.get('data', '')}"
    if config.CACHE_ENABLED:
        cached = _read_cache(namespace, cache_key, ttl_seconds)
        if cached is not None:
            return cached

    if not config.ENABLE_LIVE_DATA:
        return LiveResult(source="unavailable", error="Live data disabled by configuration", cache_key=cache_key)

    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "User-Agent": config.HTTP_USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout or config.HTTP_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        message = f"{type(exc).__name__}: {exc}"
        logger.info("Live POST failed for %s (%s)", url, message)
        _write_cache(namespace, cache_key, None, message)
        return LiveResult(source="unavailable", error=message, cache_key=cache_key)
    except json.JSONDecodeError as exc:
        message = f"Invalid JSON from {url}: {exc}"
        _write_cache(namespace, cache_key, None, message)
        return LiveResult(source="unavailable", error=message, cache_key=cache_key)

    _write_cache(namespace, cache_key, payload)
    return LiveResult(
        data=payload,
        source="live",
        fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        age_seconds=0.0,
        cache_key=cache_key,
    )

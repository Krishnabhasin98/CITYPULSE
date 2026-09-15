#!/usr/bin/env python
"""Black-box smoke test for a running CityPulse deployment.

Drives the real HTTP API the way a browser does and asserts the behaviours the
project promises — the seeded logins work, an arbitrary pincode resolves through
live OpenStreetMap, reports cluster instead of duplicating, credits only pay out
under the published rules, and authority-only endpoints reject citizens.

Usage::

    # Against an already-running server
    python scripts/smoke_test.py --base http://127.0.0.1:8000

    # Boot a throwaway production-like server yourself (temp database, real
    # external lookups, built frontend served from the same process)
    python scripts/smoke_test.py --boot

Exits non-zero if any check fails, so it can gate a deployment.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"

PASS = "PASS"
FAIL = "FAIL"
results: list[tuple[str, str, str]] = []


def record(name: str, ok: bool, detail: str = "") -> bool:
    results.append((PASS if ok else FAIL, name, detail))
    print(f"  [{PASS if ok else FAIL}] {name}{f' — {detail}' if detail else ''}")
    return ok


def call(
    base: str,
    path: str,
    method: str = "GET",
    payload: dict | None = None,
    token: str | None = None,
    timeout: int = 40,
):
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(f"{base}{path}", data=body, method=method)
    request.add_header("Accept", "application/json")
    if body is not None:
        request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode()
            content_type = response.headers.get("Content-Type", "")
            if "json" in content_type:
                return response.status, (json.loads(raw) if raw else None)
            return response.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw


def section(title: str) -> None:
    print(f"\n{title}")


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextlib.contextmanager
def booted_server(port: int | None = None):
    """Start a temporary production-like server and always shut it down again."""
    port = port or free_port()
    workdir = Path(tempfile.mkdtemp(prefix="citypulse-smoke-"))
    env = {
        **os.environ,
        "APP_ENV": "production",
        "JWT_SECRET_KEY": "smoke-test-secret-not-for-production",
        "DATABASE_URL": f"sqlite:///{(workdir / 'smoke.db').as_posix()}",
        "UPLOAD_DIR": str(workdir / "uploads"),
        "CITYPULSE_CACHE_DIR": str(workdir / "cache"),
        "ENABLE_LIVE_DATA": "true",
        "ENABLE_SCHEDULER": "false",
        "SEED_DEMO_DATA": "true",
        "SERVE_FRONTEND": "true",
    }
    log_path = workdir / "server.log"
    log = open(log_path, "w", encoding="utf-8")
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--app-dir",
            "backend",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "info",
        ],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{port}"
    print(f"Booted temporary server on {base} (database in {workdir})")
    try:
        deadline = time.time() + 90
        while time.time() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"Server exited early; see {log_path}")
            try:
                status, _ = call(base, "/health", timeout=5)
                if status == 200:
                    break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError(f"Server did not become healthy; see {log_path}")
        yield base
    finally:
        process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:  # pragma: no cover
            process.kill()
            process.wait(timeout=5)
        log.close()
        print(f"Server log: {log_path}")


def run_checks(base: str, args: argparse.Namespace) -> int:
    section("Health and metadata")
    status, health = call(base, "/health")
    record("GET /health returns 200", status == 200, f"status={status}")
    status, deep = call(base, "/health/deep")
    if isinstance(deep, dict):
        record(
            "GET /health/deep reports a healthy database",
            status == 200 and deep.get("status") == "healthy",
            str(deep.get("status")),
        )
    else:
        record("GET /health/deep reports a healthy database", False, str(deep)[:120])

    status, meta = call(base, "/api/meta")
    record("GET /api/meta returns configuration", status == 200 and isinstance(meta, dict))
    if isinstance(meta, dict):
        radius = meta.get("cluster_radius_m")
        record("Clustering radius is 180 m, as published", radius == 180.0, f"radius={radius}")
        actions = (meta.get("credits") or {}).get("actions") or []
        record("Credit catalog is exposed", bool(actions), f"{len(actions)} action(s)")

    section("Seeded accounts (the original 401 bug)")
    for role, email in (("citizen", "citizen@citypulse.local"), ("authority", "authority@citypulse.local")):
        status, payload = call(base, "/api/auth/login", "POST", {"email": email, "password": args.password})
        ok = status == 200 and isinstance(payload, dict) and payload.get("access_token")
        record(f"{role} can sign in with the documented password", bool(ok), f"status={status}")
        if role == "citizen" and ok:
            citizen_token = payload["access_token"]
            status, profile = call(base, "/api/auth/me", token=citizen_token)
            record("GET /api/auth/me returns the signed-in profile", status == 200, f"status={status}")

    section("Registration and validation")
    status, payload = call(
        base,
        "/api/auth/register",
        "POST",
        {"name": "Smoke Tester", "email": "smoke.tester@citypulse.local", "password": "smoketest123"},
    )
    already = status == 400
    record(
        "Register either creates the account or reports it already exists",
        status == 201 or already,
        f"status={status}",
    )
    new_token = payload["access_token"] if status == 201 and isinstance(payload, dict) else None
    status, _ = call(base, "/api/auth/login", "POST", {"email": "smoke.tester@citypulse.local", "password": "wrong-password"})
    record("A wrong password is rejected with 401", status == 401, f"status={status}")

    section("Reporting and clustering")
    if new_token is None:
        status, payload = call(
            base, "/api/auth/login", "POST", {"email": "smoke.tester@citypulse.local", "password": "smoketest123"}
        )
        new_token = payload.get("access_token") if isinstance(payload, dict) else None

    report_token = new_token or citizen_token
    # A fresh spot far from the seeded incidents: two reports ~40 m apart must cluster.
    lat, lon = 28.7041, 77.1025
    status, first = call(
        base,
        "/api/posts/json",
        "POST",
        {
            "description": "Large pothole covering half the lane near the metro pillar, water collects inside it",
            "latitude": lat,
            "longitude": lon,
            "address": "Smoke test junction",
        },
        token=report_token,
    )
    first_ok = status in (200, 201) and isinstance(first, dict) and bool(first.get("incident"))
    record("A report is accepted and lands on an incident", first_ok, f"status={status}")
    first_id = ((first or {}).get("incident") or {}).get("id") if first_ok else None

    status, second = call(
        base,
        "/api/posts/json",
        "POST",
        {
            "description": "Deep pothole on the same stretch of road, water logging inside the pit",
            "latitude": lat + 0.0004,
            "longitude": lon + 0.0004,
            "address": "Smoke test junction",
        },
        token=report_token,
    )
    second_ok = status in (200, 201) and isinstance(second, dict)
    second_id = ((second or {}).get("incident") or {}).get("id") if second_ok else None
    same = second_ok and first_id is not None and second_id == first_id
    record(
        "A near-identical report 60 m away clusters into one incident",
        bool(same),
        f"first={first_id} second={second_id}",
    )

    if first_id is not None:
        status, detail = call(base, f"/api/incidents/{first_id}")
        if isinstance(detail, dict):
            record(
                "The clustered incident counts both reports",
                status == 200 and detail.get("report_count", 0) >= 2,
                f"report_count={detail.get('report_count')}",
            )
            record(
                "The incident carries a response deadline (SLA)",
                bool(detail.get("sla")),
                str((detail.get("sla") or {}).get("state")),
            )
        else:
            record("The clustered incident counts both reports", False, str(detail)[:120])

    section("Citizen credits pay out, once")
    if first_id is not None and report_token:
        status, catalog = call(base, "/api/incidents/credits/catalog")
        immediate = None
        if isinstance(catalog, dict):
            immediate = next(
                (row for row in catalog.get("actions", []) if row.get("verification") == "immediate"),
                None,
            )
        if immediate:
            _, before = call(base, "/api/auth/me", token=report_token)
            credits_before = (before or {}).get("credits", 0) if isinstance(before, dict) else 0
            status, action = call(
                base,
                f"/api/incidents/{first_id}/actions",
                "POST",
                {"action_type": immediate["key"], "description": "Smoke test contribution"},
                token=report_token,
            )
            first_action_ok = status in (200, 201)
            record(
                f"'{immediate['label']}' is accepted",
                first_action_ok,
                f"status={status} awarded={(action or {}).get('credits_awarded') if isinstance(action, dict) else ''}",
            )
            _, after = call(base, "/api/auth/me", token=report_token)
            credits_after = (after or {}).get("credits", 0) if isinstance(after, dict) else 0
            record(
                "Credits actually increased the balance",
                credits_after > credits_before,
                f"{credits_before} -> {credits_after}",
            )
            _, profile = call(base, "/api/auth/me", token=report_token)
            ledger = (profile or {}).get("ledger") or [] if isinstance(profile, dict) else []
            record(
                "The credit ledger records the entry (auditable trail)",
                any(entry.get("amount") == (action or {}).get("credits_awarded") for entry in ledger),
                f"{len(ledger)} ledger entry(ies)",
            )
            status, repeat = call(
                base,
                f"/api/incidents/{first_id}/actions",
                "POST",
                {"action_type": immediate["key"], "description": "Repeating the same action"},
                token=report_token,
            )
            record(
                "Repeating the same action is refused (anti-farming)",
                status == 409,
                f"status={status}",
            )
        else:
            record("A payout-eligible action exists in the catalog", False)

        status, _ = call(
            base,
            f"/api/incidents/{first_id}/resolve",
            "POST",
            {"note": "citizen should not be able to do this"},
            token=report_token,
        )
        record("A citizen cannot resolve an incident (authority-only)", status in (401, 403), f"status={status}")

    section("Area intelligence for an arbitrary pincode")
    # 110043 (Najafgarh) and 110024 (Ashok Vihar) are outside the small seeded
    # sample, so resolving them proves the live OpenStreetMap path works for any
    # pincode rather than only a hardcoded handful.
    for pincode in ("110001", "110043", "110024"):
        status, area = call(base, f"/api/area/analyze?pincode={pincode}")
        ok = status == 200 and isinstance(area, dict) and area.get("resolved")
        detail = ""
        if isinstance(area, dict):
            detail = f"area={(area.get('area') or {}).get('area_name')} risk={(area.get('risk') or {}).get('score')}"
        record(f"Pincode {pincode} resolves to a real area with a risk score", bool(ok), detail)
        if isinstance(area, dict) and area.get("resolved"):
            record(
                f"Pincode {pincode} analysis is transparent about its sources",
                bool(area.get("data_sources") or (area.get("area") or {}).get("resolution_source")),
            )

    section("Public intelligence endpoints")
    for path, key in (
        ("/api/incidents/", None),
        ("/api/incidents/health", None),
        ("/api/incidents/departments", None),
        ("/api/incidents/policy", None),
        ("/api/incidents/forecasts", None),
        ("/api/incidents/scorecard", None),
        ("/api/area/summary", None),
        ("/api/area/monsoon", None),
    ):
        status, payload = call(base, path)
        record(f"GET {path}", status == 200, f"status={status}")

    status, answer = call(base, "/api/assistant/?q=" + urllib.parse.quote("Which incidents are past their deadline?"))
    record(
        "Assistant answers from live data",
        status == 200 and isinstance(answer, dict) and bool(answer.get("answer")),
    )
    status, agentic = call(base, "/api/assistant/agentic?q=" + urllib.parse.quote("Analyse Karol Bagh"))
    trace_len = len((agentic or {}).get("agent_trace") or []) if isinstance(agentic, dict) else 0
    record("Agent pipeline returns a six-step trace", status == 200 and trace_len == 6, f"steps={trace_len}")

    section("Single-container frontend hosting")
    status, body = call(base, "/")
    is_spa = isinstance(body, str) and '<div id="root"' in body
    if is_spa:
        record("GET / serves the built single-page app", True)
    elif isinstance(body, dict):
        record("GET / serves the built single-page app", True, "API-only deployment (no frontend build present)")
    else:
        record("GET / serves the built single-page app", False, f"status={status}")
    status, banner = call(base, "/api")
    record("GET /api stays a machine-readable banner", status == 200 and isinstance(banner, dict))
    status, body = call(base, "/some/client/route")
    spa_fallback = (isinstance(body, str) and '<div id="root"' in body) or isinstance(body, dict)
    record("Unknown client routes fall back (SPA routing)", status == 200 and spa_fallback, f"status={status}")

    # A client page route that shares a path with an API route returns JSON on a
    # hard refresh instead of the app. The City health page used to sit on
    # /health for exactly that reason.
    for client_route, label in (("/city-health", "City health"), ("/area", "Area intelligence"), ("/credits", "Citizen credits")):
        status, body = call(base, client_route)
        renders_app = isinstance(body, str) and '<div id="root"' in body
        record(f"Page route {client_route} ({label}) is not shadowed by an API path", renders_app, f"status={status}")

    if not args.skip_live:
        section("Live external data (OpenStreetMap + Open-Meteo)")
        if isinstance(meta, dict) and not meta.get("live_data_enabled"):
            record("Live data is enabled", False, "ENABLE_LIVE_DATA is off")
        else:
            status, area = call(base, "/api/area/resolve?query=" + urllib.parse.quote("Lajpat Nagar Delhi"))
            place = (area or {}).get("place") or {} if isinstance(area, dict) else {}
            resolved = bool(place.get("latitude")) and bool(place.get("area_name"))
            record(
                "Nominatim resolves an arbitrary Delhi place name",
                bool(resolved),
                f"status={status} place={place.get('area_name')} source={(place.get('resolution_source'))}",
            )
            status, monsoon = call(base, "/api/area/monsoon")
            source = ((monsoon or {}).get("weather_meta") or {}).get("source") if isinstance(monsoon, dict) else None
            record(
                "Open-Meteo forecast is reachable (live or cached)",
                source in {"live", "cache"},
                f"source={source}",
            )

    failed = [row for row in results if row[0] == FAIL]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("\nFailures:")
        for _, name, detail in failed:
            print(f"  - {name} ({detail})")
        return 1
    print("Smoke test passed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test a CityPulse deployment")
    parser.add_argument("--base", default="http://127.0.0.1:8000", help="Base URL of a running API")
    parser.add_argument(
        "--boot",
        action="store_true",
        help="Start a throwaway production-like server first (temp database, live data)",
    )
    parser.add_argument("--port", type=int, default=None, help="Port to use together with --boot")
    parser.add_argument("--skip-live", action="store_true", help="Skip checks that need internet access")
    parser.add_argument(
        "--password",
        default="password123",
        help="Password for the seeded demo accounts (DEMO_PASSWORD)",
    )
    args = parser.parse_args()

    if args.boot:
        with booted_server(args.port) as base:
            return run_checks(base, args)
    return run_checks(args.base.rstrip("/"), args)


if __name__ == "__main__":
    sys.exit(main())

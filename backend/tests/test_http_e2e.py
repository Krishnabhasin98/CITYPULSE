"""End-to-end HTTP test.

Boots a real uvicorn process against a temporary SQLite database and drives the
public API with ``urllib`` — registration, login, reporting, clustering,
credits, authority-only actions and area intelligence. Set ``CITYPULSE_E2E=0``
to skip it (CI without the ability to bind a local port).
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request

from .helpers import BACKEND_DIR, TEMP_DIR

SKIP = os.getenv("CITYPULSE_E2E", "1") == "0"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def request(base: str, path: str, method: str = "GET", payload: dict | None = None, token: str | None = None):
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(f"{base}{path}", data=body, method=method)
    req.add_header("Accept", "application/json")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode()
            return response.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:  # pragma: no cover
            return exc.code, raw


@unittest.skipIf(SKIP, "CITYPULSE_E2E=0")
class EndToEndTests(unittest.TestCase):
    process: subprocess.Popen | None = None
    base = ""

    @classmethod
    def setUpClass(cls):
        cls.port = _free_port()
        cls.base = f"http://127.0.0.1:{cls.port}"
        env = {
            **os.environ,
            "DATABASE_URL": f"sqlite:///{(TEMP_DIR / 'e2e.db').as_posix()}",
            "CITYPULSE_CACHE_DIR": str(TEMP_DIR / "cache-e2e"),
            "ENABLE_LIVE_DATA": "false",
            "ENABLE_SCHEDULER": "false",
            "SEED_DEMO_DATA": "true",
            "JWT_SECRET_KEY": "e2e-secret",
            "SERVE_FRONTEND": "false",
        }
        # Server output goes to a file rather than a pipe: a pipe that nobody
        # drains can fill and stall the child, and leaks a file handle at exit.
        cls.log_file = open(TEMP_DIR / "e2e-server.log", "w", encoding="utf-8")
        cls.process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(cls.port),
                "--log-level",
                "warning",
            ],
            cwd=str(BACKEND_DIR),
            env=env,
            stdout=cls.log_file,
            stderr=subprocess.STDOUT,
        )
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                status, _ = request(cls.base, "/health")
                if status == 200:
                    return
            except Exception:
                time.sleep(0.4)
        cls.tearDownClass()
        raise RuntimeError("Test server did not start in time")

    @classmethod
    def tearDownClass(cls):
        if cls.process is not None:
            cls.process.terminate()
            try:
                cls.process.wait(timeout=15)
            except subprocess.TimeoutExpired:  # pragma: no cover
                cls.process.kill()
                cls.process.wait(timeout=5)
            cls.process = None
        if getattr(cls, "log_file", None) is not None:
            cls.log_file.close()
            cls.log_file = None

    # ------------------------------------------------------------------
    def test_01_health_and_metadata(self):
        status, payload = request(self.base, "/health/deep")
        self.assertEqual(status, 200, payload)
        self.assertEqual(payload["status"], "healthy")
        self.assertIn("counts", payload)

        status, meta = request(self.base, "/api/meta")
        self.assertEqual(status, 200)
        self.assertEqual(meta["cluster_radius_m"], 180.0)
        self.assertTrue(meta["credits"]["actions"])
        self.assertFalse(meta["authenticated"])

    def test_02_demo_seed_is_present_and_clustered(self):
        status, incidents = request(self.base, "/api/incidents/")
        self.assertEqual(status, 200)
        self.assertTrue(incidents)
        clustered = [row for row in incidents if row["report_count"] > 1]
        self.assertTrue(clustered, "expected the seeded Connaught Place duplicate pair to cluster")

        status, health = request(self.base, "/api/incidents/health")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(health["duplicate_reports_absorbed"], 1)
        self.assertIn("sla", health)

    def test_03_demo_login_works_with_the_documented_password(self):
        status, payload = request(
            self.base,
            "/api/auth/login",
            "POST",
            {"email": "citizen@citypulse.local", "password": "password123"},
        )
        self.assertEqual(status, 200, payload)
        self.assertIn("access_token", payload)
        self.__class__.citizen_token = payload["access_token"]

        status, me = request(self.base, "/api/auth/me", token=payload["access_token"])
        self.assertEqual(status, 200)
        self.assertEqual(me["email"], "citizen@citypulse.local")

    def test_04_wrong_password_is_rejected(self):
        status, _ = request(
            self.base, "/api/auth/login", "POST", {"email": "citizen@citypulse.local", "password": "wrong"}
        )
        self.assertEqual(status, 401)

    def test_05_registration_reporting_and_clustering(self):
        email = f"e2e-{int(time.time())}@test.local"
        status, session = request(
            self.base, "/api/auth/register", "POST", {"name": "E2E Reporter", "email": email, "password": "secret123"}
        )
        self.assertEqual(status, 201, session)
        token = session["access_token"]

        status, first = request(
            self.base,
            "/api/posts/json",
            "POST",
            {
                "description": "Large pothole on the CP inner ring near Block A causing accidents.",
                "latitude": 28.6328,
                "longitude": 77.2197,
                "address": "Connaught Place, New Delhi",
            },
            token=token,
        )
        self.assertEqual(status, 200, first)
        self.assertIn("incident", first)

        status, second = request(
            self.base,
            "/api/posts/json",
            "POST",
            {
                "description": "Same large pothole on the CP inner ring near Block A, buses swerve around it.",
                "latitude": 28.6329,
                "longitude": 77.2199,
            },
            token=token,
        )
        self.assertEqual(status, 200, second)
        self.assertTrue(second["clustered"], second["match_reason"])
        self.assertEqual(second["incident"]["id"], first["incident"]["id"])

        status, detail = request(self.base, f"/api/incidents/{first['incident']['id']}")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(detail["reports"]), 2)
        self.assertIn("cluster", detail)
        self.assertIn("trust_audit", detail)
        self.assertIn("explanation", detail["cluster"])

    def test_06_credits_pay_out_once_and_pending_actions_need_confirmation(self):
        status, session = request(
            self.base, "/api/auth/login", "POST", {"email": "citizen@citypulse.local", "password": "password123"}
        )
        token = session["access_token"]

        status, incidents = request(self.base, "/api/incidents/")
        target = next(row for row in incidents if row["status"] == "open")

        status, action = request(
            self.base,
            f"/api/incidents/{target['id']}/actions",
            "POST",
            {"action_type": "support", "description": "Confirmed on my walk today"},
            token=token,
        )
        self.assertIn(status, (200, 409), action)
        if status == 200:
            self.assertTrue(action["credits_released"])
            self.assertGreater(action["credits_awarded"], 0)

            status, duplicate = request(
                self.base,
                f"/api/incidents/{target['id']}/actions",
                "POST",
                {"action_type": "support", "description": "again"},
                token=token,
            )
            self.assertEqual(status, 409, duplicate)

    def test_07_authority_guards_are_enforced(self):
        status, session = request(
            self.base, "/api/auth/login", "POST", {"email": "citizen@citypulse.local", "password": "password123"}
        )
        citizen = session["access_token"]

        status, incidents = request(self.base, "/api/incidents/")
        target = incidents[0]

        status, denied = request(
            self.base, f"/api/incidents/{target['id']}/resolve", "POST", {}, token=citizen
        )
        self.assertEqual(status, 403, denied)

        status, authority = request(
            self.base, "/api/auth/login", "POST", {"email": "authority@citypulse.local", "password": "password123"}
        )
        self.assertEqual(status, 200)
        status, closed = request(
            self.base,
            f"/api/incidents/{target['id']}/resolve",
            "POST",
            {"verification_notes": "E2E closure"},
            token=authority["access_token"],
        )
        self.assertEqual(status, 200, closed)
        self.assertEqual(closed["incident"]["status"], "resolved")

    def test_08_area_intelligence_answers_for_any_location(self):
        status, known = request(self.base, "/api/area/analyze?query=110001")
        self.assertEqual(status, 200, known)
        self.assertTrue(known["resolved"])
        self.assertEqual(known["area"]["postcode"], "110001")
        self.assertIn("drivers", known["risk"])

        status, unseen = request(self.base, "/api/area/analyze?query=110096")
        self.assertEqual(status, 200)
        self.assertTrue(unseen["resolved"])
        self.assertEqual(unseen["provenance"]["prior_available"], False)
        self.assertTrue(unseen["risk"]["recommended_actions"])

        status, gps = request(self.base, "/api/area/analyze?lat=28.6139&lon=77.2090")
        self.assertEqual(status, 200)
        self.assertTrue(gps["resolved"])

        status, missing = request(self.base, "/api/area/analyze?query=Atlantis")
        self.assertEqual(status, 200)
        self.assertFalse(missing["resolved"])
        self.assertIn("pincode", missing["error"])

    def test_09_assistant_and_agentic_pipeline_use_real_data(self):
        status, answer = request(self.base, "/api/assistant/?q=What%20is%20the%20risk%20in%20110001%3F")
        self.assertEqual(status, 200, answer)
        self.assertEqual(answer["intent"], "area_analysis")
        self.assertIn("risk", answer)

        status, agentic = request(self.base, "/api/assistant/agentic?q=Analyze%20Connaught%20Place%20potholes")
        self.assertEqual(status, 200, agentic)
        self.assertTrue(agentic["synthesis"])
        self.assertEqual(len(agentic["agent_trace"]), 6)
        self.assertIn("limitations", agentic)
        statuses = {step["status"] for step in agentic["agent_trace"]}
        self.assertTrue(statuses & {"COMPLETED", "PARTIAL", "SKIPPED"})

    def test_10_accountability_endpoints(self):
        status, scorecard = request(self.base, "/api/incidents/scorecard")
        self.assertEqual(status, 200)
        self.assertIn("sla", scorecard)

        status, queue = request(self.base, "/api/incidents/queue")
        self.assertEqual(status, 200)
        self.assertTrue(queue)
        self.assertIn("urgency", queue[0])

        status, departments = request(self.base, "/api/incidents/departments")
        self.assertEqual(status, 200)
        self.assertTrue(departments)

        status, policy = request(self.base, "/api/incidents/policy")
        self.assertEqual(status, 200)
        self.assertTrue(policy)

        status, forecasts = request(self.base, "/api/incidents/forecasts")
        self.assertEqual(status, 200)

    def test_11_geojson_and_map_payloads_are_consistent(self):
        status, geojson = request(self.base, "/api/incidents/geojson")
        self.assertEqual(status, 200)
        self.assertEqual(geojson["type"], "FeatureCollection")
        for feature in geojson["features"][:3]:
            longitude, latitude = feature["geometry"]["coordinates"]
            self.assertTrue(28.0 < latitude < 29.0)
            self.assertTrue(76.0 < longitude < 78.0)
            self.assertIn("sla", feature["properties"])

    def test_12_openapi_document_is_valid(self):
        status, schema = request(self.base, "/openapi.json")
        self.assertEqual(status, 200)
        self.assertIn("/api/area/analyze", schema["paths"])
        self.assertIn("/api/incidents/{incident_id}/actions/{action_id}/verify", schema["paths"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

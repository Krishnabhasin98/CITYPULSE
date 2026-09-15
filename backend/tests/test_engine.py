"""Clustering, classification, trust and risk behaviour."""

from __future__ import annotations

import unittest

from ai.classification.classifier import classify_civic_hazard
from ai.duplicate_detection.matcher import evaluate_duplicate_candidate, haversine_meters
from ai.fake_detection.trust_engine import detect_ai_provenance, run_trust_verification_pipeline
from ai.risk.risk_engine import calculate_risk_matrix
from app import config
from app.services.intelligence import serialize_incident
from app.models.credit_transaction import CreditTransaction

from .helpers import CONNAUGHT_PLACE, DatabaseTestCase


class ClusteringTests(DatabaseTestCase):
    def test_duplicate_reports_collapse_into_one_incident(self):
        first = self.make_user("first@test.local")
        second = self.make_user("second@test.local")

        a = self.report(first, "Large pothole on the CP inner ring causing two-wheeler accidents.")
        b = self.report(
            second,
            "Same dangerous pothole on the CP inner ring, buses are swerving around it.",
            latitude=CONNAUGHT_PLACE[0] + 0.0004,
            longitude=CONNAUGHT_PLACE[1] + 0.0004,
        )

        self.assertFalse(a["clustered"])
        self.assertTrue(b["clustered"], b["match_reason"])
        self.assertEqual(self.incident_count(), 1)
        self.assertEqual(b["incident"].report_count, 2)

    def test_reports_beyond_the_radius_stay_separate(self):
        user = self.make_user()
        self.report(user, "Pothole on the CP inner ring near the outer circle.")
        far = self.report(
            user,
            "Pothole on the CP inner ring near the outer circle.",
            latitude=CONNAUGHT_PLACE[0] + 0.01,  # ~1.1 km away
            longitude=CONNAUGHT_PLACE[1],
        )
        self.assertFalse(far["clustered"])
        self.assertEqual(self.incident_count(), 2)

    def test_documented_radius_is_the_one_that_is_applied(self):
        """The engine must not silently fall back to the matcher's 250 m default."""
        user = self.make_user()
        self.report(user, "Deep pothole on the CP inner ring outside the metro gate.")
        offset = (config.CLUSTER_RADIUS_METERS + 40) / 111_320
        result = self.report(
            user,
            "Deep pothole on the CP inner ring outside the metro gate.",
            latitude=CONNAUGHT_PLACE[0] + offset,
            longitude=CONNAUGHT_PLACE[1],
        )
        distance = haversine_meters(
            CONNAUGHT_PLACE[0], CONNAUGHT_PLACE[1], CONNAUGHT_PLACE[0] + offset, CONNAUGHT_PLACE[1]
        )
        self.assertGreater(distance, config.CLUSTER_RADIUS_METERS)
        self.assertFalse(result["clustered"])

    def test_conflicting_category_nearby_is_not_merged_blindly(self):
        user = self.make_user()
        self.report(user, "Large pothole damaging cars on the CP inner ring road.")
        other = self.report(
            user,
            "Garbage bins are overflowing on the CP inner ring near the same corner.",
            latitude=CONNAUGHT_PLACE[0] + 0.0003,
            longitude=CONNAUGHT_PLACE[1],
        )
        # Different category and wording: even at ~35 m it must not be treated as
        # the same real-world incident with high confidence.
        self.assertLess(other["incident"].confidence, 0.99)

    def test_matcher_reports_distance_and_reason(self):
        result = evaluate_duplicate_candidate(
            CONNAUGHT_PLACE[0],
            CONNAUGHT_PLACE[1],
            "pothole near connaught place",
            "Infrastructure",
            CONNAUGHT_PLACE[0] + 0.0005,
            CONNAUGHT_PLACE[1],
            "Pothole near Connaught Place",
            "pothole near connaught place",
            "Infrastructure",
            max_distance_meters=config.CLUSTER_RADIUS_METERS,
        )
        self.assertTrue(result["is_match"])
        self.assertLess(result["distance_m"], config.CLUSTER_RADIUS_METERS)
        self.assertIn("GPS", result["reason"])

    def test_missing_gps_is_explicit(self):
        user = self.make_user()
        result = self.report(user, "Somewhere in Delhi there is a broken footpath.", latitude=None, longitude=None)
        self.assertFalse(result["clustered"])
        self.assertIn("No GPS", result["match_reason"])


class ClassifierTests(unittest.TestCase):
    def test_department_is_matched_to_the_text(self):
        cases = {
            "Garbage and overflowing bins outside the market": ("Sanitation", "Sanitation"),
            "Exposed electrical wiring hanging over the street after rain": ("Electricity", "Electricity"),
            "Water pipeline leak flooding the lane": ("Water", "Water"),
            "Deep pothole on the main road": ("Infrastructure", "Public Works"),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                result = classify_civic_hazard(text)
                self.assertEqual((result["category"], result["department"]), expected)

    def test_consequence_words_do_not_hijack_the_category(self):
        """"pothole ... caused an accident" is still an Infrastructure report."""
        result = classify_civic_hazard("A deep pothole on the CP inner ring caused an accident yesterday.")
        self.assertEqual(result["category"], "Infrastructure")
        self.assertGreater(result["severity"], classify_civic_hazard("A small pothole on the side road.")["severity"])

    def test_high_risk_words_escalate_severity(self):
        calm = classify_civic_hazard("A small pothole on the side road.")
        urgent = classify_civic_hazard("A pothole caused an accident and a child was injured near the school.")
        self.assertGreater(urgent["severity"], calm["severity"])

    def test_claimed_category_is_only_a_tiebreaker(self):
        result = classify_civic_hazard("Garbage piles up outside the school", claimed_category="Infrastructure")
        self.assertEqual(result["category"], "Sanitation")


class TrustTests(unittest.TestCase):
    def test_explicit_ai_provenance_is_detected(self):
        result = detect_ai_provenance(b"Software: Stable Diffusion", "street.png")
        self.assertTrue(result["suspected"])

    def test_ai_provenance_reduces_trust_and_requires_review(self):
        result = run_trust_verification_pipeline(
            "A deep pothole on the CP inner ring is throwing cyclists off their bikes every evening.",
            28.6328,
            77.2197,
            "Connaught Place",
            "/uploads/photo.jpg",
            ai_image_detection={"suspected": True, "reason": "marker"},
        )
        self.assertEqual(result["trust_status"], "Needs Verification")
        self.assertTrue(result["requires_human_review"])

    def test_missing_gps_and_photo_lowers_trust(self):
        weak = run_trust_verification_pipeline("bad", None, None, None, None)
        strong = run_trust_verification_pipeline(
            "A deep pothole on the CP inner ring is throwing cyclists off their bikes every evening.",
            28.6328,
            77.2197,
            "Connaught Place",
            "/uploads/photo.jpg",
            100,
            3,
            0,
        )
        self.assertLess(weak["trust_score"], strong["trust_score"])
        self.assertEqual(strong["trust_status"], "Verified")

    def test_flags_push_an_incident_towards_suspicious(self):
        result = run_trust_verification_pipeline(
            "Pothole reported with a photo.",
            28.6328,
            77.2197,
            "Connaught Place",
            "/uploads/photo.jpg",
            100,
            0,
            5,
        )
        self.assertEqual(result["trust_status"], "Suspicious")
        self.assertTrue(result["requires_human_review"])


class CreditPenaltyTests(DatabaseTestCase):
    def test_ai_provenance_penalty_is_applied_during_ingestion(self):
        user = self.make_user(credits=100)
        result = self.report(
            user,
            "A deep pothole on the CP inner ring is throwing cyclists off their bikes every evening.",
            ai_image_detection={
                "suspected": True,
                "confidence": 0.99,
                "reason": "AI generator marker detected: stable diffusion",
            },
        )
        self.assertEqual(result["credits_awarded"], -40)
        self.assertEqual(result["credits"], 60)
        reasons = [row.reason for row in self.db.query(CreditTransaction).all()]
        self.assertIn("Suspected AI-generated image (automatic review penalty)", reasons)


class RiskTests(unittest.TestCase):
    def test_more_reports_raise_priority(self):
        low = calculate_risk_matrix(40, 1, 0, "Infrastructure")
        high = calculate_risk_matrix(40, 6, 4, "Infrastructure")
        self.assertGreater(high["priority_score"], low["priority_score"])

    def test_priority_maps_to_a_response_window(self):
        critical = calculate_risk_matrix(95, 5, 3, "Public Safety")
        self.assertEqual(critical["level"], "CRITICAL")
        self.assertEqual(critical["action_sla_hours"], 12)


class SerialisationTests(DatabaseTestCase):
    def test_serialised_incident_exposes_sla_and_priority(self):
        user = self.make_user()
        result = self.report(user, "Exposed wiring near the school gate is a shock hazard.")
        payload = serialize_incident(result["incident"])
        self.assertIn("sla", payload)
        self.assertIn("priority_score", payload)
        self.assertEqual(payload["report_count"], 1)
        self.assertEqual(payload["sla"]["state"], "on_track")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
